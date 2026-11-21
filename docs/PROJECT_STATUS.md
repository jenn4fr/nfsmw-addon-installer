# Project status — v0.6.1

## Implemented in this update

- Safe ZIP extraction with path-traversal, symlink, duplicate/case-collision and Windows-unsafe-path checks; RAR/7z via external 7-Zip with pre-list and post-extraction checks.
- Real-package analyzer for Binary VERSN1/VERSN2 and move_file sources, nested NFSMS scripts and file_copy sources, AMOD include graphs, MWPS, Ed Files, direct CARS/UnlimiterData payloads, save-patcher configs and alternative installation routes.
- Guided `install` command, dry-run by default and explicit `--execute` gate.
- Target-loader preflight and automatic selection when exactly one package route matches Unlimiter, NFSMW-ML or Classic ModLoader.
- Tool discovery under the supplied `--tools-root` (Binary, Attribulina Mod Installer/attribcli and Ed).
- Binary/Ed/Attribulina GUI orchestration with explicit user confirmation gates.
- Backups for declared Binary targets, model destinations, Ed config/resources, game front-end files, and the full pre-Attribulina GLOBAL directory (including trace files).
- Post-stage file/hash checks for Binary move_file, NFSMS file_copy, direct payloads and Ed staging; required Attribulina `pvehicle/<car-id>` export read-back for Unlimiter add-ons.
- Manual in-game confirmation required for final PASS.
- Guided rollback with prevalidated GLOBAL/FRONTEND tree hashes to avoid undoing later unrelated changes or partial rollback.
- Best-effort AMOD include/collection inspection, uninstall-entrypoint filtering, and refusal to guess when both NFSMS and AMOD install entry points are present; Attribulina remains authoritative for AMOD parsing/application.
- Direct root `CARS/<id>` and `UnlimiterData` payload staging for AMOD-based add-ons.
- Real archive analysis of AMC Rebel, Bugatti Chiron and Fast & Furious Flip Car.

## Verified evidence

- `python -m compileall -q nfsmw_installer tools tests`: passed.
- `python -m unittest discover -s tests -v`: **75 tests passed**. The 7-Zip listing parser and traversal/size-limit checks have mocked adapter tests; actual RAR/7z extraction still needs a Windows test with the installed 7-Zip executable.
- Three user-supplied car archives analyzed: 57 package files total; the exact archive bytes are retained in `reference_packages/` with SHA-256 manifest entries.
- Four actual CLI dry-run preflights passed against disposable synthetic game layouts: AMC Unlimiter add-on; Bugatti Unlimiter add-on; Bugatti Classic ModLoader replacement; Flip Car Unlimiter add-on. All were read-only; evidence is in `reports/reference-cli-dry-run-matrix.json`.
- `python tools/verify_reference_bundle.py`: passed for all four preserved archive hashes and all three package-analysis reports.
- Mocked guided install/rollback passed, including Binary, Ed, Attribulina, database export read-back and final user confirmation.
- Saved real-game audit reports `D:\softwares\NFS-MW-Unlimiter` as audited/read-only, with v1.3 `speed.exe`, Unlimiter ASI, NFSMW-ML ASI, dinput8 and both Attribulina database `info` checks passing. This audit was performed on the user environment and was read-only.

## Not claimed complete

- No actual Binary, Ed or Attribulina GUI run has been performed against the live Windows game in this development environment.
- No real in-game car visibility/drive test has been performed.
- Binary and Ed are GUI tools; the command launches them but the user must select options and confirm success.
- Attribulina read-back verifies the expected `pvehicle/<car-id>` collection exists; it does not compare every field/value in both ATTRIBUTES and FE_ATTRIB.
- MWPS is routed to Classic ModLoader only; the installer does not translate MWPS semantics into NFSMW-ML.
- Package-specific Binary/Ed behavior can vary; unsupported commands and unknown layouts must fail closed.
- Unlimiter/Binary version requirements are user-confirmed when declared; a VltEd requirement triggers explicit approval before using Attribulina as the alternative. Tool executable version resources are not yet parsed automatically.

## First live-test policy

Use a disposable copy of `D:\softwares\NFS-MW-Unlimiter`, not the original Classic ModLoader installation. Start with the Bugatti `unlimiter_addon` profile. Review the generated plan and backup location before running `--execute`. Do not install the Bugatti replacement profile into the Unlimiter target.
