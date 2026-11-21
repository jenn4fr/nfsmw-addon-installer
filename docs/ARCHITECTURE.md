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
             donor_catalogue.parse_amod_export
                    |  parent paths + top-level fields
                    v
             pvehicle/racers canonical vehicle anchors
                    |
                    +--> explicit class/collection refs from pvehicle fields
                    |        |
                    |        v
                    |    referenced subsystem records
                    |
                    +--> ecar exact-leaf association (lower confidence)
                    |
                    v
             donor-catalogue.json + relationship audit
                    |
                    v
             donor_matcher.rank_donors
                    |-- coverage/richness shortlist by default
                    |-- optional shared numeric feature similarity
                    v
             donor-assist.json / review-only Hybrid proposal

Addon folder + optional game root
        |
        v
planner.py
        |
        v
install-plan.json (operations/conflicts/unresolved; no execution)
        |
        v
apply_plan.apply_file_plan (dry-run unless explicit execute)
        |
        v
backup + journal -> rollback_journal
```

## Vehicle relationship model (v0.3.0)

- `pvehicle/racers` records are the canonical starting point for playable road-car candidates in the inspected MW database export.
- A pvehicle record contains explicit references such as `engine = [engine/rx7, engine/rx7_top]`, `brakes = [...]`, `tires = [...]`, and related subsystem collections. The catalogue resolves these against the named class exports and retains each relationship's source field.
- `ecar` body/handling data is joined by matching vehicle leaf because the inspected exports do not establish a direct pvehicle reference. This relationship is marked `exact-vehicle-leaf`, not treated as equally authoritative.
- `MASS`, upgrade availability, `HandlingRating`, `TENSOR_SCALE`, and selected ecar scalar fields are exported numeric descriptors. Shared numeric comparison is a heuristic, not a simulation of physical compatibility.
- ATTRIBUTES.BIN and FE_ATTRIB.BIN remain separate catalogues/profiles. Never merge them solely because their collection leaves match.

## Important data distinctions

- A **class** contains collections; the parent path is meaningful and must be preserved.
- A **pvehicle** collection is a playable-vehicle configuration anchor only when it is under `pvehicle/racers` in the inspected schema.
- A collection reference is a class/path pointer. Resolve it against the exact class export; do not assume same-name collections are interchangeable.
- A leaf-only ecar match is weaker than an explicit VLT reference and must remain labeled.
- Complex AMOD values remain raw text unless a dedicated parser validates their structure and type.

## Safety architecture

- Inspectors read package files and emit reports.
- Inventory/scanner read database metadata and exports.
- Attribulina adapter performs conversion/check/dry-run only.
- Planner emits operations but never runs them.
- Donor catalogue/matcher emit read-only reports and non-executable proposals.
- File executor is separate, dry-run by default, file-only, and journaled. Database scripts are skipped.

Future database execution requires separate design: field-type validation, dependency resolution, database backup, staged apply, post-apply verification, rollback and explicit user approval. Do not add writes as side effects of catalogue or donor commands.
