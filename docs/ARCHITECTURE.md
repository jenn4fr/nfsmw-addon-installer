# Architecture Overview

## Current data flow

```text
Addon folder / archive
        |
        v
core.scan_folder / archive reader
        |
        v
file classification + NFSMS parsing + dependency findings
        |
        v
JSON inspection report

NFSMS script + selected FE_ATTRIB.BIN + Attribulina
        |
        v
convert -> check -> strict dry-run
        |
        v
AMOD/report artifacts (no DB commit)

ATTRIBUTES.BIN + FE_ATTRIB.BIN + Attribulina
        |
        +--> inventory.py: class/collection inventory
        |
        +--> tools/scan_attribulina_database.py: list/header/export
                    |
                    v
             complete-export.amod files
                    |
                    v
             donor_catalogue.py
                    |
                    v
             donor-catalogue.json (read-only, preliminary)

Addon folder + optional game root
        |
        v
planner.py
        |
        v
install-plan.json (operations/conflicts/unresolved; no execution)
```

## Important data distinctions

- `ATTRIBUTES.BIN` and `FE_ATTRIB.BIN` are separate source databases and remain separate in the catalogue.
- A **class** contains collections; a collection path may be nested. A leaf collection name is not guaranteed unique.
- A `pvehicle` collection, an `ecar` collection, and a frontend registration may refer to related concepts but must not be treated as interchangeable without parsing actual references.
- Complete AMOD class exports are the primary data source for the current donor catalogue. The original per-collection `get` loop generated many `no collection` errors for nested paths.
- Simple scalar values are typed by the preliminary parser. Complex values remain raw text and must not be used in numerical scoring until parsed and validated.

## Safety architecture

The current code separates analysis from execution:

- Inspectors read package files and emit reports.
- Inventory/scanner read database metadata and exports.
- Attribulina adapter performs conversion/check/dry-run only.
- Planner emits operations but never runs them.
- Donor catalogue emits data but never creates/apply database changes.

Future execution should be a separate layer with explicit approvals, staged writes, backups, hashes, rollback, and tests. Do not add write behavior as a side effect of an existing read-only command.

## Added in version 0.2.0

```text
Donor catalogue JSON
        |
        v
 donor_matcher.rank_donors
        |                         donor_matcher.build_configuration_proposal
        v                                         |
 explainable coverage shortlist                  v
                                        review-only Hybrid proposal
                                        (not executable AMOD/NFSMS)

Reviewed install-plan JSON
        |
        v
 apply_plan.apply_file_plan
        |-- dry-run unless explicit execute=True
        |-- file copies only; database scripts skipped
        |-- backup existing files; write install journal
        v
 rollback_journal(install-journal.json)
```

The donor score is based on exported class coverage and scalar-field richness, not physical compatibility. The current profile key is `database:leaf`; canonical vehicle relationship discovery is still required. The file executor is experimental and must not be treated as a universal installer until ModLoader/Ed Files mappings are verified.
