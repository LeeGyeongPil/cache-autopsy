"""Reading call records: one JSON object per line with request, response, optional session_id/ts."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from .model import InputFormatError


def parse_ts(value: Any) -> float | None:
    """Seconds since the epoch from an ISO-8601 string or a number; None if absent."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        raise InputFormatError(f"ts {value!r} is not an ISO-8601 time or epoch number") from None
    return dt.timestamp() if dt.tzinfo else dt.replace(tzinfo=None).timestamp()


def read_jsonl(path: str | Path) -> Iterator[dict]:
    """Yield records with a ``_line`` field; blank lines are skipped."""
    p = Path(path)
    try:
        handle = p.open(encoding="utf-8-sig")
    except FileNotFoundError:
        raise InputFormatError(f"file not found: {path}. Check the path.") from None
    except OSError as exc:  # directory, permission denied, ...
        raise InputFormatError(f"cannot read {path}: {exc.strerror or exc}. Pass a readable UTF-8 JSONL file.") from None
    with handle:
        number = 0
        lines = iter(handle)
        while True:
            number += 1
            try:
                raw = next(lines)
            except StopIteration:
                return
            except UnicodeDecodeError:
                raise InputFormatError("not valid UTF-8. Check that the file is UTF-8 JSONL, not binary or another encoding.", number) from None
            except OSError as exc:
                raise InputFormatError(f"cannot read {path}: {exc.strerror or exc}.", number) from None
            if not raw.strip():
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise InputFormatError(f"invalid JSON ({exc.msg}). One JSON object per line is expected.", number) from None
            if not isinstance(rec, dict) or not isinstance(rec.get("request"), dict):
                raise InputFormatError(
                    'each record must be an object with a "request" object '
                    '(and usually a "response" object).', number)
            if "response" in rec and not isinstance(rec["response"], dict):
                raise InputFormatError('"response" must be an object.', number)
            rec["_line"] = number
            yield rec


def read_request(path: str | Path) -> dict:
    """Load one request body; a whole record with a "request" key is accepted too."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise InputFormatError(f"file not found: {path}. Check the path.") from None
    except UnicodeDecodeError:
        raise InputFormatError(f"{path} is not valid UTF-8. Pass a UTF-8 JSON file.") from None
    except OSError as exc:
        raise InputFormatError(f"cannot read {path}: {exc.strerror or exc}. Pass a readable JSON file.") from None
    except json.JSONDecodeError as exc:
        raise InputFormatError(f"{path} is not valid JSON: {exc.msg} (line {exc.lineno}).") from None
    if isinstance(data, dict) and isinstance(data.get("request"), dict):
        data = data["request"]
    if not isinstance(data, dict):
        raise InputFormatError(f"{path} must contain a JSON object (a request body).")
    return data


def dotted(obj: Any, path: str) -> Any:
    """Value at a dotted path such as request.metadata.user_id; None if missing."""
    for key in path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj
