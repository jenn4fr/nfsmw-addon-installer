"""Transactional file-only plan executor with explicit opt-in and rollback journal."""
from __future__ import annotations
import json, os, shutil, tempfile
from pathlib import Path
from typing import Any
from .planner import _safe_join


def apply_file_plan(plan_path: str | Path, *, execute: bool = False,
                    overwrite: bool = False, backup_root: str | Path | None = None) -> dict[str, Any]:
    plan_file = Path(plan_path).resolve()
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    if not execute:
        return {"mode": "dry-run", "writes_performed": False,
                "eligible_operations": sum(o.get("operation") == "file_copy" and o.get("source_exists") for o in plan.get("operations", [])),
                "message": "Pass --execute to copy files. Database script operations are never executed here."}
    game_root = plan.get("game_root")
    if not game_root:
        raise ValueError("Plan has no game_root; regenerate with --game-root")
    root = Path(game_root).resolve()
    if not root.is_dir():
        raise ValueError(f"Game root does not exist: {root}")
    package_root = Path(plan["package"]).resolve()
    backup = Path(backup_root).resolve() if backup_root else root / "_nfsmw_installer_backups"
    backup.mkdir(parents=True, exist_ok=True)
    journal = {"version": 1, "plan": str(plan_file), "game_root": str(root),
               "backup_root": str(backup), "operations": [], "complete": False}
    try:
        for op in plan.get("operations", []):
            kind = op.get("operation")
            if kind == "script":
                journal["operations"].append({"operation": "script", "status": "skipped-requires-separate-validation"})
                continue
            if kind == "folder_create":
                dest = _safe_join(root, op["destination"])
                existed = dest.exists()
                dest.mkdir(parents=True, exist_ok=True)
                journal["operations"].append({"operation": kind, "destination": str(dest), "created": not existed})
                continue
            if kind != "file_copy":
                continue
            if not op.get("source_exists"):
                raise ValueError(f"Missing source in plan: {op.get('source')}")
            source = Path(op.get("source_absolute") or "").resolve()
            if source != package_root and package_root not in source.parents:
                raise ValueError(f"Source missing or outside package: {source}")
            if not source.is_file():
                raise ValueError(f"Source missing or outside package: {source}")
            dest = _safe_join(root, op["destination"])
            dest.parent.mkdir(parents=True, exist_ok=True)
            entry = {"operation": kind, "source": str(source), "destination": str(dest),
                     "backup": None, "created": not dest.exists()}
            if dest.exists():
                if not overwrite:
                    raise FileExistsError(f"Destination exists; use --overwrite after reviewing plan: {dest}")
                if not dest.is_file():
                    raise ValueError(f"Refusing to overwrite non-file destination: {dest}")
                backup_file = backup / (str(len(journal['operations'])).zfill(4) + "_" + dest.name)
                shutil.copy2(dest, backup_file)
                entry["backup"] = str(backup_file)
            fd, temp_name = tempfile.mkstemp(prefix=".nfsmw-", dir=dest.parent)
            os.close(fd)
            try:
                shutil.copy2(source, temp_name)
                os.replace(temp_name, dest)
            finally:
                if os.path.exists(temp_name): os.unlink(temp_name)
            entry["status"] = "copied"
            journal["operations"].append(entry)
    except Exception:
        rollback_journal(journal)
        raise
    journal["complete"] = True
    journal_path = backup / "install-journal.json"
    journal_path.write_text(json.dumps(journal, indent=2), encoding="utf-8")
    return {"mode": "executed", "writes_performed": True, "journal": str(journal_path),
            "copied_files": sum(o.get("status") == "copied" for o in journal["operations"]),
            "backup_root": str(backup), "database_scripts_executed": False}


def rollback_journal(journal_or_path: dict[str, Any] | str | Path) -> dict[str, Any]:
    journal = (json.loads(Path(journal_or_path).read_text(encoding="utf-8"))
               if not isinstance(journal_or_path, dict) else journal_or_path)
    restored = removed = 0
    game_root = Path(journal["game_root"]).resolve()
    backup_root = Path(journal["backup_root"]).resolve()
    def require_inside(path: Path, base: Path, label: str) -> Path:
        resolved = path.resolve()
        if resolved != base and base not in resolved.parents:
            raise ValueError(f"Unsafe {label} path in rollback journal: {path}")
        return resolved
    for op in reversed(journal.get("operations", [])):
        if op.get("operation") == "folder_create" and op.get("created"):
            folder = require_inside(Path(op["destination"]), game_root, "destination")
            try:
                folder.rmdir()
            except OSError:
                pass
            continue
        if op.get("operation") != "file_copy" or op.get("status") != "copied":
            continue
        dest = require_inside(Path(op["destination"]), game_root, "destination")
        backup = op.get("backup")
        if backup:
            backup_path = require_inside(Path(backup), backup_root, "backup")
            if backup_path.is_file():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_path, dest); restored += 1
        elif op.get("created") and dest.exists():
            dest.unlink(); removed += 1
    return {"restored_files": restored, "removed_files": removed}
