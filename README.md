# NFSMW Add-on Installer

**Repository:** https://github.com/jenn4fr/nfsmw-addon-installer  
**Development version:** 0.2.0  
**Target:** Need for Speed: Most Wanted (2005), PC  
**Environment used for development:** Windows 11, Python 3.12, Git Bash

A safety-first toolkit for inspecting, validating, planning, and selectively preparing NFS Most Wanted car add-ons. It now includes an explainable donor shortlist, review-only donor configuration proposals, and an opt-in transactional file-copy executor with a rollback journal.

> **Important:** this is still not a fully verified one-click installer. ModLoader destination mapping remains provisional, Ed Files and MWPS handling remain unresolved, and donor scores measure available configuration coverage—not physical compatibility. Database scripts are never executed by the file installer.

## Start here for maintainers and AI assistants

1. [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) — verified achievements, limitations, pending work.
2. [`docs/AI_HANDOFF.md`](docs/AI_HANDOFF.md) — user decisions, environment, evidence, and continuation rules.
3. [`docs/ROADMAP.md`](docs/ROADMAP.md) — remaining milestones and acceptance criteria.
4. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — module/data flow.
5. Run the test suite before editing.

## Setup

Requirements: Python 3.10+, no third-party runtime dependencies. Attribulina CLI is optional and required only for database inventory/validation/scanning. 7-Zip is optional for archive formats not handled by Python's built-in ZIP support.

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -e .
python -m compileall -q nfsmw_installer tools tests
python -m unittest discover -s tests -v
```

Use `python -m nfsmw_installer.cli --help` for authoritative CLI syntax.

## CLI workflows

| Command | Purpose | Game/database writes |
|---|---|---|
| `inspect` | Scan folder/archive, classify files, parse supported NFSMS commands | No |
| `inventory-db` | Read class/collection inventory from both game databases | No |
| `validate-db` | Convert NFSMS, check AMOD, run strict dry-run | No |
| `plan-install` | Create read-only file/database operation plan | No |
| `build-donor-catalogue` | Parse complete Attribulina class exports | No |
| `donor-assist` | Rank donor candidates and optionally produce review-only configuration proposal | No |
| `apply-file-plan` | Dry-run by default; with `--execute`, copy supported files and create backups/journal | **Yes, only with explicit flag** |
| `rollback-install` | Restore copied/replaced files using install journal | **Yes** |

### 1. Inspect an add-on

```bash
python -m nfsmw_installer.cli inspect \
  "/path/to/extracted-addon" \
  --inventory "reports/mw-database-inventory.json" \
  -o "reports/addon-inspection.json"
```

### 2. Validate an NFSMS script (dry-run only)

```bash
python -m nfsmw_installer.cli validate-db \
  "/path/to/car_install.nfsms" \
  --database "/path/to/GLOBAL/FE_ATTRIB.BIN" \
  --attribulina "/path/to/attribcli.exe" \
  -o "reports/car-validation.amod"
```

This performs conversion → database check → strict dry-run. It does not commit changes to the database.

### 3. Build database inventory and donor catalogue

```bash
python -m nfsmw_installer.cli inventory-db \
  --attribulina "/path/to/attribcli.exe" \
  --attributes "/path/to/GLOBAL/ATTRIBUTES.BIN" \
  --frontend "/path/to/GLOBAL/FE_ATTRIB.BIN" \
  -o reports/mw-database-inventory.json

python tools/scan_attribulina_database.py \
  --inventory reports/mw-database-inventory.json \
  --attribulina "/path/to/attribcli.exe" \
  --output reports/database-scan-current

python -m nfsmw_installer.cli build-donor-catalogue \
  reports/database-scan-current -o reports/donor-catalogue.json
```

The catalogue preserves ATTRIBUTES and FE_ATTRIB as separate data sets. The supplied scan snapshot produced 4,730 parsed collection records, 860 leaf-keyed profile groups, and zero export-file parse errors.

### 4. Donor shortlist and review-only proposal

```bash
python -m nfsmw_installer.cli donor-assist \
  "/path/to/extracted-addon" \
  --catalogue reports/donor-catalogue.json \
  --limit 10 \
  -o reports/donor-assist.json
```

To add a proposal for a selected donor:

```bash
python -m nfsmw_installer.cli donor-assist \
  "/path/to/extracted-addon" \
  --catalogue reports/donor-catalogue.json \
  --donor punto \
  -o reports/donor-assist-punto.json
```

The score is a configuration-coverage/richness score. It is **not** a physical compatibility score. The proposal excludes target identity fields and is explicitly non-executable. Target collection mapping, field type validation, and external reference validation are still required.

### 5. Plan and optionally apply file operations

Create a plan:

```bash
python -m nfsmw_installer.cli plan-install \
  "/path/to/extracted-addon" \
  --game-root "/path/to/NFS-MW-Unlimiter" \
  -o reports/install-plan.json
```

Dry-run the file executor (default):

```bash
python -m nfsmw_installer.cli apply-file-plan reports/install-plan.json
```

Actual copying requires the explicit `--execute` flag:

```bash
python -m nfsmw_installer.cli apply-file-plan reports/install-plan.json --execute
```

Existing destinations cause failure unless `--overwrite` is supplied. Replaced files are copied to a backup directory and a journal is written. Database `script` operations are skipped and are never executed by this command.

Rollback using the path printed by the executor:

```bash
python -m nfsmw_installer.cli rollback-install "/path/to/_nfsmw_installer_backups/install-journal.json"
```

Review every plan before execution. The current ModLoader path mapping is provisional; Ed Files are unresolved. Do not use `--execute` on a live game until mappings have been verified for the package being installed.

## Current implementation

- Package/file classification and partial NFSMS parser.
- Attribulina adapter for conversion, check, and strict dry-run.
- Read-only class/collection inventory and class export scanner.
- Read-only package install planner with source/conflict checks.
- AMOD export parser and donor catalogue builder.
- Donor coverage shortlist with transparent factors and exclusions.
- Review-only Hybrid proposal that filters pvehicle identity fields and preserves target identity domains.
- Explicit opt-in file copy executor with backup journal and rollback for copied/replaced files.

## Known limitations

- Donor rank is based on exported config coverage and scalar-field richness. It does not currently infer physical dimensions, drivetrain, wheelbase, body size, or handling similarity.
- Leaf-keyed profiles are provisional groupings, not canonical vehicle identities.
- Nested AMOD/VLT parsing is intentionally incomplete; nested values remain raw text.
- Proposal output is JSON review data, not executable AMOD/NFSMS.
- ModLoader mapping has not been independently verified against all loader versions/package layouts.
- Ed Files resource mapping and MWPS/binary patching are not implemented.
- The file executor should be treated as experimental until validated against representative packages; it skips database scripts.
- Uninstall management beyond journal-based rollback is not implemented.
- Tests are unit tests with fixtures/mocks; no end-to-end install into the user's live game has been performed.

## Project evidence

The AMC Rebel sample package was inspected and its NFSMS conversion/check/strict dry-run was accepted by Attribulina. A read-only plan identified ModLoader payloads and an unresolved Ed Files mapping. No live database write was performed. See `reports/` and `docs/AI_HANDOFF.md` for the evidence and context.
