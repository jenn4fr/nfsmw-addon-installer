# AI / Developer handoff — read first

Last updated: 2026-11-21  
Project version: 0.6.1

## User's objective

Build a reliable Need for Speed Most Wanted (2005) add-on car installation system. Desired UX: one command per archive/folder, automatically identify the package format, use the right native tool, back up everything, verify file/database changes and require a real in-game check before reporting success.

The user has already supplied the reference packages. Do not ask them to upload the same files again. Exact originals are included in `reference_packages/`; hashes and analysis are in `reference_packages/manifest.json` and `reports/reference-package-audit.json`. Extracted working copies are in `/mnt/data/nfsmw-reference-packages` for this session while available.

## User's Windows environment

- OS: Windows 11; Python 3.12; Git Bash.
- Protected original game: `D:\softwares\NFS-MW\Need for Speed Most Wanted Black Edition`.
  - v1.3 Black Edition, Classic ModLoader and Widescreen Fix.
  - Do not modify this folder unless the user explicitly chooses it.
- Target modded game: `D:\softwares\NFS-MW-Unlimiter`.
  - Saved read-only audit: `reports/real-game-installation-audit.json`.
  - `speed.exe` v1.3, 6,029,312 bytes, reference SHA-256 `b248271bf8eac8c9b283b8c95e3add672b713bf529b05f1780e58268493b9d06`.
  - `dinput8.dll`, `scripts/NFSMWUnlimiter.asi`, `scripts/NFSMW-ML.asi`, `scripts/UnlimiterData`, `modloader` folder and NFSMW-ML log present.
  - Attribulina `info` checks passed for `GLOBAL/ATTRIBUTES.BIN` and `GLOBAL/FE_ATTRIB.BIN`.
  - This is an Unlimiter + NFSMW-ML target, not the original Classic ModLoader target.
- Tools root: `D:\softwares\NFS-hack\utils`.
- Known Attribulina CLI path: `D:\softwares\NFS-hack\utils\Attribulina\attribcli.exe`.
- Package search folders: `D:\softwares\NFS-hack\cars` and `D:\softwares\NFS-hack\routes`.
- User prefers precise, concise, step-by-step instructions. Ask for command output before advancing. Do not assume tool versions or successful installs.

## Reference archives already analyzed

1. `nfsmw-addon-installer.zip` — project source archive, SHA-256 in `reports/reference-package-audit.json`.
2. `nfsaddons.com_BugattiChiron.rar` — 2016 Bugatti Chiron.
3. `1970 AMC Rebel The Machine.rar` — AMC Rebel.
4. `Fast n Furious Flip Car-102-1-01-1704391371(1).7z` — Fast & Furious Flip Car.

Extracted reference directories in the current working environment:

- `/mnt/data/nfsmw-reference-packages/bugatti-chiron`
- `/mnt/data/nfsmw-reference-packages/amc-rebel`
- `/mnt/data/nfsmw-reference-packages/flip-car`

Detailed archive hashes, package file counts, script graph, profiles, tool requirements, MWPS and Ed findings are recorded in `reports/reference-package-audit.json` and `docs/REFERENCE_PACKAGE_FINDINGS.md`. Fresh extracted-folder analysis is in `reports/reference-amc-rebel-analysis.json`, `reports/reference-bugatti-chiron-analysis.json` and `reports/reference-flip-car-analysis.json`. The 4-case CLI dry-run matrix is `reports/reference-cli-dry-run-matrix.json`.

### Package-specific findings

- **AMC Rebel:** `Addon/Install.nfsms` copies model files to `CARS/REBEL` and calls `SetupFiles/rebel_install.nfsms`. Ed Config/Resources are included. README says ModLoader replacement for Fiat Punto, but the archive content includes an Addon script and no clear `REPLACE/ADDONS` payload; analyzer flags this mismatch. Correct flow from Ed docs: stage Ed files, run Ed/apply, then install VLT script.
- **Bugatti Chiron:** two alternatives: `unlimiter_addon` and `classic_modloader_replacement`. Add-on has Binary `.end` and NFSMS VLT script; car ID `CHIRON16`; README declares Unlimiter v3 and Binary script credits v2.2.0. Replacement uses MWPS under `REPLACE/ADDONS/CARS_REPLACE/PUNTO`; it is for Classic ModLoader only. Also contains optional save-patcher INI; never edit saves automatically.
- **Flip Car:** Binary `Binary Data Install.end` + `VLT Data Install.nfsms`, nested install/uninstall scripts; car ID `FLIPCAR`; Binary 2.4.0+ and VltEd 4.6 declared in README. Attribulina Mod Installer is used as the guided NFSMS alternative and must be verified on first real install.

## Current implementation

- `nfsmw_installer/archive.py`: safe ZIP extraction and 7-Zip-backed RAR/7z extraction. Checks traversal, links, duplicate/case-colliding names, Windows-unsafe paths and extraction limits; destination must be empty.
- `nfsmw_installer/package_analysis.py`: package analyzer for Binary VERSN1/VERSN2 and move_file sources, recursive NFSMS references/file copies, best-effort AMOD include/collection inspection, direct CARS/UnlimiterData payloads, MWPS, Ed Files, Unlimiter config and save patcher. Detects multiple/alternative profiles.
- `nfsmw_installer/workflow.py`: target-aware profile auto-selection, loader preflight, direct model payload staging, safe backup-root validation, GUI orchestration, Binary move_file/NFSMS file_copy hash checks, mandatory Attribulina pvehicle export read-back for Unlimiter add-ons, manual in-game confirmation and rollback. VltEd readme requirements trigger explicit approval before using Attribulina as the alternative.
- `nfsmw_installer/cli.py`: `analyze-package` and `install` commands plus existing database/donor commands.
- `reports/reference-package-audit.json`: real-package analysis and synthetic preflight matrix.
- `reports/real-game-installation-audit.json`: saved read-only target game audit.
- `docs/REFERENCE_PACKAGE_FINDINGS.md`: human-readable package findings.

## Single-command usage

Dry-run first:

```bash
python -m nfsmw_installer.cli install \
  "/d/softwares/NFS-hack/cars/<package>.rar" \
  --game-root "/d/softwares/NFS-MW-Unlimiter" \
  --tools-root "/d/softwares/NFS-hack/utils"
```

Execute only after reviewing the plan and backup requirements:

```bash
python -m nfsmw_installer.cli install \
  "/d/softwares/NFS-hack/cars/<package>.rar" \
  --game-root "/d/softwares/NFS-MW-Unlimiter" \
  --tools-root "/d/softwares/NFS-hack/utils" \
  --execute
```

For Ed packages add `--ed-root "/d/softwares/NFS-hack/utils/Ed"`. If auto-discovery fails, pass explicit `--binary`, `--attribulina-installer`, `--attribcli`, `--ed-exe`. For an unrecognized car ID, add `--car-id ID`. RAR/7z needs 7-Zip on PATH or `--7zip`. `attribcli.exe` is mandatory for an Unlimiter add-on PASS. If a package lists VltEd as a requirement, the workflow asks you to approve Attribulina as its alternative.

`install` is dry-run by default. The guided `--execute` stage launches GUI tools, but the user still has to select/save the Binary `.end`, apply Ed configs, and choose the Attribulina install option. This is not a headless GUI automation claim.

## Safety rules

- First real install must be on a disposable copy of `D:\softwares\NFS-MW-Unlimiter`.
- Never target the protected original game by default.
- Never combine Bugatti add-on and replacement routes.
- Never install MWPS replacement into the Unlimiter/NFSMW-ML target.
- Never patch career saves automatically. Save-patcher INIs remain manual-only.
- Do not call a package installed because files were copied. Require Binary/Ed/Attribulina completion, file hashes, mandatory pvehicle read-back for Unlimiter add-ons, and in-game confirmation.
- Backups and `install-run.json` are created before writes. Keep the backup root outside GLOBAL/FRONTEND/CARS/scripts/ADDONS/modloader/LANGUAGES and outside the Ed tool folder. Rollback refuses if GLOBAL or FRONTEND changed after install; don't weaken this protection.
- Unknown package formats, missing nested references, invalid Binary manifests and loader conflicts must stop before writes.

## Verification baseline

```bash
python -m compileall -q nfsmw_installer tools tests
python -m unittest discover -s tests -v
```

Current baseline: **75 tests passed**. ZIP extraction is exercised directly; RAR/7z listing safety is covered with mocked 7-Zip output, but real 7-Zip extraction still needs the Windows acceptance run. Run `python tools/verify_reference_bundle.py` to verify all preserved archive hashes and saved analysis reports. `docs/EXTERNAL_TOOL_CAPABILITIES.md` documents verified native-tool automation boundaries; `docs/ACCEPTANCE_TEST_PLAN.md` is the mandatory Windows live-test checklist.

Tests include a mocked end-to-end guided run with Binary/Ed/Attribulina, a mock `attribcli export` read-back and rollback. The three real packages were analyzed and preflighted against synthetic game layouts. No real live-game installation or in-game test has yet been performed.

## Next required work

1. Inspect actual Binary/Attribulina/Ed executable paths and versions in the user's tools root.
2. Clone the target Unlimiter game folder to a disposable test directory.
3. Run Bugatti `unlimiter_addon` dry-run, inspect plan, then execute on the clone.
4. Verify Binary's expected game data changes and Attribulina `pvehicle/chiron16` export.
5. Launch the clone, confirm car appears and can be driven; record any Binary/Attribulina logs and before/after hashes.
6. Repeat with Flip Car, then AMC Rebel (Ed stage first, VLT after Ed).
7. Fix any real GUI/format mismatches before claiming production readiness.

Do not repeat the Attribulina full database scan unless the exports are missing or the user asks for a refresh. The donor catalogue/matcher work remains read-only and should not be entangled with the car installer.
