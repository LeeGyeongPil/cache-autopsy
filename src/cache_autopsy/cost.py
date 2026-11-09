"""Pricing lookup and the missed-cost arithmetic."""
from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from .model import InputFormatError, Usage


@dataclass(frozen=True)
class Rates:
    """USD per 1M tokens for one model."""

    input: float
    write_5m: float
    write_1h: float
    read: float


class Pricing:
    """Per-model unit prices. Unknown models return None, and callers then report tokens only."""

    def __init__(self, table: dict[str, Any]):
        self.table = table

    @classmethod
    def default(cls) -> "Pricing":
        text = resources.files("cache_autopsy").joinpath("pricing.json").read_text(encoding="utf-8")
        return cls(json.loads(text))

    @classmethod
    def from_file(cls, path: str | Path) -> "Pricing":
        """Default table with the entries of ``path`` laid over it."""
        try:
            override = json.loads(Path(path).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise InputFormatError(f"pricing file not found: {path}. Pass an existing JSON file.") from None
        except UnicodeDecodeError:
            raise InputFormatError(f"pricing file {path} is not valid UTF-8. Pass a UTF-8 JSON file.") from None
        except OSError as exc:
            raise InputFormatError(f"cannot read pricing file {path}: {exc.strerror or exc}.") from None
        except json.JSONDecodeError as exc:
            raise InputFormatError(f"pricing file {path} is not valid JSON: {exc}") from None
        if not isinstance(override, dict):
            raise InputFormatError(f"pricing file {path} must contain a JSON object like the bundled pricing.json.")
        base = cls.default().table
        merged = {**base, "_meta": {**base.get("_meta", {}), **override.get("_meta", {})}}
        for family in ("anthropic", "openai"):
            merged[family] = {**base.get(family, {}), **override.get(family, {})}
        return cls(merged)

    def rates(self, provider: str, model: str | None) -> Rates | None:
        family = "anthropic" if provider == "anthropic" else "openai"
        models = self.table.get(family, {})
        matches = [k for k in models if model and model.startswith(k)]
        if not matches:
            return None
        e = models[max(matches, key=len)]
        try:
            if family == "anthropic":
                return Rates(e["input"], e["cache_write_5m"], e["cache_write_1h"], e["cache_read"])
            mult = self.table.get("_meta", {}).get("openai_cache_write_multiplier", 1.25)
            return Rates(e["input"], e["input"] * mult, e["input"] * mult, e["cached_input"])
        except KeyError as exc:
            raise InputFormatError(f"pricing entry for {model!r} lacks field {exc}.") from None


def hit_rate(usages: list[Usage]) -> float | None:
    """Cache reads divided by all input tokens (each provider's own total, see providers/)."""
    total = sum(u.total_input for u in usages)
    return sum(u.cache_read for u in usages) / total if total else None


def cacheable_tokens(provider: str, usage: Usage) -> int:
    """Tokens the previous call left in the cache (what the next call could have read)."""
    if provider == "anthropic":
        return usage.cache_read + usage.cache_write
    if usage.cache_write:
        return usage.cache_read + usage.cache_write
    # OpenAI caches from 1024 tokens upward in 128-token steps (docs, checked 2026-11-09)
    return usage.total_input // 128 * 128 if usage.total_input >= 1024 else 0


def missed_cost(rates: Rates, missed: int, current: Usage, one_hour: bool) -> float:
    """What the missed tokens cost beyond what a cache read would have cost.

    Missed tokens that the response reports as cache writes were billed at the write rate;
    the remainder was billed as ordinary input.
    """
    write_rate = rates.write_1h if one_hour else rates.write_5m
    written = min(missed, current.cache_write)
    extra = written * (write_rate - rates.read) + (missed - written) * (rates.input - rates.read)
    return extra / 1_000_000
