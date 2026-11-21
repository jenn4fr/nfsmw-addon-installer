# NFS Most Wanted Add-on Installer

**Version:** 0.6.1 (reference-bundle verification and live-acceptance documentation)  
**Target:** Need for Speed: Most Wanted (2005), PC  
**Runtime:** Python 3.10+; no third-party Python runtime packages  
**Windows tools:** 7-Zip for RAR/7z archives; Binary, Attribulina Mod Installer/attribcli and Ed when the package requires them

A safety-first, package-aware installer for common NFS MW car-mod formats. The goal is one command per car package, with the correct native tool used for each format, preflight checks, backups, staged execution, read-back verification and an in-game confirmation gate.

> **Important status:** the guided workflow is implemented and tested with real package archives for analysis/preflight and mocked external-tool execution. It has **not yet been run against the user's live game with the actual Binary, Ed and Attribulina GUIs**. Do the first real install on a disposable copy of the game folder. A successful file copy is never reported as a successful in-game car install.

## Quick start

On Windows, run `setup.bat` once to create the local virtual environment, install the package and run the test suite. After setup, use `start.bat` from Command Prompt or `./start.sh` from Git Bash for the single-command CLI; both prefer the project virtual environment. Or, from Git Bash in the project root:

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -e .
python -m compileall -q nfsmw_installer tools tests
python -m unittest discover -s tests -v
```

The current test suite has **75 passing tests**. ZIP extraction is tested directly; RAR/7z safety parsing is tested with a mocked 7-Zip adapter, and actual 7-Zip extraction is part of the Windows acceptance test. Run `python tools/verify_reference_bundle.py` to validate all four preserved archive hashes and the three real-package analysis reports. For an Unlimiter add-on, `attribcli.exe` is mandatory for the independent database read-back and final PASS gate.

## One-command guided installation

The `install` command accepts an extracted folder or ZIP/RAR/7z archive. The AMOD analyzer follows nested includes and reports missing/unsafe references before any write. It is **dry-run by default**. `--execute` is required before any game or Ed files are written.

### Your separate Unlimiter installation

The saved read-only audit identifies your working target:

`D:\softwares\NFS-MW-Unlimiter`

For first live acceptance, clone it to a disposable folder such as `D:\softwares\NFS-MW-Unlimiter-Test` and point installation commands at the clone. Do not use the protected original Classic ModLoader folder or your working Unlimiter game for the first execution.

It has `speed.exe` v1.3 (6,029,312 bytes), `dinput8.dll`, `scripts/NFSMWUnlimiter.asi`, `scripts/NFSMW-ML.asi`, both game databases and a `modloader` folder. The original Classic ModLoader installation remains a separate protected folder.

The installer searches the tools folder automatically for `Binary.exe`, `AttribulinaModInstaller.exe`, `attribcli.exe` and `Ed.exe`:

```bash
./start.sh install \
  "/d/softwares/NFS-hack/cars/your-car-mod.rar" \
  --game-root "/d/softwares/NFS-MW-Unlimiter-Test" \
  --tools-root "/d/softwares/NFS-hack/utils" \
  --backup-root "/d/softwares/NFS-MW-Backups" \
  --execute
```

If auto-discovery cannot find a tool, pass its path explicitly:

```bash
--binary "/d/softwares/NFS-hack/utils/Binary/Binary.exe" \
--attribulina-installer "/d/softwares/NFS-hack/utils/Attribulina/AttribulinaModInstaller.exe" \
--attribcli "/d/softwares/NFS-hack/utils/Attribulina/attribcli.exe"
```

For packages containing `Ed Files`, also pass the Ed folder (the directory containing `Ed.exe`):

```bash
--ed-root "/d/softwares/NFS-hack/utils/Ed"
```

Run Git Bash/Terminal as Administrator for the first live installation. Close the game before installing or rolling back. The default backup location is `<game-root>/_nfsmw_installer_backups`; use `--backup-root` to store transaction backups elsewhere. Keep the backup root outside `GLOBAL`, `FRONTEND`, `CARS`, `scripts`, `ADDONS`, `modloader` and `LANGUAGES`; the installer rejects unsafe locations. The Attribulina safety snapshot copies the entire `GLOBAL` directory, so make sure there is enough free disk space. Keep Attribulina trace files in `GLOBAL`; its Installed Mods/uninstall workflow depends on them. If an existing destination conflicts, review the dry-run and rerun with `--overwrite` only when you intend to replace it.

### Package-specific profiles

| Profile | Intended package format | Target requirement |
|---|---|---|
| `unlimiter_addon` | Add-on car with CARS model files, Unlimiter data, Binary `.end`, NFSMS/AMOD and/or Ed files | NFSMW Unlimiter |
| `nfsmw_modular_loader` | NFSMW-ML per-mod folder under `modloader/<mod-name>/...`; supported legacy `Modloader/ADDONS` layouts can be mapped when they contain no MWPS patches | `scripts/NFSMW-ML.asi` and `dinput8.dll` |
| `classic_modloader_replacement` | Classic `REPLACE/ADDONS/...` or `Modloader/ADDONS/...` replacement with MWPS patches | Classic `d3d9.dll` ModLoader + `modloader.ini`; kept separate from the Unlimiter/ASI-loader setup |

If an archive has multiple alternatives, the installer selects the one matching the detected target loader when exactly one route is compatible. If two or more routes fit, pass `--profile` explicitly. If a car ID cannot be confidently detected from the package scripts, add it with `--car-id CHIRON16` (repeat `--car-id` for multiple cars). Never install an add-on and its replacement variant together.

For an NFSMW-ML per-mod package:

```bash
python -m nfsmw_installer.cli install "nfsmw-ml-car.zip" \
  --game-root "/d/softwares/NFS-MW-Unlimiter" \
  --profile nfsmw_modular_loader \
  --execute
```

For a Classic ModLoader replacement, use a separate Classic ModLoader game copy and explicitly select `classic_modloader_replacement`. Do not point that profile at the Unlimiter target.

For example, the supplied Bugatti package has both `unlimiter_addon` and `classic_modloader_replacement` routes. On the audited Unlimiter installation, the installer can auto-select `unlimiter_addon`; the MWPS/Classic ModLoader variant is not compatible with that target.

### What happens during `--execute`

1. Safely extract ZIP/RAR/7z into a hash-addressed package cache.
2. Identify package type, nested scripts, model IDs, tool requirements, alternatives and unsafe/missing references.
3. Check the target game loader, executable, databases and Binary dependencies.
4. Create a backup and run journal before any installation stage.
5. Open Binary for `.end` packages. You select the `.end` file in Binary User Mode, choose the game folder and install option, then save.
6. For `Ed Files`, stage `Config/NFSMW` and `Resources/FrontEnd` (plus other recognized Ed resources) into the Ed tool folder, open Ed, select the game folder and apply. Confirm Ed's success message.
7. Open Attribulina Mod Installer with the package's `.nfsms`/`.amod` entry point. Select the game and Install option.
8. Verify Binary `move_file` destinations against source hashes, NFSMS `file_copy` destinations against source hashes, copied Ed/direct-loader payload hashes and database changes. `attribcli.exe` is required for an Unlimiter add-on run; the installer exports every detected `pvehicle/<car-id>` from the live database before allowing PASS.
9. Ask you to launch the game and confirm the car appears and can be driven. Only then can the run report `PASS`.

Binary and Ed are GUI tools; this command orchestrates and guides them but does not automate their buttons. **Binary means MaxHwoy's `Binary.exe`, not the separate Binarius application.** Attribulina Mod Installer also presents package options, which you must select. If a package README specifically requires VltEd, the installer asks you to explicitly approve using Attribulina as the alternative. This is intentional: those tools' own package logic is safer than reimplementing their proprietary operations.

### Useful commands

Analyze a package without touching the game:

```bash
python -m nfsmw_installer.cli analyze-package "car-mod.rar" -o reports/car-analysis.json
```

Build a dry-run installation plan:

```bash
python -m nfsmw_installer.cli install "car-mod.rar" \
  --game-root "/d/softwares/NFS-MW-Unlimiter" \
  --tools-root "/d/softwares/NFS-hack/utils" \
  --profile unlimiter_addon
```

Rollback a guided install using the printed `install-run.json` path:

```bash
python -m nfsmw_installer.cli rollback-install \
  "/path/to/_nfsmw_installer_backups/<run-id>/install-run.json"
```

Rollback restores backed-up files and the pre-Attribulina `GLOBAL` directory snapshot, including Attribulina trace files, plus the pre-Ed `FRONTEND` snapshot. It refuses to restore either directory if it has changed since the install, to avoid overwriting later mod work. Review the error and reconcile manually if that happens.

RAR and 7z extraction require 7-Zip. If it is not on PATH, add `--7zip "/path/to/7z.exe"`.

## Supported formats and safety boundaries

- **Binary `.end`**: parse VERSN1 manifests and VERSN2 script references/target files; delegate actual changes to Binary User Mode.
- **NFSMS `.nfsms`**: resolve nested `script` includes using the documented main-script-relative rule; inspect `file_copy`, `folder_create`, UI controls/options and vehicle-node operations; delegate installation to Attribulina Mod Installer.
- **Attribulina `.amod`**: best-effort inspect nested includes and likely car collection IDs; route to Attribulina Mod Installer, which remains authoritative for script validation/application. `attribcli export` independently verifies each expected vehicle collection.
- **Direct Unlimiter payloads**: copy root `CARS/<id>` model folders and `UnlimiterData` INIs when no Binary/NFSMS script already handles those destinations.
- **Ed Files**: map the package's `Ed Files/Config/NFSMW` and `Ed Files/Resources/FrontEnd/...` paths into the Ed tool folder; Ed performs the game-file changes.
- **Classic ModLoader / MWPS**: copy only to the classic `ADDONS` tree after confirming the Classic ModLoader target. MWPS is not silently converted to an NFSMW-ML patch.
- **NFSMW-ML**: copy a per-mod folder into the `modloader` tree; legacy `Modloader/ADDONS` payloads without MWPS can be mapped into a per-mod folder (`CARS_REPLACE`→`CARS`, plus `FRONTEND`, `GLOBAL`, `LANGUAGES` and `SCRIPTS`). Unknown legacy subfolders stop preflight rather than being silently skipped.
- **Unlimiter data**: inspect per-car `.ini` files and Binary `move_file` targets; do not treat a model-file copy as sufficient proof of car registration.
- **Save patcher files**: detect and report them, but never edit career saves automatically.

Unknown or unsupported installation routes stop during analysis/preflight. The installer does not blindly copy arbitrary files into the game root.

## Other project tools

The existing database intelligence and donor-assist functionality remains available:

- `inspect`
- `inventory-db`
- `validate-db` (conversion/check/strict dry-run; no live apply)
- `plan-install`
- `build-donor-catalogue`
- `donor-assist`
- `apply-file-plan` (separate file-only executor, dry-run unless `--execute`)
- `rollback-install`

See `docs/ARCHITECTURE.md`, `docs/PROJECT_STATUS.md`, `docs/EXTERNAL_TOOL_CAPABILITIES.md`, `docs/ACCEPTANCE_TEST_PLAN.md` and `docs/AI_HANDOFF.md`. The external-tool document explains why the current one-command flow still pauses for native GUI tools; the acceptance plan defines the final Windows live-test gate.

## Real-package test evidence

The following user-supplied reference archives were extracted and analyzed in this session; their checksums and detailed reports are in `reports/reference-package-audit.json`, with fresh analyzer outputs in `reports/reference-*-analysis.json` and dry-run profile evidence in `reports/reference-cli-dry-run-matrix.json`:

- 1970 AMC Rebel The Machine
- 2016 Bugatti Chiron
- Fast & Furious Flip Car

The analyzer resolved the nested NFSMS references in these packages, parsed the Binary installer manifests and reported the separate install routes. The actual extracted reference directories were re-analyzed and saved as `reports/reference-*-analysis.json`. CLI dry-run preflight passed for AMC Rebel, Bugatti add-on, Flip Car and Bugatti Classic ModLoader replacement against disposable synthetic game layouts. A mocked full guided run also exercised Binary, Ed, Attribulina, database read-back, in-game confirmation and rollback. `python tools/verify_reference_bundle.py` verifies the preserved archive hashes and analysis report identities.

**Not yet performed:** actual Binary/Ed/Attribulina installation into the live Windows game, real database read-back after those tools modify the game, or a real in-game drive test. That is the next acceptance gate.
