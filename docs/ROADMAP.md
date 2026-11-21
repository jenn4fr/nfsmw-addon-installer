# Roadmap and Acceptance Criteria

The project is deliberately staged. A later stage must not bypass an earlier safety or evidence requirement.

## Milestone 0 — Repository and safety foundation

**Status: achieved foundation**

- Python package and CLI.
- Unit tests.
- Read-only scanning and planning defaults.
- Path traversal rejection in planner.
- No database-write adapter.

Acceptance: compile succeeds; all tests pass; no command modifies game files or databases.

## Milestone 1 — Reliable package inspection

**Status: partial / ongoing**

- Improve NFSMS grammar and command coverage.
- Include resolution and dependency ordering.
- Detect malformed arguments, missing source files, unsupported operations, and unsafe paths.
- Add fixtures for real addon packages, including AMC Rebel.

Acceptance: each recognized command has a parser test; unknown commands remain visible; findings explain uncertainty rather than inventing validity.

## Milestone 2 — Database export and normalized inventory

**Status: basic inventory/export achieved; semantic normalization pending**

- Keep Attribulina scan read-only.
- Parse complete class exports and field headers/types.
- Preserve database, class, full collection path, field type, and raw value.
- Validate references between classes/collections.
- Avoid redundant individual nested `get` calls unless a specific supported path is proven.

Acceptance: scan output has deterministic counts, parse diagnostics, and provenance; no game DB changes; parser fixtures cover real export constructs.

## Milestone 3 — Donor catalogue and vehicle profile graph

**Status: first catalogue implementation achieved; profile semantics pending**

- Normalize vehicle identity and configuration relationships.
- Separate ATTRIBUTES and FE_ATTRIB.
- Distinguish identity/registration from performance/customization configuration.
- Model missing/unknown fields explicitly.

Acceptance: every relationship includes source evidence; no leaf-name-only assumption is used as canonical identity.

## Milestone 4 — Donor recommendation engine

**Status: pending**

- Compare candidate donors to target addon.
- Rank top 10 with transparent factor scores.
- Account for body size, drivetrain, mass, wheelbase, tire setup, performance tier, customization support, frontend structure, and engine setup where data supports it.
- Provide confidence and missing-data penalties.

Acceptance: deterministic scores; synthetic tests; sample report explains why candidates rank; no unsupported physical characteristics are invented.

## Milestone 5 — Selective donor proposal generator

**Status: pending**

- Implement Option B / Hybrid.
- Preserve target identity, registration, geometry, textures, unique names/IDs, and collection identity.
- Borrow only compatible selected configuration entries.
- Generate proposal artifacts and explanations.
- Validate with Attribulina conversion/check/strict dry-run.

Acceptance: generated proposal never wholesale-copies donor identity; every change has source/destination provenance; strict dry-run passes on disposable copies/appropriate test databases; still no automatic apply.

## Milestone 6 — File staging and installation

**Status: pending; requires user approval before write capability**

- Verify ModLoader mapping.
- Resolve Ed Files mapping.
- Stage package files under a controlled temporary root.
- Check path traversal, conflicts, hashes, and required files.
- Back up overwritten files; create rollback/uninstall manifest.
- Apply only explicitly supported formats.

Acceptance: tests use temporary game-root fixtures; rollback restores byte-identical prior state; dry-run and write modes are distinct; explicit confirmation gates writes.

## Milestone 7 — Database install/uninstall

**Status: pending; highest risk**

- Only after validated proposals and disposable-copy tests.
- Backup both relevant databases.
- Apply transactionally if Attribulina supports it; otherwise document limitations and require manual recovery plan.
- Verify post-install state and generate uninstall manifest.

Acceptance: crash/failure tests; backup verification; rollback demonstrated on disposable copies; no live apply without explicit approval.

## Milestone 8 — Release and maintenance

**Status: pending**

- CI on supported Python versions.
- Versioned releases and changelog.
- User docs and known-mod compatibility matrix.
- Regression fixtures for supported package layouts.
