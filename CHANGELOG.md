# Changelog

All notable changes to Tabulus are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions follow
[SemVer](https://semver.org/) (pre-1.0, minor/patch only).

## [0.0.4] — 2026-06-29

### Added
- Redactor now catches PEM private-key blocks, Google OAuth (`ya29.`) tokens,
  `Token <value>` auth schemes, and generic `key=value` secrets.
- Values in secret-named columns (`password`, `api_key`, `token`, …) are masked
  by column name, even when the value itself carries no in-text signal.
- Troubleshooting section in the README for common connection failures.
- Animated before/after demo GIF.

### Changed
- Phone matching tightened to require a leading `+` or explicit separators,
  eliminating false positives on bare number runs (years, IDs) and UUIDs.

### Security
- Closes 8 redactor false-negatives found in an adversarial audit. See
  [SECURITY.md](./SECURITY.md) for the redactor's guarantees and known limits.

## [0.0.3] — 2026-06-29

### Fixed
- Packaging: correct wheel source path so `pip install tabulus` ships the
  package cleanly.

## [0.0.2] — 2026-06-29

### Changed
- Project renamed to **Tabulus**.

## [0.0.1]

### Added
- Initial release: MCP server over stdio exposing five tools — `list_tables`,
  `describe_schema`, `sample_rows`, `safe_select`, `explain`.
- Read-only enforcement (keyword gate + Postgres read-only transaction + row cap).
- Opt-in PII/secret redactor (`TABULUS_REDACT=on`).
- Server-side statement timeout and row cap.

[0.0.4]: https://github.com/WalkingMountain/tabulus/releases/tag/v0.0.4
[0.0.3]: https://github.com/WalkingMountain/tabulus/releases/tag/v0.0.3
[0.0.2]: https://github.com/WalkingMountain/tabulus/releases/tag/v0.0.2
[0.0.1]: https://github.com/WalkingMountain/tabulus/releases/tag/v0.0.1
