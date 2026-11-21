# External tool capabilities and automation boundaries

Last checked: 2026-11-21

This document distinguishes what the official tool documentation supports from what this installer currently automates.

## Binary (MaxHwoy / SpeedReflect)

- Binary edits Black Box NFS binary resources and supports importing Endscript `.end` files.
- Its published README describes a graphical UI, Endscript support, collection editing, import/export and backup features. The README does not document a stable command-line install interface for arbitrary `.end` packages.
- Therefore this installer launches Binary and guides the user to select the exact `.end`, game folder, install/uninstall branch and package-specific options. It then verifies declared `move_file` payloads by SHA-256 and checks declared target files changed.
- Never substitute Binarius for Binary.

Official references:
- https://github.com/SpeedReflect/Binary
- https://github.com/SpeedReflect/Binary/releases

## Attribulina / Attribulina Mod Installer / attribcli

- Attribulina supports NFSMS script execution and its own `.amod` format.
- `AttribulinaModInstaller.exe` is explicitly documented as the dedicated GUI installer for `.nfsms` and `.amod`, including script options and install/uninstall selection.
- `attribcli.exe` documents console commands such as `apply GLOBAL mod.amod`, `export`, `get` and `diff`. The published script documentation describes `.amod` as its database-change format. It does not establish that the CLI applies arbitrary `.nfsms` scripts.
- Accordingly, this project uses Attribulina Mod Installer for NFSMS/AMOD installation and uses `attribcli export` for independent database read-back. Do not route NFSMS to `attribcli apply` unless a future tool version explicitly documents and passes a real test for it.
- Attribulina's installed-mod rollback relies on trace files under `GLOBAL`; preserve them. This project's rollback snapshots the full `GLOBAL` tree.

Official references:
- https://github.com/PepegaModTeam/attribulina
- https://github.com/PepegaModTeam/attribulina/blob/master/doc/scripts.md

## Ed

- Ed supports NFS MW (2005) add-on-car preparation and requires NFSMW Unlimiter for add-on cars.
- Its published workflow is GUI-based: open the game folder, browse/refresh the config folder if necessary, apply the config, and confirm its success dialog. The required VLT entries are a separate step.
- This project stages Ed config/resources into the Ed tool directory, launches Ed, asks the user to apply, and only proceeds to the VLT stage after the user confirms success.

Official reference:
- https://github.com/NFS404/Ed/blob/master/README.md

## NFSMW-ML

- NFSMW-ML is a runtime replacement loader for NFS MW US v1.3. It requires Ultimate ASI Loader (`dinput8.dll`) and `scripts/NFSMW-ML.asi`.
- Each mod belongs in its own directory under `modloader/`; it is loaded at runtime without patching original game files.
- The installer supports the documented per-mod folder layout and only maps recognized legacy layouts. MWPS is not translated into NFSMW-ML semantics.

Official reference:
- https://github.com/TsyVM/nfsmw-modloader

## NFSMW Unlimiter

- Unlimiter is an ASI script mod for added cars; its installation guide requires the supported v1.3 `speed.exe` and describes Binary installation of its base data.
- The guide warns against mixing Classic ModLoader files (`d3d9.dll`, `modloader.ini`) with Unlimiter.
- This project checks the target folder for loader indicators and keeps Unlimiter, NFSMW-ML and Classic ModLoader profiles separate.

Official references:
- https://github.com/nlgxzef/NFSMWUnlimiter
- https://github.com/nlgxzef/NFSMWUnlimiter/wiki/Installation

## What “one command” means today

The project provides one command per archive/folder. It performs package detection, profile selection, preflight, backup, file staging, tool launch, post-stage checks, database read-back and journaling. For Binary, Ed and NFSMS/AMOD installation, native tools still require the documented GUI interaction and user confirmation. This is intentional: the project does not use brittle screen-coordinate automation or pretend that launching a GUI means its operation succeeded.

A future unattended mode would need stable documented command-line interfaces for those operations, or tested vendor-supported automation hooks. The final in-game car appearance and drive test also remains a human acceptance step.
