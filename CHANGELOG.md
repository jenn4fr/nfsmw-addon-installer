# Changelog

## Unreleased — 2026-11-21

- Added read-only donor catalogue extraction from Attribulina complete class exports.
- Updated database scanner to avoid redundant per-collection `get` calls; class exports are used as the catalogue source.
- Added donor catalogue CLI command and tests.
- Expanded README with CLI usage, safety boundaries, current capabilities, and limitations.
- Added project status, AI handoff, roadmap, and architecture documents for future maintainers.
- Verified compilation and 30 unit tests in the update environment.

## 0.1.0 — initial development foundation

- Package inspection and NFSMS parsing.
- Attribulina conversion/check/strict dry-run adapter.
- Read-only database inventory.
- Read-only install planner.
