# Changelog

## 0.6.1 — 2026-11-21

- Added a reference-bundle verifier that checks SHA-256 and byte size for all preserved user-supplied archives.
- Added regression checks for the saved analysis reports of AMC Rebel, Bugatti Chiron and Fast & Furious Flip Car.
- Added official external-tool capability notes clarifying GUI/CLI boundaries for Binary, Attribulina, Ed, NFSMW-ML and Unlimiter.
- Added a Windows live acceptance test plan covering dry-run, execution, database read-back, in-game verification and rollback.
- Added mocked 7-Zip listing/path-safety tests; actual RAR/7z extraction remains a Windows acceptance item.
- Updated Windows and Git Bash launchers to prefer the project virtual environment, making the documented one-command workflow work after setup.
- Re-analyzed all three extracted reference packages and verified four CLI dry-run profile selections against disposable synthetic game layouts.


## 0.6.0 — 2026-11-21

- Added target-aware automatic selection when exactly one package route matches the detected loader.
- Added direct Unlimiter `CARS/<id>` and `UnlimiterData` payload staging for AMOD-based add-ons.
- Added best-effort AMOD include/collection analysis and safe rejection of ambiguous NFSMS/AMOD entry points.
- Corrected NFSMS nested `script` resolution to use the documented main-script-relative base, with visible fallback/ambiguity warnings.
- Added uninstall-entrypoint filtering so uninstall scripts are never selected as install scripts.
- Added Binary `move_file` source-to-destination hash verification and NFSMS `file_copy` hash verification.
- Added mandatory `attribcli.exe` read-back for every detected/explicit pvehicle ID before an Unlimiter add-on can reach PASS.
- Added `--car-id` for packages whose car IDs cannot be inferred automatically.
- Expanded NFSMW-ML legacy ModLoader mapping to CARS, FRONTEND, GLOBAL, LANGUAGES and SCRIPTS; unknown groups block preflight.
- Hardened ZIP/RAR/7z extraction checks against traversal, symlinks, duplicate/case-colliding paths and Windows-unsafe path names.
- Strengthened rollback prevalidation to avoid partial restores if GLOBAL/FRONTEND changed after installation.
- Added real reference-package audit reports, actual target-game audit, guided-install journal hashes and additional regression tests.

## 0.5.0 — 2026-11-18

- Initial guided-install workflow with package analysis, loader profiles, transaction backups, external-tool prompts, file verification, database read-back and rollback.
