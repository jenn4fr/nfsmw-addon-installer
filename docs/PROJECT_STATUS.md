# Project Status — NFSMW Add-on Installer

**Snapshot date:** 2026-11-21  
**Package version:** 0.1.0  
**Status:** functional analysis/validation/planning foundation; not a production installer.

## Executive summary

The repository can inspect addon packages, parse a supported subset of NFSMS commands, validate NFSMS scripts through Attribulina conversion/check/strict dry-run, inventory database class/collection references, produce a read-only install plan, and build a read-only catalogue from Attribulina class exports.

The next major milestone is the donor configuration assistant. Only its data extraction foundation exists. Donor recommendation, compatibility scoring, selective donor configuration generation, and end-to-end installation are still pending.

## Achieved and present in source

| Area | Current state | Evidence / caveat |
|---|---|---|
| Package inspection | Implemented | `core.py`; folder/archive scanning, file classification, JSON report |
| NFSMS parsing | Partial implementation | Commands and line numbers are recorded; not a full interpreter |
| Dependency findings | Implemented foundation | Tracks selected collection/node creation-order cases; not exhaustive |
| Optional inventory comparison | Implemented | Uses supplied JSON inventory; does not independently decode VLT binary |
| Attribulina adapter | Implemented | `attribulina.py`; conversion, check, strict dry-run; no actual apply method |
| Database inventory | Implemented | `inventory.py`; class and collection reference inventory, read-only |
| Install planner | Implemented, read-only | `planner.py`; supported NFSMS file/folder/script operations, path traversal rejection, conflict reporting |
| ModLoader plan mapping | Provisional | `CARS_REPLACE` → per-mod `CARS`; `FRONTEND` → per-mod `FRONTEND`; verify before execution |
| Ed Files | Not mapped | Planner explicitly marks as unresolved |
| Attribulina database scanner | Implemented script | Exports info, mods, class list, header types, and complete class exports |
| Donor catalogue parser | Implemented foundation | `donor_catalogue.py`; extracts collection blocks/simple scalars; complex values retained as raw text |
| Donor recommendation | Pending | No top-10 ranking or similarity model |
| Donor proposal generation | Pending | No selective target-specific NFSMS/AMOD proposal generator |
| Installer execution | Pending | No game file copy, MWPS patch, database apply, rollback, or uninstall executor |

## Verified data from the supplied project archive

- Inventory report: 2 databases (`ATTRIBUTES.BIN`, `FE_ATTRIB.BIN`), 57 class listings per database, 5,511 combined node references and 5,511 collection references.
- Attribulina scan: 114 class exports.
- Re-parsing the supplied complete-export files: 4,730 collection records, 860 profiles keyed by database + collection leaf, 0 parse errors.
- Original scan log: 2,406 commands; 406 successful; 2,000 failed; 0 timeouts. Failed requests predominantly came from attempting `get` on nested paths that Attribulina reported as `no collection`.
- The updated scanner uses complete class exports as the source and avoids issuing an individual `get` for every vehicle collection.
- Current combined test suite: 30 tests pass in this environment (`python -m unittest discover -s tests -v`).

The profile count is a technical grouping key, not a claim that 860 distinct real-world cars have been identified. Same leaf names can group records from different classes within one database.

## Known sample: AMC Rebel package

The supplied project artifacts include reports for `1970 AMC Rebel The Machine`:

- `Install.nfsms` and `rebel_install.nfsms` were inspected.
- Package contains ModLoader replacement payload under `Addon/Modloader/ADDONS/CARS_REPLACE/PUNTO/` and a frontend manufacturer resource.
- Ed Files includes a `REBEL.ini` configuration; its resource count was previously corrected by the user from 1 to 2, with a backup retained in the user's source package.
- Reports include inspection, dependency analysis, Attribulina conversion/check/dry-run, and a read-only install plan.
- Prior plan analysis identified Ed Files destination mapping as unresolved. Do not infer that the package is fully installable from the plan.

## Current safety contract

1. `inspect`, `inventory-db`, `plan-install`, and `build-donor-catalogue` are analysis/read-only operations.
2. `validate-db` may write generated AMOD/report files in the project, but it performs a strict dry-run against the game database and does not commit changes.
3. No game database or game installation file should be modified by the current tool.
4. Do not add an actual database apply or game copy feature without explicit user approval, backups, path validation, rollback, and dedicated tests.

## Immediate next tasks

1. Inspect and harden AMOD parser behavior for nested values, arrays, escaped strings, and duplicate fields; add fixtures from real exports.
2. Extract class/field metadata and cross-class references into a normalized vehicle profile model.
3. Distinguish vehicle identity records from reusable tuning/configuration records.
4. Add a donor candidate index and transparent compatibility scoring with evidence and missing-data penalties.
5. Implement the user's selected **Option B / Hybrid** policy: preserve target identity/registration; borrow only selected compatible configuration entries; never wholesale-copy a donor.
6. Generate proposed changes only, then validate generated scripts with Attribulina check + strict dry-run.
7. Continue to leave execution disabled until the proposal/validation process is reliable and explicit approval is obtained.

See `AI_HANDOFF.md` for detailed instructions and `ROADMAP.md` for milestone acceptance criteria.
