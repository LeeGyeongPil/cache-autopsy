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
        raise InputFormatError.coded("err.ts_invalid", value=value) from None
    return dt.timestamp() if dt.tzinfo else dt.replace(tzinfo=None).timestamp()


def read_jsonl(path: str | Path) -> Iterator[dict]:
    """Yield records with a ``_line`` field; blank lines are skipped."""
    p = Path(path)
    try:
        handle = p.open(encoding="utf-8-sig")
    except FileNotFoundError:
        raise InputFormatError.coded("err.file_not_found", path=path) from None
    except OSError as exc:  # directory, permission denied, ...
        raise InputFormatError.coded("err.cannot_read_log", path=path, reason=exc.strerror or exc) from None
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
                raise InputFormatError.coded("err.log_not_utf8", number) from None
            except OSError as exc:
                raise InputFormatError.coded("err.cannot_read_midway", number, path=path, reason=exc.strerror or exc) from None
            if not raw.strip():
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise InputFormatError.coded("err.invalid_json_line", number, detail=exc.msg) from None
            if not isinstance(rec, dict) or not isinstance(rec.get("request"), dict):
                raise InputFormatError.coded("err.record_shape", number)
            if "response" in rec and not isinstance(rec["response"], dict):
                raise InputFormatError.coded("err.response_object", number)
            rec["_line"] = number
            yield rec


def read_request(path: str | Path) -> dict:
    """Load one request body; a whole record with a "request" key is accepted too."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise InputFormatError.coded("err.file_not_found", path=path) from None
    except UnicodeDecodeError:
        raise InputFormatError.coded("err.request_not_utf8", path=path) from None
    except OSError as exc:
        raise InputFormatError.coded("err.cannot_read_request", path=path, reason=exc.strerror or exc) from None
    except json.JSONDecodeError as exc:
        raise InputFormatError.coded("err.request_invalid_json", path=path, detail=exc.msg, lineno=exc.lineno) from None
    if isinstance(data, dict) and isinstance(data.get("request"), dict):
        data = data["request"]
    if not isinstance(data, dict):
        raise InputFormatError.coded("err.request_not_object", path=path)
    return data


def dotted(obj: Any, path: str) -> Any:
    """Value at a dotted path such as request.metadata.user_id; None if missing."""
    for key in path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj
