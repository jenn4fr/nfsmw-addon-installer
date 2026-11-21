# AI handoff — read this first

> **Current source of truth:** project version **0.3.0**, updated 2026-11-21. Read the final section, “2026-11-21 update — version 0.3.0 Vehicle Intelligence,” first; it supersedes conflicting v0.1/v0.2 historical notes. Current verified test count: **41 passed**.

# AI / Developer Handoff — Read Before Continuing

This document is intended to let a future AI assistant or developer continue the NFSMW Add-on Installer project from the current repository state without asking the user to repeat known setup details or redoing completed discovery.

## 1. Project goal

Build a safe Windows tool for inspecting and eventually installing add-on/replacement cars for **Need for Speed: Most Wanted (2005), PC**. The tool should support packages containing NFSMS/Unlimiter scripts, ModLoader payloads, MWPS files, frontend resources, and Ed Files where the format and destination are verified.

The longer-term goal includes a **Donor Car Configuration Assistant** for addons whose vehicle attributes are incomplete or incompatible. It should recommend suitable donor configurations and create selective proposed changes while preserving the new car's identity.

## 2. User's preferred working style

- Give exact Git Bash commands that can be pasted directly.
- Prefer automation and complete replacement files over small snippets or manual editing.
- Avoid repeated discovery commands when reports already provide the answer.
- Work in small tested batches; ask for command output only when it changes the next decision.
- The user expects complete downloadable ZIP updates with repository-relative paths and a simple local apply workflow.
- Do not assume the assistant can push to GitHub. The user runs Git operations locally unless an authorized GitHub connector is explicitly available.

## 3. Environment and paths (as last provided)

- Windows 11 Pro, Git Bash, Python 3.12.
- Game root: `D:\softwares\NFS-MW-Unlimiter`.
- Git Bash game root: `/d/softwares/NFS-MW-Unlimiter`.
- Game databases:
  - `D:\softwares\NFS-MW-Unlimiter\GLOBAL\ATTRIBUTES.BIN`
  - `D:\softwares\NFS-MW-Unlimiter\GLOBAL\FE_ATTRIB.BIN`
- Attribulina CLI: `D:\softwares\NFS-hack\utils\Attribulina\attribcli.exe` (v1.9.1).
- Local project path: `D:\softwares\NFS-hack\utils\nfsmw-addon-installer`.
- GitHub: `https://github.com/jenn4fr/nfsmw-addon-installer` (public repository per user).

Paths are environment-specific; CLI path normalization supports Git Bash `/d/...` paths on Windows. Do not hard-code the user's local paths into library code. Keep defaults configurable.

## 4. Source modules and responsibilities

- `nfsmw_installer/core.py`: package/archive scanning, NFSMS parser, file classification, findings/dependency graph, JSON report generation.
- `nfsmw_installer/attribulina.py`: subprocess adapter. Conversion/check/dry-run only. Preserve safety flags and timeout behavior.
- `nfsmw_installer/inventory.py`: class/collection inventory parsing/building/writing.
- `nfsmw_installer/planner.py`: read-only install plan from `Install.nfsms`; safe relative path handling; conflict/unresolved mapping records; provisional ModLoader mapping.
- `nfsmw_installer/donor_catalogue.py`: parses Attribulina textual `.amod` exports and produces read-only catalogue. Simple scalar values are typed; complex values are raw text.
- `nfsmw_installer/cli.py`: argparse commands and orchestration.
- `tools/scan_attribulina_database.py`: read-only Attribulina database scanner.
- `tests/`: `unittest` suite.

Read the source before changing an interface. Do not rely on stale external summaries if the checked-out code differs.

## 5. Current CLI commands

Confirm with `python -m nfsmw_installer.cli --help`.

1. `inspect`
2. `validate-db`
3. `inventory-db`
4. `plan-install`
5. `build-donor-catalogue`
6. `donor-assist` (optional `--target-profile`)
7. `apply-file-plan` (dry-run unless explicit `--execute`)
8. `rollback-install`

There is no general `install`, `uninstall`, or live database `apply` command. The database scanner is a standalone tool script.

## 6. Data findings already established

### Database inventory

- Both databases are `mw_pc` format and expose 57 classes in the supplied scan.
- The combined inventory report records 5,511 node refs and 5,511 collection refs.
- Vehicle-relevant classes include `ecar`, `pvehicle`, `engine`, `induction`, `transmission`, `brakes`, `chassis`, `tires`, `camerainfo`, plus `acceltrans`, `nos`, `shiftpattern`, `presetride`, `rigidbodyspecs`, `engineaudio`, `turbosfx`, and `damagespecs`.
- Earlier comparison suggested many classes are identical between the two databases while `pvehicle` has some differences. Treat that as an observation from supplied exports; re-verify before deriving hard rules.

### Attribulina scan

The supplied scan is under `reports/database-scan-20261120_212135/` in the uploaded project archive. It includes per-database class directories, `complete-export.amod`, `header-types.txt`, `list.txt`, export logs, and `scan-report.json`.

Original scan summary:

- 2,406 commands
- 406 successful
- 2,000 failed
- 0 timeouts
- 114 class exports
- 2,060 individual collection reads attempted

The failed `get` calls commonly returned `attribcli: no collection <class>/<nested path>`. The old scanner was attempting `get` on every nested inventory path. The newer scanner removes that redundant loop and uses the successful complete class exports as the catalogue input.

### Donor catalogue output from supplied exports

The v0.3.0 catalogue builder anchors canonical road-car profiles on `pvehicle/racers`, resolves subsystem collection references from pvehicle fields, and keeps ATTRIBUTES.BIN and FE_ATTRIB.BIN distinct. Current supplied-export validation is recorded in the v0.3.0 update section below: 4,730 parsed collections, 86 profiles (43 per database), 1,272 relationship edges and zero export parse errors.

## 7. User's donor assistant policy — important

The user selected **Option B** and a **Hybrid** approach:

- Preserve essential new-car registration and identity entries.
- Preserve target car model/identity, geometry, textures, unique name/ID, and collection identity.
- Do not blindly copy an entire donor car.
- Reject or replace incompatible performance/customization entries with selected donor configuration entries.
- Choose configuration selectively by category, supported by actual database evidence.
- Consider body size, drivetrain, weight, wheelbase, tire setup, performance tier, customization support, frontend structure, engine config, and closest overall donor.
- Provide transparent top-10 donor candidates, score explanations, and missing-data warnings.
- Proposed changes must be target-specific and validated; never auto-apply them.

Suggested future modes were Strict, Recommended, Custom, and Hybrid. Hybrid is the selected default approach. Implement other modes only if the user still wants them.

## 8. Current sample package: AMC Rebel

The user tested `D:\softwares\NFS-hack\cars2\1970 AMC Rebel The Machine`.

- `Addon/Install.nfsms` contains folder creation, file copies, and a `script SetupFiles/rebel_install.nfsms` reference.
- ModLoader replacement files are under `Addon/Modloader/ADDONS/CARS_REPLACE/PUNTO/`.
- A frontend manufacturer resource exists under `Addon/Modloader/ADDONS/FRONTEND/MANUFACTURERS/75-REBEL.BIN`.
- Ed Files includes `Addon/Ed Files/Config/NFSMW/REBEL.ini` and resource assets.
- The user's `REBEL.ini` resource count was corrected to 2; backup retained in source package.
- Attribulina conversion/check/dry-run artifacts show the script was accepted by the user's environment. The dry-run was not committed to the game DB.
- A read-only plan identified an unresolved Ed Files destination mapping.

Use reports as evidence; do not assume every AMC Rebel package file is ready to install.

## 9. Current test baseline

Run in repository root:

```bash
python -m compileall -q nfsmw_installer tools tests
python -m unittest discover -s tests -v
```

The historical v0.2.0 baseline was 37 tests. The current v0.3.0 baseline is **41 tests passed**. Existing test groups cover parser, inventory, dependencies, Attribulina adapter, CLI path handling, planner, ModLoader path mapping, and donor catalogue parsing/building.

Every new feature needs tests. Preserve all current tests.

## 10. Next implementation sequence

### Priority A — Improve donor data model

- Parse AMOD blocks robustly: escaped quotes, braces in strings, nested objects, arrays, duplicate field names, comments, and multiline values.
- Keep raw source text and parser diagnostics for each record.
- Parse headers/types and collection inventory to validate field types and cross-reference class/collection paths.
- Replace leaf-only grouping with stable keys that include database, class, full collection path, and inferred vehicle relationship.
- Build a normalized vehicle profile graph; do not equate a collection leaf with a car ID.

### Priority B — Vehicle relationship discovery

- Determine how `ecar` references `pvehicle`, `engine`, `induction`, `transmission`, `brakes`, `chassis`, `tires`, and related classes using actual exported field values and type definitions.
- Identify identity/registration fields versus reusable tune/config fields.
- Compare ATTRIBUTES and FE_ATTRIB records without collapsing them.
- Record unknown/unresolved references explicitly.

### Priority C — Donor matching

- Candidate scoring should be evidence-based and explainable.
- Use only fields actually present and typed/validated.
- Include missing-data penalties and confidence; don't fabricate drivetrain, wheelbase, weight, or body dimensions if the DB doesn't expose them.
- Generate a top-10 list with per-factor scores and exclusions.
- Add tests with known synthetic examples and fixtures derived from exports.

### Priority D — Selective proposal generator

- Implement user's Option B / Hybrid policy.
- Preserve identity and registration fields/collections.
- Select only compatible config categories from donor.
- Produce a proposed `.nfsms`/`.amod` change file plus machine-readable explanation/manifest.
- Do not invoke actual apply. Validate with Attribulina conversion/check/strict dry-run.
- Make generated proposals deterministic and reviewable.

### Priority E — Installer execution (later, only after approval)

- Verify ModLoader mapping from actual loader behavior.
- Resolve Ed Files mapping and supported resource packaging.
- Add staging, collision checks, backups, atomic copy, rollback, and uninstall manifests.
- Handle MWPS/binary patch formats only with format-specific validation.
- Keep database changes separate from file installation; require backups and explicit confirmation.

## 11. Non-negotiable safety rules

- Never edit `ATTRIBUTES.BIN` or `FE_ATTRIB.BIN` during discovery, catalogue building, or tests.
- Never run Attribulina `apply` against live databases during development.
- Never assume a successful dry-run equals installation.
- Never copy donor identity, geometry, textures, frontend IDs, or unique target registration wholesale.
- Never treat unresolved destination mappings as ready.
- Never silently overwrite game files.
- Require backups, a reviewable plan, and explicit user approval before any future write-capable workflow.

## 12. Suggested first command for a new AI session

From the project root:

```bash
python -m nfsmw_installer.cli --help
python -m unittest discover -s tests -v
```

Then read this handoff, `PROJECT_STATUS.md`, `ROADMAP.md`, `ARCHITECTURE.md`, and the relevant implementation/tests before changing code. Do not re-run the full Attribulina scan unless the existing exports are missing or the user explicitly requests a fresh scan.

---

## 2026-11-21 update — version 0.2.0 development snapshot

The project was extended after the original 30-test handoff baseline. Read the current source; this section supersedes older statements above that said donor-assist/apply/rollback commands did not exist.

### New modules

- `nfsmw_installer/donor_matcher.py`
  - `rank_donors(catalogue, target_name, limit, database)` ranks pvehicle-backed road-car profiles using weighted presence of `pvehicle`, `engine`, `induction`, `transmission`, `brakes`, `chassis`, `tires`, `acceltrans`, `nos`, `shiftpattern`, and `rigidbodyspecs`, plus scalar-field richness.
  - The score is a configuration data coverage metric only. It is NOT a measured physical compatibility score.
  - Police/chopper/traffic collection paths are excluded from road-car donor shortlist.
  - `build_configuration_proposal(...)` produces review-only JSON; pvehicle fields are limited to an explicit allowlist and identity domains are preserved.
- `nfsmw_installer/apply_plan.py`
  - `apply_file_plan()` defaults to dry-run.
  - `execute=True` is required to copy files.
  - Existing destinations require `overwrite=True`; overwritten files are backed up.
  - Writes `install-journal.json`; `rollback_journal()` restores backups or removes newly created files.
  - Database script operations are skipped. This is a file-only experimental executor.

### New CLI commands

```bash
python -m nfsmw_installer.cli donor-assist ADDON_DIR --catalogue reports/donor-catalogue.json --limit 10
python -m nfsmw_installer.cli donor-assist ADDON_DIR --catalogue reports/donor-catalogue.json --donor punto
python -m nfsmw_installer.cli apply-file-plan reports/install-plan.json
python -m nfsmw_installer.cli apply-file-plan reports/install-plan.json --execute
python -m nfsmw_installer.cli rollback-install PATH_TO/install-journal.json
```

`apply-file-plan --execute` changes files in the supplied plan's game root. It is not a recommendation to use this on a live installation until ModLoader/Ed Files mappings have been verified. Review the JSON plan first. Database scripts are not executed.

### Verification

- Updated package version: 0.2.0.
- `python -m compileall -q nfsmw_installer tools tests` succeeded.
- `python -m unittest discover -s tests -v`: **37 tests passed**.
- Donor catalogue rebuilt from supplied exports: 4,730 collection records, 860 leaf-keyed profile groups, zero parse errors.
- Donor shortlist smoke test returned 113 candidate profiles after excluding police/chopper/traffic classes; top 10 smoke test completed. The score is completeness only, not physical compatibility.

### Known gaps remain

- The donor matcher does not yet compare dimensions, drivetrain, wheelbase, or actual handling characteristics.
- Current profiles group by leaf name and may incorrectly combine class collections with identical leaves; canonical relationship discovery is a priority.
- Configuration proposal JSON is not executable and has unresolved target collection mappings.
- File executor is experimental and not yet validated against real game installation. Folder cleanup, failure injection, symlink race-hardening, and representative package tests remain.
- ModLoader mapping is provisional; Ed Files/MWPS remain unresolved.
- No database write, live install, or live uninstall was performed.

### Instructions for the next AI/developer

1. Run compileall and the complete unittest suite first.
2. Inspect `donor_matcher.py`, `apply_plan.py`, and their tests before extending them.
3. Fix catalogue identity/relationship modeling before claiming compatibility recommendations.
4. Do not promote the coverage score as physical suitability.
5. Do not generate executable donor AMOD until target references and field types are validated.
6. Do not execute file plans against the user's live game until package-specific mappings are independently confirmed.
7. Keep all database mutation separate from file operations and require explicit confirmation plus verified backups.

---

## 2026-11-21 update — version 0.3.0 Vehicle Intelligence

This section supersedes the older v0.2.0 statements that profiles were grouped only by leaf name and that canonical relationship discovery had not begun.

### Source changes

- `donor_catalogue.py` now captures each collection's parent path from AMOD headers.
- Canonical road-car candidates are anchored on `pvehicle` records whose parent is `pvehicle/racers`. This excludes police, traffic, trailers and generic category nodes at the source rather than trying to filter all of them later.
- Each canonical pvehicle record is scanned for explicit `class/collection` references in its top-level exported values. Known vehicle classes are resolved against their corresponding class export, including base and upgrade variants (for example `engine/rx7` and `engine/rx7_top`).
- The catalogue emits `relationship_edges` and per-profile `collection_references` with resolved/unresolved status.
- `ecar` is joined by exact vehicle leaf because the inspected pvehicle records do not expose it as a direct subsystem field. The report labels this as `exact-vehicle-leaf`; do not upgrade its confidence without more evidence.
- Numeric features currently include pvehicle mass and upgrade-count fields, HandlingRating bounds, TENSOR_SCALE vector, plus selected ecar ride-height/camber/steer/wheel fields. No drivetrain, wheelbase or body-size inference is made.
- `donor_matcher.rank_donors(..., target_profile=...)` can compare shared numeric scalar/vector features against a known profile. The ranking is still heuristic and explicitly not a physical-fitment guarantee.
- CLI `donor-assist` accepts `--target-profile <profile-key-or-name>`.

### Validation against supplied scan

Using `reports/database-scan-20261120_212135/`:

- 4,730 class collection records parsed.
- 86 canonical profiles total: 43 ATTRIBUTES.BIN and 43 FE_ATTRIB.BIN.
- 1,272 relationship edges emitted; 1,190 recognized pvehicle references were audited (1,188 resolved, 2 unresolved).
- 0 export-file parse/read errors.
- 2 unresolved references among recognized vehicle-class references; unresolved entries are retained in the profile audit.
- The stock database does not contain an AMC Rebel profile. For that add-on, the current top-10 remains a configuration-completeness shortlist unless a known baseline vehicle is supplied with `--target-profile`.

### CLI examples

Build catalogue:

```bash
python -m nfsmw_installer.cli build-donor-catalogue \
  reports/database-scan-20261120_212135 \
  -o reports/donor-catalogue-v0.3.0.json
```

AMC Rebel-style custom add-on (no target profile available):

```bash
python -m nfsmw_installer.cli donor-assist \
  "/path/to/addon-folder" \
  --catalogue reports/donor-catalogue-v0.3.0.json \
  --limit 10 -o reports/donor-assist.json
```

Known baseline target profile (example RX-7):

```bash
python -m nfsmw_installer.cli donor-assist \
  "/path/to/addon-folder" \
  --catalogue reports/donor-catalogue-v0.3.0.json \
  --target-profile attributes.bin:rx7 \
  --limit 10 -o reports/donor-assist-rx7-baseline.json
```

### Tests

The v0.3.0 suite has **41 passing tests**. It adds tests for parent path parsing, pvehicle/racers anchoring, explicit subsystem reference resolution (including a different engine leaf), target-profile numeric similarity, and missing target-profile rejection.

### Remaining work after v0.3.0

1. Robust AMOD parser for nested/multiline values and comments; current parser only extracts safe top-level scalars/raw single-line values.
2. Parse field types/headers and validate reference targets and field compatibility against Attribulina exports.
3. Extract addon target hints from NFSMS and package metadata; no stock profile exists for AMC Rebel.
4. Add confidence-weighted per-factor donor score and meaningful missing-data penalties.
5. Confirm ecar relation and other identity/frontend relationships from authoritative references.
6. Generate target-specific, deterministic AMOD only after mapping/field types/dependencies are proven; still require Attribulina check and strict dry-run.
7. Verify ModLoader/Ed Files/MWPS mappings and complete install/uninstall tests.

Never treat this release as a completed installer. Database writes remain out of scope, and the experimental file executor must not be used on a live game without package-specific mapping verification and user approval.
