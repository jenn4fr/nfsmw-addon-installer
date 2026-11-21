# Roadmap — v0.3.0 baseline

## Stage 1 — Analysis and validation foundation **Implemented foundation**
- Package inspection, partial NFSMS parsing, findings and dependency graph.
- Read-only database inventory and Attribulina conversion/check/strict dry-run.
- Read-only installation plan and source/conflict reporting.

## Stage 2 — Vehicle relationship discovery **Initial implementation**
- Canonical vehicle anchors from `pvehicle/racers`.
- Explicit subsystem references resolved from pvehicle collection fields.
- Relationship audit with resolved/unresolved status.
- ecar handling/body data joined by exact vehicle leaf, with lower-confidence labeling.
- Separate profiles for ATTRIBUTES.BIN and FE_ATTRIB.BIN.

Remaining: validate all relationships against type headers and additional database snapshots; determine reliable ecar/identity/frontend references.

## Stage 3 — Vehicle feature extraction **Partial**
- Extract mass, upgrade availability, handling-rating bounds, tensor scale, selected ecar ride height/camber/steering/wheel fields.

Remaining: parse complex vectors/arrays safely; identify verified drivetrain, wheelbase, body dimensions, tire dimensions and other useful features if the game data actually exposes them. Do not infer missing values.

## Stage 4 — Donor matching **Initial explainable engine**
- Top-N shortlist by configuration coverage and scalar-field richness.
- Optional numeric feature similarity against a supplied local target profile.
- Per-candidate available/missing classes and reasons.

Remaining: confidence-calibrated per-factor scoring, meaningful missing-data penalties, target hints from add-on NFSMS/package data, and validation against known donor choices. Scores are not physical-fitment guarantees.

## Stage 5 — Hybrid configuration proposal **Review-only foundation**
- Selective class/field proposal with target identity preservation.
- Exclude model/identity references and avoid copying a full donor car.

Remaining: typed schema validation, target collection mapping, dependency/reference resolution, deterministic AMOD generation and Attribulina check/strict dry-run. Do not generate executable output until these are proven.

## Stage 6 — File execution and recovery **Experimental foundation**
- Explicit `--execute` gate; dry-run default.
- File copies only; database scripts skipped.
- Backup overwritten files, write journal, rollback copied/replaced files.

Remaining: independently verify ModLoader destination mapping, resolve Ed Files, test folder rollback/failure injection/symlink edge cases, and run representative package tests in a temporary game copy.

## Stage 7 — Package compatibility **Pending**
- Verify ModLoader layout against loader behavior and multiple real packages.
- Resolve Ed Files config/resource destinations.
- Add safe MWPS/binary patch handling only after format documentation and validation.
- Support add-on versus replacement profiles.

## Stage 8 — Database configuration workflow **Pending**
- Generate reviewable AMOD from approved target-specific field mappings.
- Require backups of both databases, Attribulina check, strict dry-run, explicit confirmation, post-apply verification and rollback.
- Keep database changes separate from file installation.

## Stage 9 — Productization **Pending**
- Manifest-based uninstall preview and execution.
- CI on supported Python versions and Windows.
- End-to-end tests against temporary copies and multiple real add-on packages.
- Release documentation and migration notes.

## Non-negotiable acceptance criteria
- No guessed target collection names or field types.
- No blind donor collection copying.
- Identity, model, geometry, textures and frontend registration remain target-owned.
- No silent overwrite.
- Dry-run by default; explicit user approval for writes.
- All operations journaled and recoverable.
- Tests pass and package-specific plan is reviewed before installation.


## v0.4.0 completed — Target-aware proposal foundation

- Parse target collection names from explicit Attribulina AMOD `create` directives.
- Map selected donor base/base-variant and top-upgrade scalar proposals to target collection names.
- Exclude global defaults and unmapped classes from target-aware proposals.
- Keep proposals review-only; typed validation and candidate AMOD generation are the next gates.
