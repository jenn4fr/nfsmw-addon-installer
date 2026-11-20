"""Read-only installation planner for NFS Most Wanted addon packages.

This module builds a manifest only. It never copies, deletes, patches, or writes
files into a game installation.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any



_INSTALL_SCRIPT = "Install.nfsms"
_SUPPORTED_INSTALL_OPS = {"folder_create", "file_copy", "script"}



def _norm_rel(value: str) -> str:
    """Normalize Windows-style package paths into POSIX relative paths."""
    value = value.strip().strip('"').strip("'").replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value



def _safe_join(root: Path, rel: str) -> Path:
    """Resolve a relative path and reject traversal outside root."""
    rel_path = Path(_norm_rel(rel))
    if rel_path.is_absolute() or any(part == ".." for part in rel_path.parts):
        raise ValueError(f"Unsafe relative path: {rel}")
    resolved = (root / rel_path).resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError(f"Path escapes root: {rel}")
    return resolved


def _parse_install_script(script_path: Path) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    text = script_path.read_text(encoding="utf-8", errors="replace")
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Remove comments conservatively; installer UI lines are not operations.
        command_match = re.match(r"^(folder_create|file_copy|script)\s+(.+)$", line, re.I)
        if not command_match:
            continue
        command = command_match.group(1).lower()
        args = command_match.group(2).strip()
        if command == "file_copy":
            parts = re.split(r"\s+", args, maxsplit=1)
            if len(parts) != 2:
                operations.append({"operation": command, "line": line_no, "raw": raw,
                                 "status": "invalid", "reason": "Expected source and destination"})
                continue
            source, destination = map(_norm_rel, parts)
            operations.append({"operation": command, "line": line_no, "source": source,
                              "destination": destination, "mechanism": "addon-installer",
                              "status": "pending"})
        elif command == "folder_create":
            operations.append({"operation": command, "line": line_no,
                              "destination": _norm_rel(args), "mechanism": "addon-installer",
                              "status": "pending"})
        elif command == "script":
            operations.append({"operation": command, "line": line_no,
                              "script": _norm_rel(args), "mechanism": "database-script",
                              "status": "requires-validation"})
    return operations



def _find_install_script(package_root: Path) -> Path | None:
    candidates = [p for p in package_root.rglob(_INSTALL_SCRIPT) if p.is_file()]
    # Prefer Addon/Install.nfsms over any nested/duplicate script.
    candidates.sort(key=lambda p: (0 if p.parent.name.lower() == "addon" else 1, len(p.parts), str(p).lower()))
    return candidates[0] if candidates else None



def build_install_plan(package: str | Path, game_root: str | Path | None = None) -> dict[str, Any]:
    """Build a read-only install plan for an extracted addon package directory."""
    package_root = Path(package).expanduser().resolve()
    if not package_root.exists() or not package_root.is_dir():
        raise ValueError(f"Package must be an extracted directory: {package_root}")
    install_script = _find_install_script(package_root)
    if install_script is None:
        raise ValueError(f"Could not find {_INSTALL_SCRIPT} under {package_root}")

    game_path = Path(game_root).expanduser().resolve() if game_root else None
    operations = _parse_install_script(install_script)
    conflicts: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for operation in operations:
        if operation.get("operation") == "file_copy":
            source_path = _safe_join(install_script.parent, operation["source"])
            operation["source_absolute"] = str(source_path)
            operation["source_exists"] = source_path.is_file()
            if not operation["source_exists"]:
                operation["status"] = "missing-source"
                operation["reason"] = "Source file was not found in package"
            if game_path:
                destination_path = _safe_join(game_path, operation["destination"])
                operation["destination_absolute"] = str(destination_path)
                operation["destination_exists"] = destination_path.exists()
                if destination_path.exists():
                    operation["status"] = "conflict"
                    conflict = {"destination": operation["destination"],
                                "existing_path": str(destination_path),
                                "type": "existing-file-or-directory",
                                "requires_backup": True}
                    conflicts.append(conflict)
                elif operation.get("source_exists"):
                    operation["status"] = "ready"
            else:
                operation["destination_exists"] = None
                operation["status"] = "ready" if operation.get("source_exists") else "missing-source"
        elif operation.get("operation") == "folder_create":
            if game_path:
                destination_path = _safe_join(game_path, operation["destination"])
                operation["destination_absolute"] = str(destination_path)
                operation["destination_exists"] = destination_path.exists()
                operation["status"] = "already-exists" if destination_path.exists() else "ready"
            else:
                operation["status"] = "destination-unresolved"
        elif operation.get("operation") == "script":
            script_path = _safe_join(install_script.parent, operation["script"])
            operation["script_absolute"] = str(script_path)
            operation["script_exists"] = script_path.is_file()
            operation["status"] = "ready-for-db-validation" if script_path.is_file() else "missing-script"
            operation["reason"] = "Database script is not executed by this planner"

    # ModLoader uses one folder per mod and mirrors game-relative paths.
    modloader_root = package_root / "Modloader"
    addons_root = modloader_root / "ADDONS"
    if addons_root.is_dir():
        mod_name = re.sub(r"[^A-Za-z0-9_-]+", "_", package_root.name).strip("_")
        if not mod_name:
            raise ValueError("Could not derive a safe ModLoader mod folder name")

        known_mappings = {
            "CARS_REPLACE": "CARS",
            "FRONTEND": "FRONTEND",
        }

        for source_group in sorted(addons_root.iterdir()):
            if not source_group.is_dir():
                unresolved.append({
                    "source": str(source_group), "mechanism": "modloader",
                    "status": "mapping-required",
                    "reason": "Unexpected file directly under Modloader/ADDONS"
                })
                continue

            destination_group = known_mappings.get(source_group.name.upper())
            if destination_group is None:
                unresolved.append({
                    "source": str(source_group), "mechanism": "modloader",
                    "status": "mapping-required",
                    "reason": "Unrecognized ModLoader ADDONS directory"
                })
                continue

            for source_file in sorted(p for p in source_group.rglob("*") if p.is_file()):
                relative_payload = source_file.relative_to(source_group)
                destination_rel = (
                    Path("modloader") / mod_name /
                    destination_group / relative_payload
                ).as_posix()

                operation = {
                    "operation": "file_copy",
                    "mechanism": "modloader",
                    "source": source_file.relative_to(package_root).as_posix(),
                    "source_absolute": str(source_file.resolve()),
                    "source_exists": True,
                    "destination": destination_rel,
                    "mod_name": mod_name,
                }

                if game_path:
                    destination_path = _safe_join(game_path, destination_rel)
                    operation["destination_absolute"] = str(destination_path)
                    operation["destination_exists"] = destination_path.exists()
                    if destination_path.exists():
                        operation["status"] = "conflict"
                        conflict = {
                            "destination": destination_rel,
                            "existing_path": str(destination_path),
                            "type": "existing-file-or-directory",
                            "requires_backup": True,
                        }
                        conflicts.append(conflict)
                    else:
                        operation["status"] = "ready"
                else:
                    operation["destination_exists"] = None
                    operation["status"] = "destination-unresolved"

                operations.append(operation)

    # ED resources need their own verified destination mapping.
    ed_root = package_root / "Addon" / "Ed Files"
    if ed_root.exists():
        unresolved.append({
            "source": str(ed_root), "mechanism": "ed-resource",
            "status": "mapping-required",
            "reason": "ED configuration/resource destination has not yet been verified"
        })


    backup_plan = [
        {"destination": c["destination"], "existing_path": c["existing_path"],
         "backup_required": True, "rollback_action": "restore-backup"}
        for c in conflicts
    ]
    return {
        "planner_version": "0.1.0",
        "package": str(package_root),
        "install_script": str(install_script),
        "game_root": str(game_path) if game_path else None,
        "mode": "read-only-plan",
        "writes_performed": False,
        "operations": operations,
        "conflicts": conflicts,
        "unresolved_mappings": unresolved,
        "backup_rollback_plan": backup_plan,
        "summary": {
            "operation_count": len(operations),
            "ready_count": sum(1 for op in operations if op.get("status") == "ready"),
            "conflict_count": len(conflicts),
            "unresolved_mapping_count": len(unresolved),
            "missing_source_count": sum(1 for op in operations if op.get("status") == "missing-source"),
        },
        "safety_note": "Plan only. No game files or databases were changed.",
    }



def write_plan(plan: dict[str, Any], output: str | Path) -> Path:
    output_path = Path(output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return output_path
