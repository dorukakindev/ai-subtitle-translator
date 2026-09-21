# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

This project does not publish versioned releases; the `master` branch is the
current state. Entries are grouped by merge date.

## [Unreleased]

## 2026-09-21

### Fixed

- Live-check gate no longer reports a false pass for the first TTL window
  after boot. `time.monotonic()` counts since boot, so the `0.0` default
  made the gate pass with no request while uptime was under 120 s — a dead
  provider could not stop a run. ([#1](https://github.com/dorukakindev/ai-subtitle-translator/pull/1))
- `_run_hybrid` (OpenAI Batch + hybrid flow) no longer runs paid
  Auto-Glossary on files that failed the quality/delivery audit. The
  helper request and its modal dialog (up to a 5-minute worker block) are
  now skipped, matching the sync and two-pass flows; the skip is recorded
  in the report as `skipped / quality_failed`. ([#2](https://github.com/dorukakindev/ai-subtitle-translator/pull/2))

### Changed

- Documentation refresh: README TOCs, an environment-variables table,
  a verified Linux/Tk note, updated module map in `Architecture.md`, and
  corrected the stale "interface is Turkish" limitation (interface is
  English-first). ([#3](https://github.com/dorukakindev/ai-subtitle-translator/pull/3),
  [#4](https://github.com/dorukakindev/ai-subtitle-translator/pull/4))

### Added

- `docs-ci` workflow: markdownlint + link check on documentation pull
  requests. ([#3](https://github.com/dorukakindev/ai-subtitle-translator/pull/3))
