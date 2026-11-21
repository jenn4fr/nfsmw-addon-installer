# Architecture overview — v0.6.1

## Single-command flow

```text
ZIP / RAR / 7z / extracted folder
              |
              v
archive.py: safe list + extraction + path validation
              |
              v
package_analysis.py
  - Binary VERSN1/VERSN2
  - NFSMS include graph + UI options + file_copy
  - AMOD include graph, collection IDs and safe direct CARS/UnlimiterData payloads
  - MWPS
  - Ed Files / UnlimiterData / save-patcher
  - alternative install profiles
              |
              v
workflow.py: build_workflow_plan
  - inspect target loader (Unlimiter / NFSMW-ML / Classic ModLoader)
  - verify speed.exe, Binary inputs and VLT databases
  - map only known package formats
              |
              v
DRY RUN plan (default)
              |
              | explicit --execute
              v
backup + run journal
              |
              +--> Binary GUI User Mode (.end packages)
              |
              +--> stage Ed Config/Resources -> Ed GUI -> user confirms
              |
              +--> Attribulina Mod Installer (.nfsms/.amod)
              |       |
              |       +--> attribcli export pvehicle/<car-id> read-back
              |
              +--> Classic ModLoader / NFSMW-ML safe file copy
              |
              v
file hashes + database evidence + in-game user confirmation
              |
              v
PASS / PARTIAL / FAILED + rollback journal
```

## Modules

- `archive.py`: safe ZIP extraction and 7-Zip list/extract adapter for RAR/7z.
- `package_analysis.py`: package structure analysis. It does not write to the game.
- `workflow.py`: loader preflight, plan construction, backup, GUI orchestration, read-back, manual final test and rollback.
- `core.py`: legacy package scanning and NFSMS parsing used by existing inspection/validation commands.
- `attribulina.py`: read-only Attribulina conversion/check/dry-run adapter used by the legacy validation workflow.
- `planner.py`: read-only installation planner for existing file/database plans.
- `apply_plan.py`: separate file-only executor; dry-run unless explicitly requested.
- `inventory.py`, `database_scan.py`, `donor_catalogue.py`, `donor_matcher.py`: read-only database intelligence and donor shortlist/proposal features.

## Loader profiles

- `unlimiter_addon`: requires `scripts/NFSMWUnlimiter.asi`; Binary, Ed and NFSMS/AMOD stages are invoked only when present.
- `nfsmw_modular_loader`: requires `scripts/NFSMW-ML.asi` and `dinput8.dll`; installs a per-mod folder under `modloader`.
- `classic_modloader_replacement`: requires `d3d9.dll` and `modloader.ini`; maps the selected replacement payload into `ADDONS`. MWPS is not translated to NFSMW-ML.

The user's audited Unlimiter game contains both Unlimiter and NFSMW-ML, plus `dinput8.dll`. The separate original game remains Classic ModLoader. The installer checks the actual target directory rather than assuming a single global loader configuration.

## Native tool hand-offs

- **Binary:** VERSN1 manifests and VERSN2 command targets are inspected; Binary performs the actual BUN/LZC/language/data modifications. The user opens the exact `.end` in User Mode and confirms the Install option.
- **Attribulina Mod Installer:** handles NFSMS/AMOD and its own script UI options. NFSMS and AMOD include graphs are analyzed separately; uninstall-only entry points are excluded from install selection, and the installer refuses to guess when both install formats are present. The installer launches the selected entrypoint. `attribcli export GLOBAL pvehicle/<car-id> --children -o <file>` provides independent existence/read-back evidence.
- **Ed:** package `Ed Files/Config/NFSMW` and `Ed Files/Resources/NFSMW/...` are staged into the Ed tool folder. Ed applies its configuration to the game; the NFSMS VLT script runs afterwards.
- **Classic ModLoader/NFSMW-ML:** only known file layouts are copied; MWPS remains Classic ModLoader-specific.

## Transaction and rollback

- A unique run directory contains backups and `install-run.json`, including package/game hashes, tool paths, car IDs and stage results.
- Binary-declared target files, NFSMS model destinations and Ed-modified game files are backed up before use.
- The full `GLOBAL` directory is snapshotted immediately before Attribulina, capturing its database changes and installed-mod trace files.
- Rollback restores the pre-Attribulina GLOBAL tree and then the earlier file snapshots. It refuses if the GLOBAL tree hash changed after the install, protecting later unrelated mod changes.
- Ed config/resource files and direct loader payloads are also backed up before overwrite.

## Verification levels

1. **Package validity:** archive paths safe, referenced scripts resolve, required manifests parse.
2. **Preflight:** target loader and game files exist.
3. **Tool completion:** user confirms Binary/Ed/Attribulina success.
4. **File verification:** expected model/data files exist; declared targets changed.
5. **Database read-back:** for an Unlimiter add-on, `attribcli.exe` is required and every detected `pvehicle/<car-id>` must export successfully.
6. **In-game verification:** user confirms car appears and drives. Only all required stages plus this final confirmation can yield `PASS`.

The current read-back checks collection existence, not every field in the VLT records. That stronger expected-value verification remains future work.
