# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-11-09

### Added
- `diff`, `analyze`, `lint`, `causes` and `demo` commands.
- Anthropic Messages, OpenAI Chat Completions and OpenAI Responses support.
- Pair verdicts (`hit`, `explained_miss`, `unexplained_miss`) combining request structure and usage.
- Missed-token and missed-cost estimates with an overridable price table.
- `--fail-under` / `--fail-on` gates with exit codes 0 / 1 / 2.
- Bundled practice (mock) logs and `scripts/make_samples.py` to regenerate them.
