"""Data types and exceptions shared by the whole package (public API types live here)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .i18n import localize_detail, t, translate


class CacheAutopsyError(Exception):
    """Base class for errors this package raises on purpose.

    ``str(exc)`` is always an English sentence. Errors raised through :meth:`coded` also carry a
    message ``code`` and ``params`` so the CLI can show the same error in the chosen language.
    """

    def __init__(self, message: str = "", code: str | None = None, params: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.params = dict(params or {})

    @classmethod
    def coded(cls, code: str, **params: Any):
        """Build the error from message-table key ``code`` (English text in ``str``)."""
        return cls(translate("en", code, **params), code=code, params=params)

    def localized(self) -> str:
        """The error text in the current output language (English when it has no code)."""
        if not self.code:
            return self.message
        params = {k: (localize_detail(v) if k in ("reason", "detail") else v) for k, v in self.params.items()}
        return t(self.code, **params)


class InputFormatError(CacheAutopsyError):
    """A record or request has a shape we cannot read. ``line`` is 1-based when known."""

    def __init__(self, message: str, line: int | None = None, code: str | None = None,
                 params: dict[str, Any] | None = None):
        self.line = line
        prefix = f"line {line}: " if line else ""
        super().__init__(message, code, params)
        self.args = (prefix + message,)

    @classmethod
    def coded(cls, code: str, line: int | None = None, **params: Any):  # type: ignore[override]
        return cls(translate("en", code, **params), line, code, params)

    def localized(self) -> str:
        return (t("err.line_prefix", line=self.line) if self.line else "") + super().localized()


class UnknownProviderError(CacheAutopsyError):
    """The provider could not be detected. Pass provider='anthropic'|'openai_chat'|'openai_responses'."""


@dataclass
class Usage:
    """Provider-neutral token usage of one response."""

    total_input: int  # every input token (uncached + cache reads + cache writes)
    cache_read: int
    cache_write: int = 0
    cache_write_1h: int = 0  # part of cache_write that used the 1-hour TTL (Anthropic)
    estimated: bool = False

    @property
    def hit_rate(self) -> float:
        return self.cache_read / self.total_input if self.total_input else 0.0


@dataclass
class Divergence:
    """Where and why two consecutive requests stop sharing a cacheable prefix."""

    byte_offset: int | None  # UTF-8 byte offset in the locally rendered prefix; None for setting changes
    json_path: str | None  # e.g. tools[0].input_schema.required
    reason: str  # provider-style top-level reason, e.g. tools_changed
    causes: list[str] = field(default_factory=list)  # detailed causes, e.g. tool_order_changed
    context_before: str = ""  # rendered text just before the divergence (same in both requests)
    context_after: str = ""  # rendered text of the NEW request from the divergence on
    context_prev_after: str = ""  # same position in the PREVIOUS request
    prefix_intact: bool = False  # True when the new request only appended (or nothing changed)

    @property
    def fix(self) -> str:
        from .rules import fix_for

        return fix_for(self.causes, self.reason)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["fix"] = self.fix
        return d


@dataclass
class Finding:
    """One lint result for a single request."""

    code: str
    severity: str  # "error" | "warning" | "info"
    path: str
    message: str
    fix: str = ""
    # display-only: message-table key and params so the CLI can show the finding in another language
    msg_key: str = field(default="", repr=False, compare=False)
    msg_params: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("msg_key"), d.pop("msg_params")
        return d


@dataclass
class PairVerdict:
    """Verdict for one request compared with the request before it in the same session."""

    session: str
    index: int  # 1-based position of the pair inside its session
    verdict: str  # hit | expected_hit | explained_miss | unexplained_miss
    divergence: Divergence
    reason: str
    causes: list[str]
    provider: str
    model: str | None
    usage: Usage | None
    prev_usage: Usage | None
    missed_tokens: int = 0
    missed_cost_usd: float | None = None
    tokens_estimated: bool = False
    gap_seconds: float | None = None
    provider_diagnostic: str | None = None
    agree: bool | None = None
    line: int | None = None

    def to_dict(self, redact: bool = False) -> dict[str, Any]:
        d = self.divergence
        return {
            "session": self.session,
            "index": self.index,
            "line": self.line,
            "provider": self.provider,
            "model": self.model,
            "verdict": self.verdict,
            "reason": self.reason,
            "causes": self.causes,
            "json_path": d.json_path,
            "byte_offset": d.byte_offset,
            "missed_tokens": self.missed_tokens,
            "missed_cost_usd": self.missed_cost_usd,
            "tokens_estimated": self.tokens_estimated,
            "gap_seconds": self.gap_seconds,
            "cache_read_tokens": self.usage.cache_read if self.usage else None,
            "total_input_tokens": self.usage.total_input if self.usage else None,
            "provider_diagnostic": self.provider_diagnostic,
            "agree": self.agree,
            "fix": d.fix,
            "context_before": "" if redact else d.context_before,
            "context_after": "" if redact else d.context_after,
        }


@dataclass
class Report:
    summary: dict[str, Any]
    sessions: list[dict[str, Any]]
    pairs: list[PairVerdict]

    def to_dict(self, redact: bool = False) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "sessions": self.sessions,
            "pairs": [p.to_dict(redact) for p in self.pairs],
        }


@dataclass(frozen=True)
class ProviderSpec:
    """How one API flavour renders its cacheable prefix and reports usage (internal)."""

    name: str
    sections: Callable[[dict], list[tuple[str, Any]]]  # ordered (section name, value), absent ones skipped
    section_reason: dict[str, str]  # section name -> provider-style reason
    settings: Callable[[dict], list[tuple[str, str, str, Any]]]  # (reason, label, json_path, value)
    settings_first: bool  # True: setting changes outrank tools/system/messages changes
    usage: Callable[[dict, dict], Usage | None]  # (request, response) -> Usage
    diagnostic: Callable[[dict], str | None]  # provider-reported miss reason in the response
    ttl_seconds: Callable[[dict], int]
    breakpoints: Callable[[dict], list[str]]  # json paths of explicit cache markers
