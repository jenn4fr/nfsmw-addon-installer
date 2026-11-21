# Windows live acceptance test plan

This is the remaining gate before calling the installer production-ready. It must be run on Windows against a disposable copy of the user's separate Unlimiter game folder, never the protected original Classic ModLoader installation.

## Preconditions

- Windows 11, Python 3.10+ (user currently has Python 3.12).
- 7-Zip installed and available on PATH for RAR/7z inputs.
- Binary.exe (MaxHwoy/SpeedReflect), AttribulinaModInstaller.exe, attribcli.exe and Ed.exe available under the configured tools root as needed.
- The test target is a disposable clone of `D:\softwares\NFS-MW-Unlimiter`.
- The game is closed; enough free disk space exists for a full `GLOBAL` snapshot and backups.
- Keep the original package archives and the pre-test game clone unchanged.

## Baseline

From the project folder in Git Bash:

```bash
python tools/verify_reference_bundle.py
python -m compileall -q nfsmw_installer tools tests
python -m unittest discover -s tests -v
python -m nfsmw_installer.cli --help
```

Expected: reference archive hashes and saved analysis reports pass; all tests pass; CLI help lists `analyze-package` and `install`.

## Dry-run matrix

Run the `install` command without `--execute` for each package. Inspect the generated plan JSON and ensure it chooses only the intended profile:

| Package | Target | Expected profile |
|---|---|---|
| Bugatti Chiron | disposable Unlimiter clone | `unlimiter_addon` |
| Bugatti Chiron | separate disposable Classic ModLoader clone | `classic_modloader_replacement` |
| Flip Car | disposable Unlimiter clone | `unlimiter_addon` |
| AMC Rebel | disposable Unlimiter clone | `unlimiter_addon`, with README mismatch warning visible |

No target files or databases may change during dry-run.

## Execute sequence

Use a fresh clone for each package, or restore the clone from a clean image before the next package.

1. **Bugatti Chiron add-on:** run with `--execute`. In Binary User Mode choose the add-on `.end` route and follow the package's options. Apply the NFSMS VLT script with Attribulina Mod Installer. Confirm all declared tool steps. Verify the Binary `move_file` files by hash, NFSMS `file_copy` files by hash, both database files changed, and `attribcli export GLOBAL pvehicle/chiron16 --children` contains the expected collection. Launch game and verify car visibility, garage selection, geometry, textures, wheels, collision and driving.
2. **Flip Car:** run with `--execute`. Binary requirements in its README include Binary 2.4.0+ and VltEd 4.6; this project asks for explicit approval before substituting Attribulina for the NFSMS/VltEd step. Verify `CARS/FLIPCAR`, `scripts/UnlimiterData/FLIPCAR.ini`, Binary targets, `pvehicle/flipcar` read-back and in-game drive test.
3. **AMC Rebel:** run with `--execute`. Stage Ed files, run Ed and wait for its success dialog. Only then run the VLT installer. Verify `CARS/REBEL`, frontend textures/config, `pvehicle/rebel` read-back and in-game drive test. Investigate the README/replacement-vs-addon warning; use the detected Unlimiter add-on route only if the user confirms that is the intended variant.
4. **Bugatti replacement:** separately test only against the Classic ModLoader clone. Confirm the MWPS replacement goes to `ADDONS`, never into the Unlimiter target. Do not install the add-on route in this test.

## Failure and rollback tests

- Cancel Binary before saving: installer must stop; journal and backups remain.
- Decline the Ed success prompt: VLT stage must not start.
- Decline Attribulina success prompt or make its database read-back fail: run must not PASS.
- Simulate an existing destination without `--overwrite`: preflight must stop before writes.
- Repeat with `--overwrite`: confirm the original file is in the transaction backup.
- Trigger a post-install failure, then run `rollback-install` with the printed `install-run.json`. Verify original file hashes and full `GLOBAL` tree hash are restored.
- Modify `GLOBAL` after install and attempt rollback: rollback must refuse rather than destroy later work.

## PASS criteria

A package is PASS only when all are true:

- The correct profile was selected and every native tool stage was explicitly confirmed.
- Every declared model/config payload exists and its expected hash matches.
- Binary-declared targets changed as expected.
- Both database files were updated for database-driven Unlimiter add-ons.
- `attribcli export` independently reads back every expected `pvehicle/<car-id>` collection.
- The game launches with the intended loader.
- The car appears in the intended menu/garage and can be driven without missing geometry/textures/wheels or obvious collision/handling failure.

Record OS/game/tool versions, package SHA-256, plan JSON, install journal, Binary/Ed/Attribulina logs, before/after hashes, database read-back exports and screenshots/video of the in-game test.

A synthetic test, mocked GUI stage, successful copy or successful database collection export alone is not a production acceptance PASS.
