# Project Status — v0.5.0 live-installation audit foundation

## Added in this update

- Read-only audit of a real NFS MW game installation.
- Required executable/database/directory checks.
- SHA-256 and size evidence for key game files.
- Optional Attribulina `info` inspection of both databases.
- ModLoader/Unlimiter directory discovery and ModLoader log-tail capture.
- Tests that prove the audit does not modify its fixture installation.

## Not claimed complete

This update does not implement live database mutation, executable AMOD
generation, universal Ed Files/MWPS mappings, or a verified universal
post-install attribute verifier. Those require exact field schemas, target
collection mappings, expected-value manifests, and read-back support.

## Run tests

```bash
python -m compileall -q nfsmw_installer tools tests
python -m unittest discover -s tests -v
```
