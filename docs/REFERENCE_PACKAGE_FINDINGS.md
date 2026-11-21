# Reference package findings — 2026-11-21

The following user-supplied archives were extracted and analyzed. The originals are preserved in `reference_packages/` inside the project bundle. Their filenames, sizes and SHA-256 hashes are recorded in both `reference_packages/manifest.json` and `reports/reference-package-audit.json`, so the same fixtures can be used again without re-uploading.

No game files were changed during this analysis.

## 1. 1970 AMC Rebel The Machine

- 10 files; car ID detected: `REBEL`.
- Detected route: `unlimiter_addon`.
- NFSMS entry point: `Addon/Install.nfsms`.
- Nested VLT script: `Addon/SetupFiles/rebel_install.nfsms`.
- The entry point includes model file copies to `CARS/REBEL` and then runs the VLT script.
- Contains Ed configuration and resources: `Config/NFSMW/REBEL.ini` plus FrontEnd texture assets.
- The archive README describes a ModLoader replacement for Fiat Punto, while the archive's `Addon` folder contains an add-on installation script and Ed pack, with no clear `REPLACE/ADDONS` payload. This mismatch is flagged; inspect the package's chosen `Addon` path rather than assuming the README alone describes the archive contents.
- Correct guided order: stage Ed files -> run Ed and apply -> run the NFSMS script through Attribulina Mod Installer -> read back `pvehicle/rebel` -> test in-game.

## 2. 2016 Bugatti Chiron

- 26 files; car ID detected: `CHIRON16`.
- Two mutually exclusive profiles:
  - `unlimiter_addon`: Binary `.end` package plus NFSMS VLT installer and model payload.
  - `classic_modloader_replacement`: Fiat Punto replacement payload under `REPLACE/ADDONS`, including MWPS patches.
- The add-on README declares NFSMW Unlimiter v3. Binary script credits identify Binary v2.2.0; this is a credited version, not a declared minimum requirement. The installer asks the user to confirm the declared Unlimiter requirement.
- Binary manifest `ADDON/2016 Bugatti Chiron Installer.end` resolves its `Files/_Settings/setup.end` script. The setup branches to install/uninstall scripts; the package includes both Binary install and uninstall scripts.
- NFSMS entry point: `ADDON/2016 Bugatti Chiron VLT.nfsms`; nested scripts include file/model copy and VLT changes.
- Contains a save-patcher INI. It is reported as manual-only; the installer never modifies career saves.
- For the audited Unlimiter target, select **only** `unlimiter_addon`. The Classic ModLoader/MWPS route is an alternative for a different game installation and should not be mixed into the Unlimiter folder.

## 3. Fast & Furious Flip Car

- 21 files; car ID detected: `FLIPCAR`.
- Detected route: `unlimiter_addon`.
- Binary entry point: `Binary Data Install.end`, with `Binary Files/global_install.end` and appended texture scripts.
- VLT entry point: `VLT Data Install.nfsms`, with install/uninstall options and nested `flipcar_install.nfsms` / `cam_stuffs.nfsms` scripts.
- Binary script moves the car model and Unlimiter per-car configuration, and imports car/part data into the game's data files.
- README requirements: Binary 2.4.0 or higher and Vlt-Ed 4.6. The guided workflow uses Attribulina Mod Installer for the NFSMS script; that substitution must be confirmed during the first real Windows test. Binary `move_file` destinations are checked against the source-file SHA-256 after the GUI step.

## Real package test matrix

| Package | Actual archive analysis | Synthetic preflight | Matching mocked workflow coverage | Live Windows/game test |
|---|---|---|---|---|
| AMC Rebel | Pass | Unlimiter + Ed | Ed staging, NFSMS file-copy hashes, Attribulina read-back | Not yet run |
| Bugatti Chiron add-on | Pass | Unlimiter + Binary + NFSMS | Binary move-file hashes plus NFSMS/Attribulina path | Not yet run |
| Bugatti Chiron replacement | Pass | Classic ModLoader | Classic replacement mapping and loader guards | Not yet run |
| Flip Car | Pass | Unlimiter + Binary + NFSMS | Binary + NFSMS guided path; Binary-only path also tested separately | Not yet run |

The real packages were analyzed and preflighted against synthetic game fixtures. The mocked tests exercise each installation mechanism with controlled fake executables; they do not run the supplied archives through the actual Windows Binary, Ed, Attribulina or NFS MW executables.

## Official tool references used

- [Binary releases](https://github.com/SpeedReflect/Binary/releases)
- [NFSMW Unlimiter installation guide](https://github.com/nlgxzef/NFSMWUnlimiter/wiki/Installation)
- [Attribulina and Attribulina Mod Installer](https://github.com/PepegaModTeam/attribulina)
- [NFS-VltEd ModScript format](https://nfs-tools.blogspot.com/2018/02/nfs-vlted-usage-2-modscript-format.html)
- [Ed README / install workflow](https://github.com/NFS404/Ed/blob/master/README.md)
