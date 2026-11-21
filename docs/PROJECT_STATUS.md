# Project Status — 2026-11-21

**Version:** 0.3.0 development snapshot  
**Overall:** stronger vehicle relationship and donor-data foundation; installer execution remains experimental and is not a verified universal one-click installer.

## Verified in this snapshot

- Package inspection, file classification, partial NFSMS parsing and dependency findings.
- Attribulina conversion/check/strict dry-run adapter; no live database apply operation is exposed by the validation workflow.
- Read-only inventory and complete class exports for ATTRIBUTES.BIN and FE_ATTRIB.BIN.
- Read-only install planner with source checks, destination conflicts, provisional ModLoader mapping and unresolved Ed Files mapping.
- AMOD parser now retains collection parent paths.
- Donor profiles are anchored on `pvehicle/racers` rather than merging arbitrary same-leaf records across all classes.
- Subsystem collections are discovered from explicit class/collection references in each pvehicle record. The relationship audit records field, class, collection and whether the target collection was found.
- ecar body/handling setup is joined by exact vehicle leaf and explicitly labeled as that weaker relationship method.
- Numeric descriptors include mass, upgrade availability counts, handling-rating bounds, tensor scale, ride height, camber and wheel spoke count where present.
- Optional target-profile matching compares shared numeric features; reports explain matched fields and warn that this is not a physical fitment test.
- Hybrid donor configuration output remains review-only JSON and never emits executable AMOD/NFSMS.
- File-only plan executor remains dry-run by default; explicit `--execute` is required. It backs up replaced files, writes a journal, skips database scripts, and supports journal rollback.

## Supplied database export validation

Source: `reports/database-scan-20261120_212135/` from the user-provided project/report bundle.

- 4,730 collection records parsed.
- 86 racer-anchored vehicle profiles: 43 from ATTRIBUTES.BIN and 43 from FE_ATTRIB.BIN.
- 1,272 relationship edges emitted, including explicit pvehicle subsystem references and ecar leaf associations; 1,190 recognized pvehicle references were audited (1,188 resolved, 2 unresolved).
- 0 export-file parse/read errors.
- 2 unresolved references among the recognized vehicle-class references in the generated profile audit; these remain visible rather than silently guessed.
- AMC Rebel is not a stock profile in the supplied database export, so its donor shortlist currently uses configuration completeness unless the user supplies a known baseline vehicle profile.

These figures describe the supplied snapshot, not every possible game database or modded installation.

## Current CLI

1. `inspect`
2. `validate-db`
3. `inventory-db`
4. `plan-install`
5. `build-donor-catalogue`
6. `donor-assist`
7. `apply-file-plan`
8. `rollback-install`

`donor-assist` accepts optional `--target-profile` to compare the target against a known local profile. Without it, ranking is based on coverage/richness.

## Test status

**41 tests passed** in the v0.3.0 source snapshot. Run:

```bash
python -m compileall -q nfsmw_installer tools tests
python -m unittest discover -s tests -v
```

Tests include synthetic cross-class references, racer-only anchoring, numeric target-profile similarity, identity-preserving proposals, planner path safety, dry-run/apply/rollback behavior, Attribulina adapter behavior and existing parser/inventory/dependency coverage. They are not an end-to-end live-game installation test.

## Status by capability

| Capability | Status | Notes |
|---|---|---|
| Package inspection / NFSMS parsing | Implemented foundation | Partial dialect coverage |
| Database inventory / export scanner | Implemented | Read-only; Attribulina required |
| Vehicle profile anchoring | Implemented for supplied schema | Anchored on `pvehicle/racers` |
| Subsystem relationship discovery | Implemented foundation | Explicit pvehicle references; unresolved refs audited |
| ecar relationship | Heuristic | Exact vehicle leaf; not an explicit pvehicle reference |
| Numeric feature extraction | Partial | Only exported scalar/vector values; no verified dimensions or drivetrain |
| Donor ranking | Initial explainable engine | Coverage/richness, optionally shared numeric feature similarity |
| Hybrid donor proposal | Review-only, target-aware | Explicit AMOD create mappings; field type validation and executable script generation remain pending |
| NFSMS database validation | Implemented | Convert/check/strict dry-run only |
| Install planning | Implemented foundation | ModLoader provisional; Ed Files unresolved |
| File executor / rollback | Experimental | File operations only; no real-game end-to-end validation |
| MWPS / binary patching | Pending | Format-specific work required |
| Full uninstall manager | Pending | Journal rollback exists, general uninstall does not |
| Live database write workflow | Disabled / pending | Requires separate transactional design and explicit approval |

## Next priorities

1. Validate reference resolution against additional real database snapshots and class header/type exports.
2. Improve AMOD parsing for multiline nested arrays/objects, quoted braces, duplicate fields and comments while retaining raw source.
3. Extract more trustworthy target-car hints from addon NFSMS and package metadata without guessing physical properties.
4. Build per-factor donor scores and confidence/missing-data penalties using validated field types.
5. Validate every proposed scalar against Attribulina class headers, then generate deterministic candidate AMOD and run Attribulina check plus strict dry-run.
6. Independently verify ModLoader mappings; resolve Ed Files and MWPS.
7. Add package-specific staging, failure-injection tests and end-to-end tests using temporary game copies.

## Non-negotiable safety rules

- Never modify ATTRIBUTES.BIN or FE_ATTRIB.BIN during discovery, catalogue generation or tests.
- Never run Attribulina apply against the user's live databases during development.
- Never claim physical compatibility from collection completeness or a few numeric scalar comparisons.
- Never copy donor identity, model, geometry, textures, frontend registration or unique target collection IDs wholesale.
- Never silently overwrite game files; preserve backups and journal operations.
- Keep database mutation separate from file installation and require explicit user approval.
