# Roadmap — v0.6.1

## Stage 1 — Read-only package analysis: implemented
- Binary VERSN1 manifest and VERSN2 script summaries.
- Recursive NFSMS include graph, UI options, file-copy operations and pvehicle IDs.
- AMOD, MWPS, Ed Files, Unlimiter config and save-patcher detection.
- Missing/unsafe path reporting and alternative-profile detection.

## Stage 2 — Loader-aware install planning: implemented foundation
- Unlimiter add-on profile.
- NFSMW-ML per-mod folder profile.
- Classic ModLoader replacement profile.
- Preflight of loader indicators, speed.exe, Binary dependencies and both VLT databases.
- Legacy Modloader/ADDONS mapping to NFSMW-ML only when MWPS is absent.

## Stage 3 — Guided execution and recovery: implemented foundation
- Safe archive extraction.
- Backup-before-write and transaction journal.
- Binary GUI, Ed GUI and Attribulina Mod Installer hand-offs.
- File/hash checks, Attribulina pvehicle export read-back and manual in-game confirmation.
- Rollback for file/database snapshots and Attribulina trace files.

## Stage 4 — Real Windows acceptance: next priority
- Run on a disposable clone of the user's Unlimiter game.
- Verify actual Binary package handling and its optional choices.
- Verify Attribulina Mod Installer handles the nested NFSMS/UI controls in each reference package.
- Verify Ed resource/config staging and output changes.
- Compare actual `attribcli export` results for all affected `pvehicle` and frontend nodes.
- Launch game, locate the car in the intended menu/lot, enter a race/free roam, and confirm geometry, textures, wheels, collision and handling.
- Capture logs, before/after hashes and exact tool versions in a real install report.

## Stage 5 — Stronger verification and productization
- Add typed expected-value manifests for ATTRIBUTES.BIN and FE_ATTRIB.BIN, including frontend registrations.
- Verify Unlimiter configuration references and all Binary data collections, not just file hashes.
- Add exact tool version detection for Binary, Ed, Attribulina and Unlimiter.
- Add more real package fixtures: simple Unlimiter-only, AMOD-only, Binary-only, classic MWPS, NFSMW-ML, and unusual nested options.
- Add CI for Windows and supported Python versions.
- Add uninstall preview and Attribulina-aware uninstall orchestration.
- Add a report viewer and installation profile persistence.

## Acceptance criteria

- Unsupported package formats fail before writing.
- Alternative profiles are never installed together by default.
- Every overwritten file has a restorable backup.
- Database writes are delegated to a supported native tool, then independently read back.
- `PASS` requires the user to confirm the car appears and drives in-game.
- No live install is claimed from mocked tests or file-copy evidence alone.
