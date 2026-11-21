# Project Status — 2026-11-21

**Version:** 0.2.0 development snapshot  
**Overall:** substantially expanded analysis/planning foundation; experimental file executor; not yet a production-safe universal installer.

## Verified in this snapshot

- Package inspection, file classification, partial NFSMS parsing and dependency findings.
- Attribulina conversion/check/strict dry-run adapter; no database apply operation exposed.
- Read-only inventory of ATTRIBUTES.BIN and FE_ATTRIB.BIN.
- Read-only install planner with source checks, destination conflicts, ModLoader provisional mapping, and unresolved Ed Files mapping.
- AMOD export parser and catalogue builder. Supplied exports: 4,730 parsed collection records, 860 leaf-keyed profile groups, zero export-file parse errors.
- Donor ranking command. It filters non-road-car police/chopper/traffic candidates and ranks road-car profiles by configuration class coverage and exported scalar-field richness.
- Review-only donor configuration proposal. It filters pvehicle fields to a conservative allowlist and excludes identity-oriented classes/domains. It does not generate executable AMOD/NFSMS.
- File-only plan executor, dry-run by default; explicit `--execute` required. It backs up replaced files, writes an install journal, skips database scripts, and supports journal rollback.

## Current CLI

1. `inspect`
2. `validate-db`
3. `inventory-db`
4. `plan-install`
5. `build-donor-catalogue`
6. `donor-assist`
7. `apply-file-plan`
8. `rollback-install`

## Test status

**37 tests passed** after adding donor matcher and file-executor tests. Run:

```bash
python -m compileall -q nfsmw_installer tools tests
python -m unittest discover -s tests -v
```

Tests cover the existing parser/inventory/dependency/Attribulina/planner behavior plus donor ranking, identity-field filtering, dry-run, explicit copy, backup and rollback. They do not constitute an end-to-end game installation test.

## Status by capability

| Capability | Status | Notes |
|---|---|---|
| Package inspection / NFSMS parsing | Implemented foundation | Partial dialect coverage |
| Database inventory / export scanner | Implemented | Read-only; Attribulina required |
| NFSMS validation | Implemented | Conversion/check/strict dry-run only |
| Install planning | Implemented | ModLoader mapping provisional; Ed Files unresolved |
| Donor catalogue | Implemented initial | Leaf grouping is not canonical identity |
| Donor shortlist | Implemented initial | Coverage ranking, not physics compatibility |
| Hybrid donor proposal | Review-only | No target mapping or executable script generation |
| File executor | Experimental | Explicit opt-in; backup/journal/rollback; database scripts skipped |
| Full install workflow | Pending | Requires mapping verification and end-to-end package tests |
| Database config application | Pending | Must remain separate, explicit, backed up, and Attribulina-validated |
| MWPS/binary patching | Pending | Format-specific work required |
| Ed Files installation | Pending | Destination/resource mapping unresolved |
| Uninstall manager | Pending | Rollback journal exists; persistent uninstall manifest/clean uninstall pending |
| Physical donor compatibility | Pending | Need schema/reference analysis and actual measurable target attributes |

## Critical limitations / caveats

1. **Donor score meaning:** score measures availability of configuration classes and scalar fields. It must not be described as a vehicle suitability or handling compatibility score.
2. **Profile identity:** `database:leaf` is a grouping convenience. Different class collections can share leaves; canonical cross-class vehicle relationships still need discovery.
3. **Proposal safety:** proposal JSON is non-executable. `target_collection` remains unresolved; references and field types must be validated before any AMOD generation.
4. **Installer safety:** `apply-file-plan --execute` can change files in the specified game root. Use only after manually reviewing the plan. Existing file overwrite requires `--overwrite`; backup/journal are produced. Database script operations are skipped.
5. **Mappings:** ModLoader destination mapping is provisional. Ed Files and MWPS are not supported by the executor.
6. **Validation:** no live game install or live database write has been performed by this project.

## Next priorities

1. Improve catalogue identity model using actual cross-class references and preserve full collection paths.
2. Parse AMOD typed/nested values and validate fields against Attribulina headers.
3. Build a target vehicle profile from add-on NFSMS + local DB and compute evidence-based similarity where measurable data exists.
4. Resolve donor proposal target collection mappings and external references; generate candidate AMOD only after validation rules are proven.
5. Verify ModLoader mapping and add representative package fixtures; resolve Ed Files.
6. Add end-to-end staging/install/rollback tests in a temporary game-root fixture.
7. Implement explicit database transaction workflow only after backup/restore semantics are proven; never auto-apply.
8. Add uninstall manifest and safe uninstall preview.

## Sample evidence

AMC Rebel sample: `Addon/Install.nfsms`, `SetupFiles/rebel_install.nfsms`, ModLoader replacement payload under `Addon/Modloader/ADDONS/CARS_REPLACE/PUNTO/`, frontend manufacturer resource, and Ed Files config. Attribulina conversion/check/dry-run accepted the NFSMS script. The install plan left Ed Files unresolved. The user's live game DB was not modified.
