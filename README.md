# NFSMW Add-on Installer

**Project:** `jenn4fr/nfsmw-addon-installer`  
**Package version:** `0.1.0` (development foundation)  
**Target:** Need for Speed: Most Wanted (2005), PC  
**Current operating environment:** Windows 11 + Python 3.12 + Git Bash  
**Primary purpose:** inspect, validate, plan, and eventually install add-on/replacement cars safely.

This repository is a safety-first development project. Its current capabilities are strongest in **package inspection, NFSMS analysis, read-only database inventory, dry-run validation, install planning, and donor-catalogue extraction**. It is not yet a fully automatic car installer.

> **Safety rule:** Until a separately reviewed installation engine exists, do not treat a generated plan or successful validation as permission to modify the game. The current planner is read-only, and `validate-db` ends with a strict dry-run.

## Start here

- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) — achieved capabilities, verified results, limitations, and pending work.
- [`docs/AI_HANDOFF.md`](docs/AI_HANDOFF.md) — detailed context and instructions for another AI/developer to continue without repeating discovery.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — staged implementation plan and acceptance criteria.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — module responsibilities and data flow.

## Quick start

Requirements:

- Python 3.10 or newer (project tested here with Python 3.12).
- No third-party runtime Python dependencies.
- Optional: Attribulina CLI for database inventory and NFSMS validation.
- Optional: 7-Zip (`7z`/`7zz`) for listing supported compressed archives.

From Git Bash in the repository root:

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

The launchers `start.bat` and `start.sh` provide the interactive entry point. The installed console command is `nfsmw-installer`.

## Current CLI

Run `python -m nfsmw_installer.cli --help` for the authoritative options. Current subcommands:

| Command | Purpose | Writes to game? |
|---|---|---:|
| `inspect` | Scan an extracted package or supported archive; classify payloads, parse NFSMS commands, and write a JSON report | No |
| `validate-db` | Convert NFSMS to AMOD, check against the selected database, and run strict dry-run | No |
| `inventory-db` | Build a read-only class/collection inventory for `ATTRIBUTES.BIN` and `FE_ATTRIB.BIN` | No |
| `plan-install` | Build a proposed file/database operation plan, detect source gaps/conflicts, and flag unresolved mappings | No |
| `build-donor-catalogue` | Parse Attribulina class exports into a read-only vehicle configuration catalogue | No |

### Inspect a package

```bash
python -m nfsmw_installer.cli inspect \
  "/path/to/extracted-addon" \
  --inventory "reports/mw-database-inventory.json" \
  -o "reports/addon-inspection.json"
```

The scanner recognizes common NFSMS/Unlimiter, ModLoader, MWPS, INI, geometry, texture, logo, and resource payloads. It records parsed NFSMS commands, dependency findings, and package layout. Unknown commands are retained for review; they are not executed.

### Validate an NFSMS script

```bash
python -m nfsmw_installer.cli validate-db \
  "/path/to/car_install.nfsms" \
  --database "/path/to/GLOBAL/FE_ATTRIB.BIN" \
  --attribulina "/path/to/attribcli.exe" \
  --output "reports/car-validation.amod"
```

The workflow is conversion → database check → strict dry-run. It stops on failure. A successful result means the script passed these checks; it does **not** mean the mod has been installed. The adapter deliberately does not expose a database-write operation.

### Build the database inventory

```bash
python -m nfsmw_installer.cli inventory-db \
  --attribulina "/path/to/attribcli.exe" \
  --attributes "/path/to/GLOBAL/ATTRIBUTES.BIN" \
  --frontend "/path/to/GLOBAL/FE_ATTRIB.BIN" \
  -o "reports/mw-database-inventory.json"
```

The inventory stores database/class/collection references. It is not a complete typed field-value dump.

### Plan an installation (read-only)

```bash
python -m nfsmw_installer.cli plan-install \
  "/path/to/extracted-addon" \
  --game-root "/path/to/NFS-MW-Unlimiter" \
  -o "reports/addon-install-plan.json"
```

The planner currently understands the supported `Install.nfsms` operations `folder_create`, `file_copy`, and `script`, plus a provisional mapping for `Modloader/ADDONS/CARS_REPLACE` and `Modloader/ADDONS/FRONTEND`. Existing destinations are conflicts. Ed Files resource destinations are explicitly unresolved. **No copy, patch, or database script is applied.**

### Scan databases and build donor catalogue

The standalone scanner exports class lists, headers/type definitions, and complete class exports using Attribulina. Example:

```bash
python tools/scan_attribulina_database.py \
  --inventory reports/mw-database-inventory.json \
  --attribulina "/path/to/attribcli.exe" \
  --output "reports/database-scan-YYYYMMDD_HHMMSS"
```

Build the catalogue from that scan directory:

```bash
python -m nfsmw_installer.cli build-donor-catalogue \
  "reports/database-scan-YYYYMMDD_HHMMSS" \
  -o "reports/donor-catalogue.json"
```

The catalogue keeps `ATTRIBUTES.BIN` and `FE_ATTRIB.BIN` data separate. It extracts collection names and simple scalar fields; complex/nested VLT values are retained as raw text rather than falsely interpreted. This is an extraction foundation only: it does not score donors or generate donor changes.

## Repository layout

```text
nfsmw-addon-installer/
├── nfsmw_installer/
│   ├── cli.py                 # CLI entry points and command orchestration
│   ├── core.py                # package/archive scanner, NFSMS parser, findings
│   ├── attribulina.py         # safe Attribulina subprocess adapter
│   ├── inventory.py           # read-only database class/collection inventory
│   ├── planner.py              # read-only install-plan builder
│   └── donor_catalogue.py     # AMOD export parser and donor catalogue builder
├── tools/
│   └── scan_attribulina_database.py
├── tests/                     # unittest suite
├── reports/                   # local evidence, inventories, scan exports, plans
├── docs/
│   ├── PROJECT_STATUS.md
│   ├── AI_HANDOFF.md
│   ├── ROADMAP.md
│   └── ARCHITECTURE.md
├── pyproject.toml
├── start.bat
└── start.sh
```

## Verified sample project evidence

The supplied project snapshot includes an AMC Rebel add-on analysis and local database scan artifacts. See `reports/` for the detailed outputs. Highlights:

- Database inventory previously recorded two databases, 57 classes in each, and 5,511 node/collection references in the combined inventory report.
- The supplied Attribulina scan contains 114 class exports across `ATTRIBUTES.BIN` and `FE_ATTRIB.BIN`.
- Rebuilding the donor catalogue from those exact exports produced **4,730 parsed collection records**, **860 leaf-keyed vehicle profiles**, and **0 file parse errors**.
- The original scan log records 2,406 Attribulina commands: 406 succeeded and 2,000 failed. The failures are primarily redundant `get` requests against nested collection paths. The updated scanner no longer performs those per-collection reads; complete class exports are used as the catalogue source.
- The AMC Rebel validation artifacts show conversion/check/dry-run work was performed. The actual game database was not changed by the validation workflow.

These figures describe the supplied scan snapshot, not a guarantee about a different game installation or future scan.

## Tests

Run:

```bash
python -m compileall -q nfsmw_installer tools tests
python -m unittest discover -s tests -v
```

**Latest recorded local verification for this documentation/update bundle:** 30 tests passed. Re-run the commands on the target Windows checkout before committing or merging. Tests use temporary fixtures/mocks; they do not prove compatibility with every third-party addon or every game database.

## Safety boundaries and known limitations

- No game database writes are performed by current CLI workflows.
- No game-file copy/install engine exists yet.
- No MWPS/binary patch application exists.
- No rollback/uninstall executor exists; planner only describes backup/rollback intent for conflicts.
- ModLoader destination mapping is provisional and needs confirmation against loader behavior and representative packages.
- Ed Files resource mapping is unresolved.
- NFSMS parsing is partial; arbitrary installer UI commands, includes, conditionals, and custom dialects may not be fully understood.
- The donor catalogue is not yet a donor recommender. It does not infer vehicle geometry, drivetrain, wheelbase, mass suitability, tuning compatibility, or customization compatibility.
- Nested AMOD/VLT structures are retained as raw text; field-level semantic parsing is incomplete.
- No automated online compatibility knowledge base is implemented.

## Contribution/continuation rule

Before implementing a feature, read `docs/AI_HANDOFF.md` and `docs/PROJECT_STATUS.md`. Preserve the read-only default. Add tests for each new parser, mapping, scoring rule, and operation. Never silently convert an unresolved mapping into an assumed install destination. Do not apply changes to the user's live game databases or game files without explicit approval and a separately reviewed execution path.
