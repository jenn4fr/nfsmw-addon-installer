#!/usr/bin/env bash
set -euo pipefail
ZIP="${1:-}"
if [[ -z "$ZIP" || ! -f "$ZIP" ]]; then
  echo "Usage: bash tools/apply_update.sh /c/Users/Admin/Downloads/nfsmw-addon-installer-update.zip" >&2
  exit 2
fi
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "Run inside the Git repository." >&2; exit 2; }
cd "$ROOT"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: Working tree is not clean. Commit/stash changes first; nothing modified." >&2
  git status --short
  exit 2
fi
git remote get-url origin >/dev/null 2>&1 || { echo "ERROR: origin remote is missing." >&2; exit 2; }
BRANCH="feature/donor-engine-v0.3.0"
git fetch origin --prune
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git switch "$BRANCH"
elif git show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; then
  git switch -c "$BRANCH" --track "origin/$BRANCH"
else
  git switch -c "$BRANCH"
fi
BACKUP=".update-backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP"
python - "$ZIP" "$ROOT" "$BACKUP" <<'PY'
import json, pathlib, re, shutil, stat, sys, zipfile
def native(value):
    m=re.match(r"^/([a-zA-Z])/(.*)$", value)
    return pathlib.Path(f"{m.group(1).upper()}:/{m.group(2)}") if m else pathlib.Path(value)
archive, root, backup = native(sys.argv[1]), native(sys.argv[2]).resolve(), native(sys.argv[3])
with zipfile.ZipFile(archive) as z:
    names=set(z.namelist())
    manifest=json.loads(z.read('manifest.json'))
    files=manifest.get('files', [])
    if not files: raise SystemExit('Empty update manifest')
    for rel in files:
        p=pathlib.PurePosixPath(rel)
        if p.is_absolute() or '..' in p.parts or '\\' in rel: raise SystemExit(f'Unsafe path: {rel}')
        member='files/'+rel
        if member not in names: raise SystemExit(f'Missing archive member: {member}')
        info=z.getinfo(member)
        if stat.S_ISLNK(info.external_attr >> 16): raise SystemExit(f'Symlink payload refused: {rel}')
    for rel in files:
        target=(root/pathlib.Path(*pathlib.PurePosixPath(rel).parts)).resolve()
        if root not in target.parents: raise SystemExit(f'Path escapes repository: {rel}')
        saved=backup/pathlib.Path(*pathlib.PurePosixPath(rel).parts)
        if target.exists():
            saved.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(target,saved)
        else:
            marker=backup/'.new-files'/pathlib.Path(*pathlib.PurePosixPath(rel).parts)
            marker.parent.mkdir(parents=True,exist_ok=True); marker.touch()
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(z.read('files/'+rel))
    (backup/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(f"Installed {len(files)} files. Backup: {backup}")
PY
rollback() {
  python - "$ROOT" "$BACKUP" <<'PY'
import pathlib, re, shutil, sys
def native(value):
    m=re.match(r"^/([a-zA-Z])/(.*)$", value)
    return pathlib.Path(f"{m.group(1).upper()}:/{m.group(2)}") if m else pathlib.Path(value)
root, backup=native(sys.argv[1]),native(sys.argv[2])
new=backup/'.new-files'
if new.exists():
    for marker in sorted(new.rglob('*'),reverse=True):
        if marker.is_file():
            rel=marker.relative_to(new); (root/rel).unlink(missing_ok=True)
for saved in backup.rglob('*'):
    if saved.is_file() and '.new-files' not in saved.parts and saved.name!='manifest.json':
        rel=saved.relative_to(backup); target=root/rel; target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(saved,target)
PY
}
if ! python -m compileall -q nfsmw_installer tools tests; then echo "Compile failed; restoring backup."; rollback; exit 1; fi
if ! python -m unittest discover -s tests -v; then echo "Tests failed; restoring backup."; rollback; exit 1; fi
mapfile -t UPDATE_FILES < <(python - "$ZIP" <<'PY' | tr -d '\r'
import json,sys,zipfile
m=json.loads(zipfile.ZipFile(sys.argv[1]).read('manifest.json'))
for item in m['files']: print(item.rstrip('\r\n'))
PY
)
git add -- "${UPDATE_FILES[@]}"
if git diff --cached --quiet; then echo "No changes to commit."; exit 0; fi
MESSAGE="$(python - "$ZIP" <<'PY'
import json,sys,zipfile
m=json.loads(zipfile.ZipFile(sys.argv[1]).read('manifest.json'))
print(m.get('commit_message','Complete donor assistant and safe file workflow'))
PY
)"
git commit -m "$MESSAGE"
git push -u origin "$BRANCH"
echo "Update tested, committed and pushed: $BRANCH"
echo "Backup retained at: $BACKUP"
