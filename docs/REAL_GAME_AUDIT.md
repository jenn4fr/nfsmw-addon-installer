# Real game installation audit

The saved read-only audit is `reports/real-game-installation-audit.json`.

## Audited target

`D:\softwares\NFS-MW-Unlimiter`

Audit result: **audited**, with no writes performed.

- `speed.exe`: 6,029,312 bytes; SHA-256 matches the previously verified v1.3 reference.
- `GLOBAL/ATTRIBUTES.BIN`: present; Attribulina `info` passed (57 classes, 2,379 collections).
- `GLOBAL/FE_ATTRIB.BIN`: present; Attribulina `info` passed (57 classes, 461 collections in that vault).
- `dinput8.dll`: present.
- `scripts/NFSMWUnlimiter.asi`: present.
- `scripts/NFSMW-ML.asi`: present.
- `scripts/UnlimiterData`: present.
- `modloader` folder and `NFSMW-ML.log`: present. The log reports NFSMW-ML v1.0.0 and successful initialization of two mod folders.

This is the separate Unlimiter/NFSMW-ML installation. Do not confuse it with the protected original Classic ModLoader game folder.

The saved audit did not include a dedicated check for `d3d9.dll` and `modloader.ini`; the guided installer checks those directly at runtime before allowing a Classic ModLoader replacement profile.

## Running a fresh audit

From Git Bash:

```bash
python tools/audit_game_installation.py \
  --game-root "/d/softwares/NFS-MW-Unlimiter" \
  --attribulina "/d/softwares/NFS-hack/utils/Attribulina/attribcli.exe" \
  -o "reports/real-game-installation-audit.json"
```

The audit checks required files/directories, records hashes, identifies optional loaders and can run Attribulina's read-only `info` command against both databases. It never invokes `apply` and never modifies the game.

## What this audit does not prove

- It does not prove any particular add-on car is correctly registered.
- It does not verify individual VLT field values.
- It does not prove Binary or Ed changes were applied.
- It does not prove the game launches or that a car can be selected/driven.

Those are installation-specific stages in the guided workflow and require actual read-back and an in-game test.
