"""English / Korean message table for everything the CLI prints for humans.

Machine output (``--format json``, cause codes, verdict values, severity words, exit codes) is
never translated. The cause descriptions (``cause.<code>.meaning`` / ``.fix``) are English in
``rules.CAUSES``; ``rules`` registers them into ``MESSAGES["en"]`` when it is imported.

Language order: ``--lang`` > ``CACHE_AUTOPSY_LANG`` > ``LC_ALL`` > ``LC_MESSAGES`` > ``LANG``.
A value starting with ``ko`` selects Korean; anything else (``C``, ``en_US``, junk) is English.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Mapping

LANGS = ("en", "ko")
ENV_VAR = "CACHE_AUTOPSY_LANG"
_ENV_ORDER = (ENV_VAR, "LC_ALL", "LC_MESSAGES", "LANG")

_current = "en"


def resolve_lang(cli_value: str | None, environ: Mapping[str, str]) -> str:
    """Pick ``en`` or ``ko``. Empty environment values are skipped; bad env values mean ``en``."""
    if cli_value in LANGS:
        return cli_value  # type: ignore[return-value]
    for name in _ENV_ORDER:
        value = (environ.get(name) or "").strip()
        if value:
            return "ko" if value.lower().startswith("ko") else "en"
    return "en"


def _width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def ljust(text: str, width: int) -> str:
    """Pad to a display width (Korean characters take two columns) so table columns line up."""
    return text + " " * max(0, width - _width(text))


def rjust(text: str, width: int) -> str:
    return " " * max(0, width - _width(text)) + text


def set_lang(lang: str) -> None:
    global _current
    _current = lang if lang in LANGS else "en"


def current_lang() -> str:
    return _current


def translate(lang: str, key: str, /, **params: object) -> str:
    """Message ``key`` in ``lang`` (falls back to English, then to the key itself)."""
    table = MESSAGES.get(lang) or MESSAGES["en"]
    text = table.get(key)
    if text is None:
        text = MESSAGES["en"].get(key, key)
    return text.format(**params) if params else text


def t(key: str, /, **params: object) -> str:
    """Message ``key`` in the current language."""
    return translate(_current, key, **params)


# ---- OS / JSON error details (Python gives these in English; Korean output maps the common ones) ----
_OS_KO = {
    "Is a directory": "디렉터리입니다",
    "No such file or directory": "파일이나 디렉터리가 없습니다",
    "Permission denied": "권한이 없습니다",
    "Not a directory": "디렉터리가 아닙니다",
    "Input/output error": "입출력 오류",
    "Too many open files": "열린 파일이 너무 많습니다",
    "Operation not permitted": "허용되지 않은 작업입니다",
}
_JSON_KO = (
    ("Expecting value", "값이 필요합니다"),
    ("Expecting property name enclosed in double quotes", "큰따옴표로 감싼 속성 이름이 필요합니다"),
    ("Expecting ':' delimiter", "':' 구분자가 필요합니다"),
    ("Expecting ',' delimiter", "',' 구분자가 필요합니다"),
    ("Extra data", "JSON 뒤에 불필요한 데이터가 있습니다"),
    ("Unterminated string starting at", "닫히지 않은 문자열이 시작되는 위치"),
    ("Invalid control character at", "허용되지 않는 제어 문자 위치"),
    ("Invalid \\escape", "잘못된 이스케이프"),
    ("Invalid \\uXXXX escape", "잘못된 \\uXXXX 이스케이프"),
)
_POS = re.compile(r": line (\d+) column (\d+) \(char (\d+)\)$")


def localize_detail(text: object, lang: str | None = None) -> str:
    """Korean text for a common OS or JSON parser error detail; anything else is returned unchanged."""
    text = str(text)
    if (lang or _current) != "ko":
        return text
    if text in _OS_KO:
        return _OS_KO[text]
    suffix = ""
    m = _POS.search(text)
    if m:
        text, suffix = text[: m.start()], f": {m.group(1)}행 {m.group(2)}열 (문자 {m.group(3)})"
    for en, ko in _JSON_KO:
        if text.startswith(en):
            return ko + text[len(en):] + suffix
    return text + suffix


_EN: dict[str, str] = {
    # ---- errors (code + params; str(exc) is these English sentences) ----
    "err.line_prefix": "line {line}: ",
    "err.ts_invalid": "ts {value!r} is not an ISO-8601 time or epoch number",
    "err.file_not_found": "file not found: {path}. Check the path.",
    "err.cannot_read_log": "cannot read {path}: {reason}. Pass a readable UTF-8 JSONL file.",
    "err.log_not_utf8": "not valid UTF-8. Check that the file is UTF-8 JSONL, not binary or another encoding.",
    "err.cannot_read_midway": "cannot read {path}: {reason}.",
    "err.invalid_json_line": "invalid JSON ({detail}). One JSON object per line is expected.",
    "err.record_shape": 'each record must be an object with a "request" object (and usually a "response" object).',
    "err.response_object": '"response" must be an object.',
    "err.request_not_utf8": "{path} is not valid UTF-8. Pass a UTF-8 JSON file.",
    "err.cannot_read_request": "cannot read {path}: {reason}. Pass a readable JSON file.",
    "err.request_invalid_json": "{path} is not valid JSON: {detail} (line {lineno}).",
    "err.request_not_object": "{path} must contain a JSON object (a request body).",
    "err.pricing_not_found": "pricing file not found: {path}. Pass an existing JSON file.",
    "err.pricing_not_utf8": "pricing file {path} is not valid UTF-8. Pass a UTF-8 JSON file.",
    "err.pricing_cannot_read": "cannot read pricing file {path}: {reason}.",
    "err.pricing_invalid_json": "pricing file {path} is not valid JSON: {detail}",
    "err.pricing_not_object": "pricing file {path} must contain a JSON object like the bundled pricing.json.",
    "err.pricing_missing_field": "pricing entry for {model!r} lacks field {field}.",
    "err.record_not_dict": 'each record must be a dict with a "request" object',
    "err.record_needs_request": 'each record needs a "request" object',
    "err.first_not_object": "the first request must be a JSON object, got {type}",
    "err.second_not_object": "the second request must be a JSON object, got {type}",
    "err.provider_ambiguous": "'openai' is ambiguous; use 'openai_chat' or 'openai_responses'.",
    "err.provider_unknown": "unknown provider {name!r}; choose one of: {choices}.",
    "err.provider_undetected": ("could not detect the provider from this request. Pass provider='anthropic', "
                                "'openai_chat' or 'openai_responses' (CLI: --provider)."),
    "err.usage_int_anthropic": "usage.{key} must be a non-negative integer, got {value!r}",
    "err.usage_int_openai": "usage field {name} must be a non-negative integer, got {value!r}",
    "err.usage_not_object": "response.usage must be an object",
    "err.fail_under_range": "--fail-under must be a ratio between 0 and 1 (got {value}). Write 0.6 for 60%.",
    "err.fail_on_unknown": ("unknown --fail-on value(s): {values}. Run `cache-autopsy causes` for cause codes; "
                            "verdicts are {verdicts}."),
    # ---- cli messages ----
    "cli.error": "error: {detail}",
    "cli.no_records": "warning: no records in {path}.",
    "cli.no_usage": "cannot apply --fail-under: the log has no usage data.",
    "cli.fail_rate": "FAIL: hit rate {rate} < {limit}",
    "cli.fail_on": "FAIL: {count} comparison(s) match --fail-on {wanted}",
    "cli.causes_row": "{code} [{layer}]\n    {meaning}\n    fix: {fix}",
    # ---- help ----
    "help.description": "Find out why an LLM prompt cache missed (offline, no network).",
    "help.lang": "output language: en or ko (default: CACHE_AUTOPSY_LANG, then LC_ALL / LC_MESSAGES / LANG, else en)",
    "help.diff": "first divergence between two request bodies",
    "help.analyze": "hit rate, missed cost and causes for a JSONL call log",
    "help.lint": "risky patterns in one request body",
    "help.causes": "list cause codes and how to fix them",
    "help.demo": "run the bundled practice (mock) data, no keys needed",
    "help.provider": "force the provider (default: detect)",
    "help.context": "characters of context to show (default 40)",
    "help.redact": "do not print any request text",
    "help.pricing": "JSON file overriding the bundled prices",
    "help.session_key": "dotted path to group calls, e.g. request.metadata.user_id",
    "help.min_tokens": "provider minimum cacheable tokens",
    "help.fail_under": "exit 1 if the overall hit rate is below this (0-1)",
    "help.fail_on": "comma list of verdicts or cause codes that make the run fail",
    # ---- report: divergence ----
    "div.reason": "reason : {value}",
    "div.causes": "causes : {value}",
    "div.where": "where  : path={path} {byte}  (local rendering, see README)",
    "div.byte": "byte={offset}",
    "div.byte_na": "byte=n/a (setting change)",
    "div.before": "before : ...{value}",
    "div.old": "old    : {value}",
    "div.new": "new    : {value}",
    "div.fix": "fix    : {value}",
    # ---- report: analysis text ----
    "rep.head": "cache-autopsy: {records} calls, {sessions} session(s), {pairs} comparisons",
    "rep.session": "session {id}: {calls} calls, hit rate {rate}, missed {tokens} tokens, {cost}",
    "rep.col_verdict": "verdict",
    "rep.col_reason": "reason / causes",
    "rep.col_path": "path",
    "rep.col_byte": "byte",
    "rep.col_tokens": "missed tok",
    "rep.col_usd": "missed usd",
    "rep.fix": "      fix: {value}",
    "rep.gap_unknown": "unknown gap",
    "rep.gap": "gap {seconds}s",
    "rep.note": "      note: structure is identical, so this is a suspicion, not a finding ({gap}).",
    "rep.old": "      old: ...{value}",
    "rep.new": "      new: ...{value}",
    "rep.provider_says": "      provider says: {diagnostic} (agree={agree})",
    "rep.total": "hit rate {rate} | missed {tokens} tokens | missed cost {cost}",
    "rep.estimated": " | token counts partly estimated (~)",
    "rep.cost_unavailable": "cost unavailable: no price for {models}; pass --pricing FILE.",
    "rep.by_cause": "by cause:",
    "rep.by_cause_row": "  {code:<28} {pairs:>3} call(s) {tokens:>9} tokens {cost:>10}",
    # ---- report: markdown ----
    "md.title": "## cache-autopsy report",
    "md.summary": "**Hit rate {rate}** · missed {tokens} tokens · missed cost {cost}",
    "md.pairs_head": "| session | # | verdict | reason / causes | path | byte | missed tokens | missed cost |",
    "md.cause_head": "| cause | calls | missed tokens | missed cost |",
    "md.causes_title": "# Cause codes",
    "md.causes_generated": "Generated by `cache-autopsy causes --format md`.",
    "md.causes_head": "| Code | Layer | Meaning | How to fix | Source |",
    # ---- lint ----
    "lint.none": "no findings: nothing in this request is likely to break the cache.",
    "lint.summary": "{warn} warning(s), {info} info",
    "lint.fix_line": "fix: {value}",
    "lint.volatile": "a value that changes between calls sits in the cached prefix ({path}).",
    "lint.no_marker": "no cache_control marker found; nothing will be cached.",
    "lint.too_many": "{count} cache markers found; the limit is {limit}.",
    "lint.breakpoint_volatile": ("{marker} is cached, but the prefix up to it contains a changing value "
                                 "({culprit}), so the cache key never repeats."),
    "lint.below_min": ("estimated ~{est} tokens (characters/4) is below {minimum}; "
                       "providers skip caching under their per-model minimum."),
    # ---- demo ----
    "demo.note": ("NOTE: practice mock data. These are NOT real API logs; "
                  "usage numbers are invented to follow the providers' rules."),
    "demo.note2": "The analyzer really renders, diffs and classifies the fake requests below.",
    "demo.col_session": "session",
    "demo.col_calls": "calls",
    "demo.col_rate": "hit rate",
    "demo.col_tokens": "missed tokens",
    "demo.col_cost": "missed cost",
    "demo.why": "Why 'broken' misses (cause: calls, missed tokens):",
    "demo.row": "  {code:<26} {pairs} call(s)  {tokens} tokens  {cost}",
    "demo.try": "Try: cache-autopsy analyze <your-log>.jsonl   |   cache-autopsy causes",
}

_KO: dict[str, str] = {
    "err.line_prefix": "{line}행: ",
    "err.ts_invalid": "ts {value!r} 값이 ISO-8601 시각이나 epoch 숫자가 아닙니다",
    "err.file_not_found": "파일을 찾을 수 없습니다: {path}. 경로를 확인하세요.",
    "err.cannot_read_log": "{path} 을(를) 읽을 수 없습니다: {reason}. 읽을 수 있는 UTF-8 JSONL 파일을 넘기세요.",
    "err.log_not_utf8": "올바른 UTF-8 이 아닙니다. 바이너리나 다른 인코딩이 아니라 UTF-8 JSONL 인지 확인하세요.",
    "err.cannot_read_midway": "{path} 을(를) 읽을 수 없습니다: {reason}.",
    "err.invalid_json_line": "올바른 JSON 이 아닙니다 ({detail}). 한 줄에 JSON 객체 하나가 필요합니다.",
    "err.record_shape": '각 레코드는 "request" 객체(보통 "response" 객체도)를 가진 객체여야 합니다.',
    "err.response_object": '"response" 는 객체여야 합니다.',
    "err.request_not_utf8": "{path} 은(는) 올바른 UTF-8 이 아닙니다. UTF-8 JSON 파일을 넘기세요.",
    "err.cannot_read_request": "{path} 을(를) 읽을 수 없습니다: {reason}. 읽을 수 있는 JSON 파일을 넘기세요.",
    "err.request_invalid_json": "{path} 은(는) 올바른 JSON 이 아닙니다: {detail} ({lineno}행).",
    "err.request_not_object": "{path} 에는 JSON 객체(요청 본문)가 들어 있어야 합니다.",
    "err.pricing_not_found": "가격표 파일을 찾을 수 없습니다: {path}. 존재하는 JSON 파일을 넘기세요.",
    "err.pricing_not_utf8": "가격표 파일 {path} 은(는) 올바른 UTF-8 이 아닙니다. UTF-8 JSON 파일을 넘기세요.",
    "err.pricing_cannot_read": "가격표 파일 {path} 을(를) 읽을 수 없습니다: {reason}.",
    "err.pricing_invalid_json": "가격표 파일 {path} 은(는) 올바른 JSON 이 아닙니다: {detail}",
    "err.pricing_not_object": "가격표 파일 {path} 에는 기본 pricing.json 처럼 JSON 객체가 들어 있어야 합니다.",
    "err.pricing_missing_field": "{model!r} 의 가격 항목에 {field} 필드가 없습니다.",
    "err.record_not_dict": '각 레코드는 "request" 객체를 가진 dict 여야 합니다',
    "err.record_needs_request": '각 레코드에는 "request" 객체가 필요합니다',
    "err.first_not_object": "첫 번째 요청은 JSON 객체여야 합니다(받은 형식: {type})",
    "err.second_not_object": "두 번째 요청은 JSON 객체여야 합니다(받은 형식: {type})",
    "err.provider_ambiguous": "'openai' 는 모호합니다. 'openai_chat' 또는 'openai_responses' 를 쓰세요.",
    "err.provider_unknown": "알 수 없는 공급자 {name!r}. 다음 중에서 고르세요: {choices}.",
    "err.provider_undetected": ("이 요청에서 공급자를 알아내지 못했습니다. provider='anthropic', "
                                "'openai_chat', 'openai_responses' 중 하나를 넘기세요(CLI: --provider)."),
    "err.usage_int_anthropic": "usage.{key} 는 0 이상의 정수여야 합니다(받은 값: {value!r})",
    "err.usage_int_openai": "usage 필드 {name} 는 0 이상의 정수여야 합니다(받은 값: {value!r})",
    "err.usage_not_object": "response.usage 는 객체여야 합니다",
    "err.fail_under_range": "--fail-under 는 0 과 1 사이의 비율이어야 합니다(받은 값: {value}). 60% 는 0.6 으로 쓰세요.",
    "err.fail_on_unknown": ("알 수 없는 --fail-on 값: {values}. 원인 코드는 `cache-autopsy causes` 로 확인하세요. "
                            "판정 값은 {verdicts} 입니다."),
    "cli.error": "오류: {detail}",
    "cli.no_records": "경고: {path} 에 레코드가 없습니다.",
    "cli.no_usage": "--fail-under 를 적용할 수 없습니다: 로그에 usage 데이터가 없습니다.",
    "cli.fail_rate": "FAIL: 적중률 {rate} < {limit}",
    "cli.fail_on": "FAIL: 비교 {count}건이 --fail-on {wanted} 에 해당합니다",
    "cli.causes_row": "{code} [{layer}]\n    {meaning}\n    해결: {fix}",
    "help.description": "LLM 프롬프트 캐시가 왜 빗나갔는지 찾아냅니다(오프라인, 네트워크 없음).",
    "help.lang": "출력 언어: en 또는 ko (기본: CACHE_AUTOPSY_LANG, 다음 LC_ALL / LC_MESSAGES / LANG, 없으면 en)",
    "help.diff": "두 요청 본문이 처음 달라지는 지점",
    "help.analyze": "JSONL 호출 로그의 적중률·놓친 비용·원인",
    "help.lint": "요청 본문 하나에서 위험한 패턴 찾기",
    "help.causes": "원인 코드와 해결 방법 목록",
    "help.demo": "내장 연습용 목(mock) 데이터로 실행(키 불필요)",
    "help.provider": "공급자를 직접 지정(기본: 자동 감지)",
    "help.context": "보여 줄 앞뒤 문자 수(기본 40)",
    "help.redact": "요청 텍스트를 출력하지 않음",
    "help.pricing": "내장 가격을 덮어쓰는 JSON 파일",
    "help.session_key": "호출을 묶을 점(.) 경로, 예: request.metadata.user_id",
    "help.min_tokens": "공급자의 캐시 최소 토큰 수",
    "help.fail_under": "전체 적중률이 이 값(0-1) 미만이면 종료 코드 1",
    "help.fail_on": "실행을 실패로 만들 판정 값·원인 코드(쉼표로 구분)",
    "div.reason": "이유   : {value}",
    "div.causes": "원인   : {value}",
    "div.where": "위치   : path={path} {byte}  (로컬 렌더링 기준, README 참고)",
    "div.byte": "byte={offset}",
    "div.byte_na": "byte=n/a (설정 변경)",
    "div.before": "앞     : ...{value}",
    "div.old": "이전   : {value}",
    "div.new": "이후   : {value}",
    "div.fix": "해결   : {value}",
    "rep.head": "cache-autopsy: 호출 {records}건, 세션 {sessions}개, 비교 {pairs}건",
    "rep.session": "세션 {id}: 호출 {calls}건, 적중률 {rate}, 놓친 토큰 {tokens}개, {cost}",
    "rep.col_verdict": "판정",
    "rep.col_reason": "이유 / 원인",
    "rep.col_path": "경로",
    "rep.col_byte": "byte",
    "rep.col_tokens": "놓친 토큰",
    "rep.col_usd": "놓친 USD",
    "rep.fix": "      해결: {value}",
    "rep.gap_unknown": "간격 알 수 없음",
    "rep.gap": "간격 {seconds}초",
    "rep.note": "      참고: 구조가 같아서 확정이 아니라 추정입니다 ({gap}).",
    "rep.old": "      이전: ...{value}",
    "rep.new": "      이후: ...{value}",
    "rep.provider_says": "      공급자 진단: {diagnostic} (일치={agree})",
    "rep.total": "적중률 {rate} | 놓친 토큰 {tokens}개 | 놓친 비용 {cost}",
    "rep.estimated": " | 토큰 수 일부는 추정치(~)",
    "rep.cost_unavailable": "비용을 계산할 수 없음: {models} 의 가격이 없습니다. --pricing 파일을 넘기세요.",
    "rep.by_cause": "원인별:",
    "rep.by_cause_row": "  {code:<28} {pairs:>3}건 {tokens:>9} 토큰 {cost:>10}",
    "md.title": "## cache-autopsy 보고서",
    "md.summary": "**적중률 {rate}** · 놓친 토큰 {tokens}개 · 놓친 비용 {cost}",
    "md.pairs_head": "| 세션 | # | 판정 | 이유 / 원인 | 경로 | byte | 놓친 토큰 | 놓친 비용 |",
    "md.cause_head": "| 원인 | 호출 | 놓친 토큰 | 놓친 비용 |",
    "md.causes_title": "# 원인 코드",
    "md.causes_generated": "`cache-autopsy causes --format md` 로 생성했습니다.",
    "md.causes_head": "| 코드 | 구분 | 의미 | 해결 방법 | 출처 |",
    "lint.none": "발견 사항 없음: 이 요청에서 캐시를 깨뜨릴 만한 것이 없습니다.",
    "lint.summary": "경고 {warn}건, 참고 {info}건",
    "lint.fix_line": "해결: {value}",
    "lint.volatile": "호출마다 바뀌는 값이 캐시되는 앞부분에 있습니다 ({path}).",
    "lint.no_marker": "cache_control 표시가 없습니다. 아무것도 캐시되지 않습니다.",
    "lint.too_many": "캐시 표시가 {count}개 있습니다. 한도는 {limit}개입니다.",
    "lint.breakpoint_volatile": ("{marker} 까지 캐시되지만 그 앞부분에 바뀌는 값({culprit})이 있어 "
                                 "캐시 키가 반복되지 않습니다."),
    "lint.below_min": ("추정 ~{est} 토큰(문자 수/4)은 {minimum} 보다 작습니다. "
                       "공급자는 모델별 최소치 미만이면 캐시하지 않습니다."),
    "demo.note": ("안내: 연습용 목(mock) 데이터입니다. 실제 API 로그가 아니며 "
                  "usage 숫자는 공급자 규칙에 맞춰 지어낸 값입니다."),
    "demo.note2": "분석기는 아래 가짜 요청을 실제로 렌더링·비교·분류합니다.",
    "demo.col_session": "세션",
    "demo.col_calls": "호출",
    "demo.col_rate": "적중률",
    "demo.col_tokens": "놓친 토큰",
    "demo.col_cost": "놓친 비용",
    "demo.why": "'broken' 이 빗나가는 이유 (원인: 호출 수, 놓친 토큰):",
    "demo.row": "  {code:<26} {pairs}건  {tokens} 토큰  {cost}",
    "demo.try": "다음: cache-autopsy analyze <내-로그>.jsonl   |   cache-autopsy causes",
}

# cause.<code>.meaning / cause.<code>.fix (English side comes from rules.CAUSES)
_KO_CAUSES: dict[str, tuple[str, str]] = {
    "model_changed": ("모델 이름이 이전 요청과 다릅니다.",
                      "캐시하는 대화 하나에는 모델 하나만 쓰세요. 캐시는 모델별입니다."),
    "tools_changed": ("도구 정의가 다릅니다. 그 뒤의 모든 것이 무효화됩니다.",
                      "같은 도구 목록을 같은 순서, 같은 스키마로 보내세요."),
    "system_changed": ("시스템 프롬프트가 다릅니다. 시스템 프롬프트와 메시지가 무효화됩니다.",
                       "시스템 프롬프트를 호출마다 바이트까지 같게 유지하고, 바뀌는 사실은 마지막 사용자 메시지로 옮기세요."),
    "messages_changed": ("메시지 기록(또는 메시지 수준 설정)의 무언가가 바뀌었습니다.",
                         "새 메시지만 뒤에 덧붙이고, 이전 턴은 받은 그대로 다시 보내세요."),
    "input_changed": ("input/messages/instructions 가 이전 요청과 다릅니다.",
                      "덧붙이기만 하고, 이전 input 항목과 instructions 는 바이트까지 같게 유지하세요."),
    "prompt_cache_key_changed": ("prompt_cache_key 가 달라 요청이 다르게 라우팅됩니다.",
                                 "공유하는 앞부분마다 안정적인 prompt_cache_key 하나를 쓰세요."),
    "service_tier_changed": ("service_tier 가 이전 요청과 다릅니다.",
                             "캐시를 공유해야 하는 요청에는 같은 service_tier 를 쓰세요."),
    "text_format_changed": ("구조화 출력 형식(response_format / text.format)이 바뀌었습니다.",
                            "대화 내내 출력 스키마를 고정하세요."),
    "reasoning_effort_changed": ("추론 강도(reasoning effort)가 바뀌었습니다.",
                                 "캐시하는 대화 안에서는 추론 강도를 일정하게 유지하세요."),
    "verbosity_changed": ("verbosity 설정이 바뀌었습니다.",
                          "캐시하는 대화 안에서는 verbosity 를 일정하게 유지하세요."),
    "tool_order_changed": ("도구는 같지만 순서가 다릅니다.",
                           "보내기 전에 도구를 정렬(예: 이름순)하거나 고정된 순서로 등록하세요."),
    "json_key_order_changed": ("내용은 같지만 JSON 키가 다른 순서로 직렬화되었습니다.",
                               "키 순서가 결정적인 직렬화를 쓰세요(sort_keys=True 또는 고정된 스키마 빌더 하나)."),
    "tool_definition_changed": ("도구의 이름·설명·스키마가 바뀌었습니다.",
                                "도구 정의를 버전 관리되는 상수로 다루고, 의도할 때만 바꾸세요."),
    "timestamp_in_prefix": ("날짜나 시각 값이 캐시되는 앞부분에 있고 호출마다 바뀝니다.",
                            "시계 값을 맨 뒤(마지막 사용자 메시지)로 옮기거나 없애세요."),
    "uuid_in_prefix": ("UUID 가 캐시되는 앞부분에 있고 호출마다 바뀝니다.",
                       "시스템 프롬프트와 도구 텍스트에서 요청별 ID 를 빼거나 마지막 메시지로 옮기세요."),
    "request_id_in_prefix": ("요청별 ID 가 캐시되는 앞부분에 있습니다.",
                             "요청·추적 ID 는 프롬프트 텍스트가 아니라 헤더나 메타데이터에 두세요."),
    "history_edited": ("이전 메시지가 바뀌었거나 삭제되었거나 다시 직렬화되었습니다.",
                       "이전 턴을 고쳐 쓰지 말고, assistant 와 tool_result 블록을 그대로 다시 보내세요."),
    "system_edited": ("시스템 프롬프트 텍스트가 바뀌었습니다.",
                      "시스템 프롬프트에 버전을 붙이고, 의도한 변경마다 캐시가 한 번 다시 쓰인다고 예상하세요."),
    "append_only_ok": ("새 요청이 메시지만 덧붙였습니다. 앞부분은 그대로입니다.",
                       "고칠 것이 없습니다."),
    "identical": ("두 요청의 앞부분이 똑같이 렌더링됩니다.", "고칠 것이 없습니다."),
    "section_added_or_removed": ("섹션 전체(도구, 시스템 등)가 생기거나 사라졌습니다.",
                                "선택 섹션도 대화의 모든 호출에 계속 넣어 두세요."),
    "setting_changed": ("캐시에 영향을 주는 요청 설정이 바뀌었습니다(setting_changed:<필드> 로 표시).",
                        "tool_choice, thinking 같은 설정을 대화 내내 일정하게 유지하세요."),
    "below_min_tokens": ("캐시되는 앞부분이 공급자 최소치보다 짧을 가능성이 높아 아무것도 캐시되지 않습니다.",
                         "공유하는 앞부분을 모델 최소치(공급자 문서 참고)보다 길게 만들거나 캐시를 포기하세요."),
    "breakpoint_on_volatile_block": ("캐시 표시가 호출마다 바뀌는 블록 위 또는 뒤에 있습니다.",
                                     "cache_control 을 바뀌는 것보다 앞의, 마지막으로 안정적인 블록에 두세요."),
    "too_many_breakpoints": ("명시적 cache_control 표시가 4개를 넘습니다.",
                             "명시적 표시는 최대 4개로 유지하세요."),
    "no_cache_marker": ("Anthropic 요청에서 cache_control 표시를 찾지 못했습니다.",
                        "최상위 cache_control 을 추가하거나 마지막으로 안정적인 블록에 표시하세요."),
    "ttl_expired_suspected": ("구조는 같지만 이전 호출과의 간격이 캐시 수명을 넘었습니다(추정).",
                              "TTL 안에 다시 호출하거나 1시간 TTL 을 쓰거나, 다시 쓰이는 것을 받아들이세요."),
    "provider_side_suspected": ("구조가 같고 간격도 짧은데 읽힌 것이 없습니다. 로그만으로는 증명할 수 없습니다.",
                                "라우팅 힌트(prompt_cache_key, 요청 빈도), 동시 첫 호출, 공급자 상태를 확인하세요."),
}
for _code, (_meaning, _fix) in _KO_CAUSES.items():
    _KO[f"cause.{_code}.meaning"] = _meaning
    _KO[f"cause.{_code}.fix"] = _fix

MESSAGES: dict[str, dict[str, str]] = {"en": _EN, "ko": _KO}
