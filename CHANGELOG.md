# Changelog

## 0.2.0 — 2026-11-21
- Added explainable donor shortlist based on configuration class coverage and scalar-field richness.
- Added review-only Hybrid donor configuration proposal with conservative pvehicle field allowlist and identity preservation.
- Added explicit opt-in file-plan executor, overwrite backups, install journal and rollback.
- Added donor matcher and file executor tests.
- Updated README, project status, roadmap, architecture and AI handoff.
- Safety: donor proposal remains non-executable; database scripts are skipped by file executor.
- Hardened rollback journal path validation and added a test rejecting destinations outside the selected game root.
- Donor proposals now include only simple typed scalar values, record omitted fields, and exclude path-like/nested/identity references.

## 0.1.0 — development foundation
- Package inspection, NFSMS parser, database inventory, Attribulina dry-run validation, read-only install planner and donor catalogue extraction.
