# Roadmap

## Stage 1 — Analysis and validation foundation **Complete**
- Package inspection, partial NFSMS parsing, findings and dependency graph.
- Read-only database inventory and Attribulina conversion/check/strict dry-run.
- Read-only installation plan and source/conflict reporting.

## Stage 2 — Donor data foundation **Complete, initial**
- Parse complete AMOD class exports.
- Keep ATTRIBUTES.BIN and FE_ATTRIB.BIN separate.
- Produce leaf-keyed vehicle configuration groups.

## Stage 3 — Donor shortlist **Initial implementation**
- Rank road-car candidates by configuration coverage and scalar-field richness.
- Explain available/missing classes.
- Explicitly disclose that ranking is not physical compatibility.

Acceptance still needed: canonical identity mapping, target profile extraction, measurable physical similarity, and data-derived confidence.

## Stage 4 — Hybrid configuration proposal **Review-only foundation**
- Selective class/field proposal with target identity preservation.
- Exclude model/identity references and avoid copying full donor car.
- Mark unresolved target mappings and validation requirements.

Acceptance still needed: cross-class relationship resolution, field-type validation, external reference analysis, deterministic target-specific AMOD generation, Attribulina check and strict dry-run.

## Stage 5 — File execution and recovery **Experimental foundation**
- Explicit `--execute` gate; dry-run default.
- Copy file operations only; database scripts skipped.
- Backup overwritten files, write journal, rollback copied/replaced files.

Acceptance still needed: verify ModLoader destination mapping, test folder rollback and failure injection, validate paths against symlinks/races, package-specific end-to-end tests, and review backup retention.

## Stage 6 — Package compatibility
- Verify ModLoader layout against loader source/logs and multiple real packages.
- Resolve Ed Files config/resource destinations.
- Add safe MWPS/binary patch handling only after format documentation and validation.
- Add install profile for add-on versus replacement car.

## Stage 7 — Database configuration workflow
- Discover canonical vehicle relationships and typed schema.
- Generate reviewable AMOD from approved field mappings.
- Require backup of both databases, Attribulina check, strict dry-run, explicit confirmation, post-apply verification, and rollback.
- Never make database changes part of the file-only executor.

## Stage 8 — Productization
- Uninstall preview and manifest-based uninstall.
- GUI only if CLI workflow is stable.
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
