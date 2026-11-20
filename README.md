# NFSMW Add-on Installer & Validator

Version 0.1.0 — discovery, analysis, and database-validation foundation for Need for Speed: Most Wanted (2005) car mods.

## Quick start

- Windows: double-click `start.bat`.
- Git Bash/Linux/macOS: run `./start.sh`.
- Both launchers provide a menu to inspect a mod folder/ZIP, run tests, open reports, or view capabilities.
- You can also drag a folder/archive onto `start.bat`, or pass a path to `./start.sh`.

The inspector asks for a mod path, runs the analysis command internally, and writes a JSON report under `reports/`.

## What it does now

### Mod discovery and inspection

- Scans extracted mod folders and ZIP archives (RAR/7z archive listing is optional when 7-Zip is installed).
- Classifies common payloads: Unlimiter/NFSMS, ModLoader replacement, MWPS, INI, model/texture, logo/resource files.
- Parses NFSMS commands and records line numbers.
- Optionally compares donor/target nodes and collection references against a user-supplied JSON inventory.
- Writes a machine-readable JSON report.

### Attribulina database validation

The optional `validate-db` command integrates with Attribulina to validate an NFSMS installation script against the user's actual Need for Speed: Most Wanted database.

It performs three stages:

1. Converts the NFSMS script into an AMOD script using the VLTEd-compatible conversion mode.
2. Checks that the generated AMOD script is readable and compatible with the selected database.
3. Runs a strict dry-run to report the changes Attribulina would make.

Example:

```bash
python -m nfsmw_installer.cli validate-db \
  "/path/to/car_install.nfsms" \
  --database "/path/to/GLOBAL/FE_ATTRIB.BIN" \
  --attribulina "/path/to/attribcli.exe" \
  --output "reports/car-validation.amod"
```

The database argument should point to `FE_ATTRIB.BIN`. Attribulina automatically handles the associated `ATTRIBUTES.BIN` database when available.

The command reports conversion, database-check, and dry-run results separately. It stops if a stage fails.

**Important:** Successful validation does not install the car. The command does not commit database changes or copy car files into the game.

## Requirements

- Python 3.10+
- No third-party Python packages required.
- Optional: 7-Zip (`7z` or `7zz`) on PATH for archive listing.
- Optional: Attribulina CLI for NFSMS-to-AMOD conversion and database validation.

Extract RAR/7z files manually for full text inspection.

## Setup (if not already installed)

```bash
python -m venv .venv
# Git Bash
source .venv/Scripts/activate
python -m pip install -e .
```

## Optional VLT inventory

Create a JSON file with the exact nodes/collections you have verified in your own VltEd database. Names are case-sensitive in this first version; use the exact internal names. Example:

```json
{
  "nodes": ["brakes/punto", "brakes/punto_top", "pvehicle/rebel"],
  "collections": ["rebel", "rebel_top", "corvette_z06_v2"],
  "fields": []
}
```

Then run:

```bash
nfsmw-installer inspect "/path/to/mod" --inventory ./my-vlt-inventory.json -o reports/report.json
```

The inventory is user-provided evidence, not an automatic VLT parser. A warning means the tool cannot confirm an item; it does not necessarily mean the script is invalid. Some nodes are created by earlier `copy_node` commands.

## Current safety boundaries

- No automatic VLT database installation or commit.
- No automatic MWPS/binary patch application.
- No automatic game-file copying yet.
- No automatic rollback or uninstall workflow yet.
- `validate-db` performs conversion, checking, and strict dry-run only.
- The Attribulina adapter does not expose an actual database-write operation.
- No claim that every author's custom installer format is understood.
- Unknown commands are retained in the report for manual review, not executed.

## Planned stages

1. Improve the NFSMS parser and dependency graph, including node creation order and include resolution.
2. Add more comprehensive validation of fields, collections, resources, and dependencies against the actual game database.
3. Build a VLT inventory exporter/reader based on a verified format/API rather than guessed binary offsets.
4. Add an explicit file-staging plan with path validation, conflict detection, backups, and rollback.
5. Add separate adapters for ModLoader MWPS and supported binary patch formats.
6. Add controlled installation and post-install verification, with rollback and uninstall support.
7. Consider optional VltEd automation only after repeatable tests against disposable database copies.
