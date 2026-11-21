# Changelog

## 0.4.0 — Target-aware configuration intelligence

- Added parsing of explicit Attribulina `create class/target from class/source` directives to discover target collection names from a converted add-on AMOD.
- Added `donor-assist --amod` to attach those grounded target mappings to a review-only Hybrid proposal.
- Restricted mapped proposals to the selected donor's base/base-variant and `_top` records; global defaults and unrelated shared records are excluded.
- Proposals now identify exact target collection paths for mapped performance classes while leaving unmapped classes out of the mapped proposal.
- Generated the AMC Rebel review report using the supplied v0.3.0 donor catalogue and validated Rebel AMOD.
- No executable AMOD/NFSMS is generated; no Attribulina apply, database write, or game installation is performed.
- Added target mapping/parser tests. 44/44 tests pass.


## 0.3.0 — Vehicle intelligence foundation

- Replaced broad leaf-only grouping with `pvehicle/racers`-anchored vehicle profiles.
- Preserved collection parent paths and parsed explicit VLT collection references from pvehicle fields.
- Joined referenced engine, induction, transmission, brakes, chassis, tires and other subsystem collections by actual class/collection reference, including upgrade variants.
- Joined ecar handling/body setup by exact vehicle leaf and records that relationship method explicitly.
- Extracted numeric descriptors including mass, upgrade availability, handling rating bounds, tensor scale, ride height, camber and wheel spoke count.
- Added optional target-profile numeric similarity to donor ranking, with explicit warnings and no physical-fitment claims.
- Added relationship/reference audit details and expanded tests.
- Read-only only; no game database writes or executable donor AMOD generation.

## 0.2.0 — 2026-11-21
- Added explainable donor shortlist based on configuration class coverage and scalar-field richness.
- Added review-only Hybrid donor configuration proposal with conservative pvehicle field allowlist and identity preservation.
- Added explicit opt-in file-plan executor, overwrite backups, install journal and rollback.
- Added donor matcher and file executor tests.
- Updated README, project status, roadmap, architecture and AI handoff.
- Safety: donor proposal remains non-executable; database scripts are skipped by file executor.
- Hardened rollback journal path validation and added a test rejecting destinations outside the selected game root.
- Donor proposals now include only simple typed scalar values, record omitted fields, and exclude path-like/nested/identity references.

## 0.1.0 — development foundation
- Package inspection, NFSMS parser, database inventory, Attribulina dry-run validation, read-only install planner and donor catalogue extraction.
