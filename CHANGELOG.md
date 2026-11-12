# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] - 2026-11-12

### Added
- English and Korean output. `--lang en|ko` (before or after the subcommand) or the `CACHE_AUTOPSY_LANG` environment variable chooses the language; otherwise `LC_ALL`, `LC_MESSAGES` and `LANG` are read in that order, a value starting with `ko` means Korean, and anything else is English.
- Translated help texts, text and Markdown reports, lint findings, the `causes` table, the `demo` screen, and error messages (including the details after `error:` / `오류:`; common OS and JSON parser details such as "Is a directory" are translated too).
- `CacheAutopsyError.coded()` and `.localized()`; exceptions keep an English `str()` and carry a message `code` plus `params`.
- `rules.display_fix()` (fix text in the current output language) and `causes_markdown(lang)`.

### Changed
- `demo` banner is English by default (the Korean gloss moved to the Korean output).
- When `LANG` (or `LC_ALL` / `LC_MESSAGES`) starts with `ko`, human-readable output is now Korean. `--format json` output, cause codes, verdict values, `WARNING` / `ERROR` / `INFO`, the `FAIL:` prefix and exit codes are unchanged. `Finding.message`, `Finding.fix`, `Divergence.fix` and `str(exc)` stay English.

## [0.1.1] - 2026-11-10

### Fixed
- JSONL logs, request JSON files and `--pricing` price tables that start with a UTF-8 BOM were rejected with "invalid JSON" (exit 2); they are now read like files without a BOM.

## [0.1.0] - 2026-11-09

### Added
- `diff`, `analyze`, `lint`, `causes` and `demo` commands.
- Anthropic Messages, OpenAI Chat Completions and OpenAI Responses support.
- Pair verdicts (`hit`, `explained_miss`, `unexplained_miss`) combining request structure and usage.
- Missed-token and missed-cost estimates with an overridable price table.
- `--fail-under` / `--fail-on` gates with exit codes 0 / 1 / 2.
- Bundled practice (mock) logs and `scripts/make_samples.py` to regenerate them.
