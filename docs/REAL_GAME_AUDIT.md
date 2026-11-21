# Real Game Installation Audit

The `tools/audit_game_installation.py` utility performs a read-only preflight
against an existing NFS Most Wanted (2005) installation.

## Run on the configured installation

From the repository root in Git Bash:

```bash
python tools/audit_game_installation.py \
  --game-root "/d/softwares/NFS-MW-Unlimiter" \
  --attribulina "/d/softwares/NFS-hack/utils/Attribulina/attribcli.exe" \
  -o "reports/real-game-installation-audit.json"
```

The utility checks required game files/directories, hashes the executable and
database files, records optional ModLoader/Unlimiter locations, captures the
ModLoader log tail when present, and optionally runs Attribulina's read-only
`info` command against both databases.

It never calls Attribulina `apply`, never writes to the game root, and never
changes either database.

## Interpretation

- `audited`: required files and directories exist; optional Attribulina checks
  were not requested or passed.
- `warning`: required files/directories exist, but an Attribulina info check
  failed or timed out.
- `incomplete`: at least one required file or directory is missing.

A speed.exe size/hash mismatch is recorded as a reference warning only. It is
not treated as proof of an invalid installation.

## Important limitation

This is the real-installation **preflight** stage. It does not prove that an
add-on's VLT attributes were installed correctly. That requires an
installation-specific expected-value manifest containing exact database,
class, collection and field/value pairs, followed by independent read-back
queries and comparison. The verifier must not infer expected values from a
donor name or from the installer reporting success.

The eventual post-install verifier will compare:

1. The expected plan/approved attribute manifest.
2. The actual values read back from `ATTRIBUTES.BIN` and `FE_ATTRIB.BIN`.
3. The actual installed files and their hashes.
4. The installation journal and before/after database snapshots.

A mismatch must result in `FAIL` or `PARTIAL`, never success. Game launch and
in-game vehicle/menu validation are a separate end-to-end gate.
