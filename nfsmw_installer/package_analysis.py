"""Evidence-based analysis of real NFS Most Wanted car-mod packages.

This module does not install anything. It identifies installation mechanisms,
entry points, nested scripts, target car IDs, and external-tool requirements.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any

from .core import parse_nfsms


def read_text(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8-sig", errors="replace")


def _safe_package_path(value: str) -> str:
    value = value.strip().strip('"').strip("'").replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    if not value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ValueError(f"Unsafe package-relative path: {value!r}")
    parts = PurePosixPath(value).parts
    if any(part in {"..", ""} for part in parts):
        raise ValueError(f"Unsafe package-relative path: {value!r}")
    return "/".join(parts)


def _resolve_case_insensitive(root: Path, relative: str) -> Path | None:
    """Resolve a package path using Windows-style case-insensitive lookup."""
    try:
        rel = _safe_package_path(relative)
    except ValueError:
        return None
    current = root
    for part in rel.split("/"):
        if not current.is_dir():
            return None
        matches = [p for p in current.iterdir() if p.name.casefold() == part.casefold()]
        if not matches:
            return None
        current = sorted(matches, key=lambda p: p.name)[0]
    return current


def _parse_binary_manifest(path: Path) -> dict[str, Any] | None:
    text = read_text(path).strip()
    if not text.upper().startswith("[VERSN1]"):
        return None
    body = text.split("\n", 1)[1].strip() if "\n" in text else ""
    # Binary's historical manifests contain raw Windows separators. In these
    # path-only manifest fields every backslash is a separator, including the
    # sequences JSON would otherwise interpret as \f, \t, etc. Preserve an
    # escaped quote but double all other backslashes before JSON parsing.
    body = re.sub(r'\\(?!")', lambda _m: "\\\\", body)
    # Binary manifests are JSON-like and commonly retain trailing commas.
    body = re.sub(r",\s*([}\]])", r"\1", body)
    try:
        obj = json.loads(body)
    except json.JSONDecodeError as exc:
        return {"valid": False, "error": str(exc), "raw_header": "[VERSN1]"}
    if not isinstance(obj, dict):
        return {"valid": False, "error": "Binary VERSN1 body is not a JSON object"}
    files = obj.get("Files", [])
    links = obj.get("Links", [])
    if not isinstance(files, list) or not isinstance(links, list):
        return {"valid": False, "error": "Binary Files/Links must be arrays"}
    safe_files = []
    safe_links = []
    errors = []
    for item in files:
        if not isinstance(item, str):
            errors.append("Non-string path in Files array")
            continue
        try:
            safe_files.append(_safe_package_path(item))
        except ValueError as exc:
            errors.append(str(exc))
    for item in links:
        if not isinstance(item, dict):
            errors.append("Non-object entry in Links array")
            continue
        file_value = item.get("File")
        if not isinstance(file_value, str):
            errors.append("Link entry has no string File path")
            continue
        try:
            safe_links.append({**item, "File": _safe_package_path(file_value)})
        except ValueError as exc:
            errors.append(str(exc))
    endscript = obj.get("Endscript")
    if isinstance(endscript, str):
        try:
            endscript = _safe_package_path(endscript)
        except ValueError as exc:
            errors.append(str(exc))
    else:
        errors.append("Binary manifest has no Endscript path")
    return {
        "valid": not errors,
        "usage": obj.get("Usage"),
        "game": obj.get("Game"),
        "directory": obj.get("Directory"),
        "endscript": endscript,
        "game_files": safe_files,
        "links": safe_links,
        "errors": errors,
    }


def _binary_script_summary(path: Path) -> dict[str, Any]:
    text = read_text(path)
    commands: list[dict[str, Any]] = []
    references: list[str] = []
    target_game_files: set[str] = set()
    uninstall_target_files: set[str] = set()
    move_file_operations: list[dict[str, str]] = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", "//", ";")) or line.startswith("["):
            continue
        m = re.match(r"([A-Za-z_][\w]*)\s+(.*)$", line)
        if not m:
            continue
        command, rest = m.group(1).lower(), m.group(2)
        commands.append({"line": line_no, "command": command, "raw": line})
        tokens = re.findall(r'"[^"\n]*"|\S+', rest)
        if command == "append" and tokens:
            ref = tokens[0].strip('"')
            try:
                references.append(_safe_package_path(ref))
            except ValueError:
                pass
        elif command == "import" and len(tokens) >= 3:
            target = tokens[1].strip('"')
            source = tokens[-1].strip('"')
            try:
                target_game_files.add(_safe_package_path(target))
            except ValueError:
                pass
            try:
                references.append(_safe_package_path(source))
            except ValueError:
                pass
        elif command == "bind_textures" and len(tokens) >= 2:
            target = tokens[1].strip('"')
            source = tokens[-1].strip('"')
            try:
                target_game_files.add(_safe_package_path(target))
            except ValueError:
                pass
            try:
                references.append(_safe_package_path(source))
            except ValueError:
                pass
        elif command in {"add_string", "add_texture", "copy_collection", "update_collection", "add_collection", "remove_string", "remove_texture", "remove_collection"} and tokens:
            try:
                path_value = _safe_package_path(tokens[0].strip('"'))
                if command.startswith("remove_"):
                    uninstall_target_files.add(path_value)
                else:
                    target_game_files.add(path_value)
            except ValueError:
                pass
            if command == "add_texture" and len(tokens) >= 2:
                try:
                    references.append(_safe_package_path(tokens[-1].strip('"')))
                except ValueError:
                    pass
        elif command in {"erase_file", "erase_folder"} and len(tokens) >= 2:
            try:
                uninstall_target_files.add(_safe_package_path(tokens[1].strip('"')))
            except ValueError:
                pass
        elif command == "move_file" and len(tokens) >= 5:
            # Binary v2: move_file <policy> <relative|absolute> <source> <dest>
            src = tokens[3].strip('"')
            dest = tokens[4].strip('"')
            try:
                safe_src = _safe_package_path(src)
                references.append(safe_src)
            except ValueError:
                safe_src = src
            try:
                safe_dest = _safe_package_path(dest)
                target_game_files.add(safe_dest)
                move_file_operations.append({"source": safe_src, "destination": safe_dest})
            except ValueError:
                pass
    return {
        "version_header": text.splitlines()[0].strip() if text.splitlines() else "",
        "commands": commands,
        "command_counts": _count_commands(commands),
        "package_references": sorted(set(references)),
        "target_game_files": sorted(target_game_files),
        "uninstall_target_files": sorted(uninstall_target_files),
        "move_file_operations": move_file_operations,
        "binary_gui_required": True,
    }


def _count_commands(commands: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in commands:
        key = item["command"]
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _analyze_nfsms(root: Path, scripts: list[Path]) -> dict[str, Any]:
    script_paths = {p.resolve() for p in scripts}
    included: set[Path] = set()
    missing: list[dict[str, Any]] = []
    unsafe: list[dict[str, Any]] = []
    visited: set[Path] = set()
    queue = list(sorted(script_paths))
    command_counts: dict[str, int] = {}
    car_nodes: set[str] = set()
    copy_ops: list[dict[str, Any]] = []
    ui_controls: list[dict[str, Any]] = []
    ui_options: list[dict[str, Any]] = []
    script_edges: list[dict[str, Any]] = []
    relative_path_fallbacks: list[dict[str, Any]] = []
    ambiguous_script_references: list[dict[str, Any]] = []
    script_base = Path(os.path.commonpath([str(p.parent) for p in sorted(script_paths)])) if script_paths else root

    while queue:
        script = queue.pop(0)
        if script in visited:
            continue
        visited.add(script)
        try:
            text = read_text(script)
        except OSError as exc:
            missing.append({"script": str(script), "error": str(exc)})
            continue
        commands = parse_nfsms(text)
        command_counts[str(script.relative_to(root).as_posix())] = len(commands)
        for cmd in commands:
            a = cmd.args
            if cmd.command == "script" and a:
                raw_ref = a[0]
                try:
                    rel = _safe_package_path(raw_ref)
                except ValueError as exc:
                    unsafe.append({"script": str(script.relative_to(root)), "line": cmd.line, "path": raw_ref, "error": str(exc)})
                    continue
                target = _resolve_case_insensitive(script_base, rel)
                fallback_target = _resolve_case_insensitive(script.parent, rel)
                if target is None or not target.is_file():
                    if fallback_target is not None and fallback_target.is_file():
                        target = fallback_target
                        relative_path_fallbacks.append({"script": str(script.relative_to(root)), "line": cmd.line,
                                                         "reference": raw_ref, "resolved": target.relative_to(root).as_posix()})
                    else:
                        missing.append({"script": str(script.relative_to(root)), "line": cmd.line, "reference": raw_ref})
                        script_edges.append({"from": str(script.relative_to(root)), "line": cmd.line, "to": rel, "status": "missing"})
                        continue
                elif fallback_target is not None and fallback_target.is_file() and fallback_target.resolve() != target.resolve():
                    ambiguous_script_references.append({"script": str(script.relative_to(root)), "line": cmd.line,
                                                        "reference": raw_ref, "main_script_resolution": target.relative_to(root).as_posix(),
                                                        "nested_script_resolution": fallback_target.relative_to(root).as_posix()})
                target = target.resolve()
                included.add(target)
                script_edges.append({"from": str(script.relative_to(root)), "line": cmd.line, "to": str(target.relative_to(root).as_posix()), "status": "resolved"})
                if target not in visited:
                    queue.append(target)
            elif cmd.command == "file_copy" and len(a) >= 2:
                try:
                    source_rel = _safe_package_path(a[0])
                    destination_rel = _safe_package_path(a[1])
                except ValueError as exc:
                    unsafe.append({"script": str(script.relative_to(root)), "line": cmd.line, "error": str(exc)})
                    continue
                source = _resolve_case_insensitive(script.parent, source_rel)
                copy_ops.append({
                    "script": str(script.relative_to(root).as_posix()),
                    "line": cmd.line,
                    "source": str(source.relative_to(root).as_posix()) if source else source_rel,
                    "source_exists": bool(source and source.is_file()),
                    "destination": destination_rel,
                })
            elif cmd.command == "folder_create" and a:
                try:
                    _safe_package_path(a[0])
                except ValueError as exc:
                    unsafe.append({"script": str(script.relative_to(root)), "line": cmd.line, "error": str(exc)})
            elif cmd.command == "copy_node" and len(a) >= 4 and a[0].casefold() == "pvehicle":
                if a[2].casefold() == "racers":
                    car_nodes.add(a[3].upper())
            elif cmd.command == "ui_control":
                ui_controls.append({"script": str(script.relative_to(root)), "line": cmd.line, "args": a})
            elif cmd.command == "ui_option":
                ui_options.append({"script": str(script.relative_to(root)), "line": cmd.line, "args": a})

    all_entrypoints = [p for p in scripts if p.resolve() not in included]
    uninstall_entrypoints = [p for p in all_entrypoints if "uninstall" in p.stem.casefold()]
    entrypoints = [p for p in all_entrypoints if p not in uninstall_entrypoints]
    return {
        "script_count": len(visited),
        "entrypoints": sorted(p.relative_to(root).as_posix() for p in entrypoints),
        "uninstall_entrypoints": sorted(p.relative_to(root).as_posix() for p in uninstall_entrypoints),
        "scripts": sorted(p.relative_to(root).as_posix() for p in visited),
        "script_edges": script_edges,
        "script_base": script_base.relative_to(root).as_posix() if script_base != root else ".",
        "relative_path_fallbacks": relative_path_fallbacks,
        "ambiguous_script_references": ambiguous_script_references,
        "command_counts": command_counts,
        "car_collection_ids": sorted(car_nodes),
        "file_copy_operations": copy_ops,
        "ui_controls": ui_controls,
        "ui_options": ui_options,
        "requires_interactive_choices": bool(ui_controls or ui_options),
        "missing_references": missing,
        "unsafe_references": unsafe,
    }


def _analyze_amod(root: Path, amod_files: list[Path]) -> dict[str, Any]:
    scripts = {p.resolve() for p in amod_files}
    included: set[Path] = set()
    visited: set[Path] = set()
    active: set[Path] = set()
    missing: list[dict[str, Any]] = []
    unsafe: list[dict[str, Any]] = []
    graph: dict[str, list[str]] = {}
    cycles: list[str] = []
    car_ids: set[str] = set()
    game_targets: set[str] = set()

    def visit(path: Path) -> None:
        path = path.resolve()
        if path in visited:
            return
        if path in active:
            cycles.append(path.relative_to(root).as_posix())
            return
        active.add(path)
        rel_script = path.relative_to(root).as_posix()
        graph.setdefault(rel_script, [])
        content = read_text(path)
        for match in re.finditer(r"(?im)^\s*include\s+(?:\"([^\"]+)\"|'([^']+)'|([^\s#;]+))", content):
            reference = match.group(1) or match.group(2) or match.group(3)
            try:
                rel = _safe_package_path(reference)
            except ValueError as exc:
                unsafe.append({"script": rel_script, "reference": reference, "error": str(exc)})
                continue
            target = _resolve_case_insensitive(path.parent, str(rel))
            if target is None or not target.is_file():
                missing.append({"script": rel_script, "reference": reference})
                continue
            target = target.resolve()
            included.add(target)
            graph[rel_script].append(target.relative_to(root).as_posix())
            visit(target)
        for match in re.finditer(r'(?im)^\s*(?:create|collection)\s+pvehicle/([A-Za-z0-9_]+)', content):
            car_ids.add(match.group(1).upper())
        for match in re.finditer(r'(?im)^\s*game\s+([^\s#;]+)', content):
            game_targets.add(match.group(1))
        active.remove(path)
        visited.add(path)

    for script in sorted(scripts):
        visit(script)
    all_entrypoints = sorted(p.relative_to(root).as_posix() for p in scripts if p not in included)
    uninstall_entrypoints = [x for x in all_entrypoints if "uninstall" in Path(x).stem.casefold()]
    entrypoints = [x for x in all_entrypoints if x not in uninstall_entrypoints]
    return {
        "scripts": sorted(p.relative_to(root).as_posix() for p in scripts),
        "entrypoints": entrypoints,
        "uninstall_entrypoints": uninstall_entrypoints,
        "include_graph": graph,
        "missing_references": missing,
        "unsafe_references": unsafe,
        "cycles": sorted(set(cycles)),
        "car_collection_ids": sorted(car_ids),
        "game_targets": sorted(game_targets),
        "script_count": len(scripts),
    }


def analyze_package(package_root: str | Path) -> dict[str, Any]:
    """Analyze an extracted package and return installation profiles/evidence."""
    root = Path(package_root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Package root is not a directory: {root}")

    files = sorted(p for p in root.rglob("*") if p.is_file())
    rels = [p.relative_to(root).as_posix() for p in files]
    warnings: list[dict[str, Any]] = []

    nfsms_files = [p for p in files if p.suffix.casefold() == ".nfsms"]
    amod_files = [p for p in files if p.suffix.casefold() == ".amod"]
    amod = _analyze_amod(root, amod_files) if amod_files else {
        "scripts": [], "entrypoints": [], "uninstall_entrypoints": [], "include_graph": {}, "missing_references": [],
        "unsafe_references": [], "cycles": [], "car_collection_ids": [], "game_targets": [], "script_count": 0,
    }
    nfsms = _analyze_nfsms(root, nfsms_files) if nfsms_files else {
        "script_count": 0, "entrypoints": [], "scripts": [], "script_edges": [],
        "command_counts": {}, "car_collection_ids": [], "file_copy_operations": [],
        "ui_controls": [], "ui_options": [], "requires_interactive_choices": False,
        "missing_references": [], "unsafe_references": [],
    }

    binary_manifests = []
    binary_scripts = []
    for p in files:
        if p.suffix.casefold() != ".end":
            continue
        manifest = _parse_binary_manifest(p)
        if manifest is not None:
            endscript_path = _resolve_case_insensitive(p.parent, manifest.get("endscript") or "")
            binary_manifests.append({
                "path": p.relative_to(root).as_posix(),
                **manifest,
                "endscript_resolved": str(endscript_path.relative_to(root).as_posix()) if endscript_path else None,
                "endscript_exists": bool(endscript_path and endscript_path.is_file()),
            })
        else:
            binary_scripts.append({"path": p, "summary": _binary_script_summary(p)})

    binary_entry_paths = {m["endscript_resolved"] for m in binary_manifests if m.get("endscript_resolved")}
    binary_manifest_roots = []
    for manifest in binary_manifests:
        if manifest.get("endscript_resolved"):
            manifest_root = (root / _safe_package_path(manifest["endscript_resolved"])).parent
            if manifest_root not in binary_manifest_roots:
                binary_manifest_roots.append(manifest_root)
    binary_target_game_files: set[str] = set()
    for item in binary_scripts:
        if "uninstall" not in item["path"].name.casefold():
            binary_target_game_files.update(item["summary"].get("target_game_files", []))
    binary_script_report = []
    binary_missing_references = []
    for item in binary_scripts:
        missing_refs = []
        for ref in item["summary"].get("package_references", []):
            candidates = [item["path"].parent, *binary_manifest_roots, root]
            resolved = next((found for candidate_root in candidates
                             if (found := _resolve_case_insensitive(candidate_root, ref)) is not None and found.exists()), None)
            if resolved is None:
                missing_refs.append(ref)
                binary_missing_references.append({"script": item["path"].relative_to(root).as_posix(), "reference": ref})
        binary_script_report.append({
            "path": item["path"].relative_to(root).as_posix(),
            **item["summary"],
            "missing_package_references": missing_refs,
            "uninstall_script": "uninstall" in item["path"].name.casefold(),
            "uninstall_target_files": item["summary"].get("uninstall_target_files", []),
            "is_manifest_endscript": item["path"].relative_to(root).as_posix() in binary_entry_paths,
        })

    binary_file_moves = []
    for item in binary_script_report:
        if item.get("uninstall_script"):
            continue
        for operation in item.get("move_file_operations", []):
            candidates = [root / Path(_safe_package_path(item["path"])).parent, *binary_manifest_roots, root]
            source_path = next((found for candidate_root in candidates
                                if (found := _resolve_case_insensitive(candidate_root, operation["source"])) is not None and found.is_file()), None)
            binary_file_moves.append({
                "script": item["path"],
                "source": source_path.relative_to(root).as_posix() if source_path else operation["source"],
                "source_exists": bool(source_path),
                "destination": operation["destination"],
            })

    mwps = []
    mwps = []
    for p in files:
        if p.suffix.casefold() == ".mwps":
            text = read_text(p)
            directives = []
            for line_no, raw in enumerate(text.splitlines(), 1):
                line = raw.strip()
                if not line or line.startswith(("#", "//", ";")):
                    continue
                head = line.split(None, 1)[0].casefold()
                if head in {"memfile", "vpak", "patch"}:
                    directives.append({"line": line_no, "command": head, "raw": line})
            mwps.append({
                "path": p.relative_to(root).as_posix(),
                "directive_counts": _count_commands(directives),
                "directives": directives,
            })

    ed_roots = [p for p in files if any(part.casefold() == "ed files" for part in p.relative_to(root).parts)]
    ed_payload = []
    for p in ed_roots:
        if p.suffix.casefold() == ".bak":
            continue
        parts = list(p.relative_to(root).parts)
        index = next(i for i, part in enumerate(parts) if part.casefold() == "ed files")
        ed_payload.append({
            "source": p.relative_to(root).as_posix(),
            "ed_relative": "/".join(parts[index + 1:]),
        })

    replacement_files = [r for r in rels if "/replace/addons/" in ("/" + r.casefold() + "/") or r.casefold().startswith("replace/addons/")]
    legacy_modloader_payload = [r for r in rels if "/modloader/addons/" in ("/" + r.casefold() + "/")]
    modern_modloader_payload = [
        r for r in rels
        if r.casefold().startswith("modloader/")
        and len(Path(r).parts) >= 4
        and any(part.casefold() in {"cars", "frontend", "global", "scripts"} for part in Path(r).parts[2:-1])
    ]

    car_ids = set(nfsms["car_collection_ids"]) | set(amod["car_collection_ids"])
    for item in binary_script_report:
        text = "\n".join(c["raw"] for c in item["commands"])
        for m in re.finditer(r"(?:CARS[\\/])([A-Z0-9_]+)[\\/]", text, re.I):
            car_ids.add(m.group(1).upper())
    for r in rels:
        m = re.search(r"(?:^|/)(?:_Main/)?CARS/([A-Z0-9_]+)/GEOMETRY\.BIN$", r, re.I)
        if m:
            car_ids.add(m.group(1).upper())
    for r in rels:
        m = re.search(r"(?:^|/)([A-Z0-9_]+)\.ini$", r, re.I)
        if m and not m.group(1).startswith("_") and ("unlimiterdata" in r.casefold() or "_settings" in r.casefold()):
            car_ids.add(m.group(1).upper())

    unlimiter_configs = [
        r for r in rels
        if r.casefold().endswith(".ini")
        and ("unlimiterdata/" in r.casefold() or ("_settings/" in r.casefold() and Path(r).stem.upper() in car_ids))
    ]
    save_patcher_files = [r for r in rels if r.casefold().endswith(".ini") and ("savepatch" in r.casefold() or "save patcher" in r.casefold())]
    script_model_targets = {x["destination"].replace("\\", "/").casefold() for x in nfsms.get("file_copy_operations", [])}
    script_model_targets.update(x.casefold() for x in binary_target_game_files if x.casefold().startswith(("cars/", "scripts/unlimiterdata/")))
    direct_model_payload = []
    for rel in rels:
        normalized = rel.replace("\\", "/")
        low = normalized.casefold()
        if low.startswith("cars/"):
            destination = normalized
        elif low.startswith("unlimiterdata/"):
            destination = "scripts/UnlimiterData/" + normalized.split("/", 1)[1]
        elif low.startswith("scripts/unlimiterdata/"):
            destination = normalized
        else:
            continue
        if destination.casefold() not in script_model_targets:
            direct_model_payload.append({"source": rel, "destination": destination})
    geometry_dirs = {str(Path(r).parent).casefold() for r in rels if Path(r).name.casefold() == "geometry.bin"}
    texture_dirs = {str(Path(r).parent).casefold() for r in rels if Path(r).name.casefold() == "textures.bin"}
    model_directories = sorted(geometry_dirs & texture_dirs)
    has_model_files = bool(model_directories)
    has_binary = bool(binary_manifests or binary_scripts)
    has_vlt = bool(nfsms_files or amod_files)
    has_ed = bool(ed_payload)
    has_mwps = bool(mwps)
    has_modloader_replace = bool(replacement_files or (legacy_modloader_payload and has_mwps))
    has_nf_mw_ml_payload = bool(modern_modloader_payload or (legacy_modloader_payload and not has_mwps))

    profiles: list[dict[str, Any]] = []
    if has_model_files and (has_vlt or has_binary):
        profiles.append({
            "id": "unlimiter_addon",
            "label": "Unlimiter add-on car",
            "requires": ["NFSMW Unlimiter", *( ["Binary User Mode"] if has_binary else []), *( ["Attribulina Mod Installer or compatible VLT tool"] if has_vlt else [])],
            "components": [x for x, yes in (("model files", has_model_files), ("Binary package", has_binary), ("VLT/NFSMS/AMOD database scripts", has_vlt), ("Unlimiter per-car configuration", bool(unlimiter_configs)), ("Ed configuration/resources", has_ed)) if yes],
        })
    elif has_model_files and unlimiter_configs:
        warnings.append({"code": "MISSING_CAR_REGISTRATION_SCRIPT", "message": "Model and Unlimiter config files are present, but no NFSMS/AMOD or Binary registration script was found; this package is not safe to install as a complete add-on car."})
    if has_modloader_replace or has_mwps:
        profiles.append({
            "id": "classic_modloader_replacement",
            "label": "Classic ModLoader replacement car",
            "requires": ["Classic NFSMW ModLoader (d3d9.dll + modloader.ini)"],
            "components": [x for x, yes in (("replacement payload", has_modloader_replace), ("MWPS patches", has_mwps)) if yes],
        })
    if has_nf_mw_ml_payload:
        profiles.append({"id": "nfsmw_modular_loader", "label": "NFSMW-ML per-mod folder", "requires": ["NFSMW-ML ASI loader"], "components": ["modloader per-mod folder"]})
    if has_ed and not any(p["id"] == "unlimiter_addon" for p in profiles):
        profiles.append({"id": "ed_pack", "label": "Ed configuration/resource pack", "requires": ["Ed for NFSMW"], "components": ["Ed configuration/resources"]})

    if len(profiles) > 1:
        warnings.append({"code": "MULTIPLE_INSTALL_PROFILES", "message": "The archive contains more than one installation route. Choose one; do not install all profiles together."})
    readmes = [p for p in files if p.name.casefold() in {"readme.txt", "readme.md", "readme"}]
    readme_text = "\n".join(read_text(p) for p in readmes)
    tool_requirements: dict[str, str] = {}
    binary_req = re.search(r"Binary\s*(?:\(|v|version)?\s*(\d+(?:\.\d+){1,2})([^\n]{0,35})", readme_text, re.I)
    if binary_req:
        suffix = binary_req.group(2).casefold()
        if "higher" in suffix:
            tool_requirements["Binary"] = binary_req.group(1) + " or higher (required)"
        elif re.search(r"requires?[^\n]{0,40}Binary|Binary[^\n]{0,40}required", readme_text, re.I):
            tool_requirements["Binary"] = binary_req.group(1) + " (required)"
        else:
            tool_requirements["Binary"] = binary_req.group(1) + " (credited version; minimum not stated)"
    vlt_req = re.search(r"(?:Vlt-Ed|VltEd|VLT-Ed)\s*(\d+(?:\.\d+){0,2})", readme_text, re.I)
    if vlt_req:
        tool_requirements["VltEd"] = vlt_req.group(1) + " (required by readme; Attribulina alternative used by this workflow)"
    unlimiter_req = re.search(r"Unlimiter\s*v?(\d+(?:\.\d+){0,2})", readme_text, re.I)
    if unlimiter_req:
        tool_requirements["Unlimiter"] = unlimiter_req.group(1) + " (required)"
    binary_script_versions = []
    for item in binary_script_report:
        pth = root / _safe_package_path(item["path"])
        for match in re.finditer(r"(?im)^\s*version\s+([0-9]+(?:\.[0-9]+){1,2})", read_text(pth)):
            binary_script_versions.append({"file": item["path"], "version": match.group(1)})
    if binary_script_versions and "Binary" not in tool_requirements:
        tool_requirements["Binary"] = binary_script_versions[0]["version"] + " (package script version; minimum tool version not confirmed)"
    if re.search(r"modloader.{0,50}replac|replac.{0,50}modloader", readme_text, re.I) and any(p["id"] == "unlimiter_addon" for p in profiles) and not has_modloader_replace:
        warnings.append({"code": "README_INSTALL_MODE_CONFLICT", "message": "README mentions a ModLoader replacement, but the archive also contains an Unlimiter add-on install script and no clear REPLACE payload. Confirm the intended variant before installing."})
    if has_modloader_replace and any(p["id"] == "unlimiter_addon" for p in profiles):
        warnings.append({"code": "ALTERNATIVE_INSTALLERS", "message": "The archive contains both add-on and Classic ModLoader replacement paths. They are alternatives, not cumulative steps."})
    if nfsms["missing_references"]:
        warnings.append({"code": "MISSING_NFSMS_REFERENCES", "message": f"{len(nfsms['missing_references'])} referenced NFSMS script(s) could not be resolved."})
    if nfsms["unsafe_references"]:
        warnings.append({"code": "UNSAFE_NFSMS_REFERENCES", "message": f"{len(nfsms['unsafe_references'])} unsafe NFSMS reference(s) were found."})
    if nfsms.get("relative_path_fallbacks"):
        warnings.append({"code": "NFSMS_NESTED_PATH_FALLBACK", "message": "Some nested script paths only resolved relative to the nested file, not the documented main-script directory."})
    if nfsms.get("ambiguous_script_references"):
        warnings.append({"code": "NFSMS_AMBIGUOUS_SCRIPT_PATH", "message": "Some nested script paths resolve to different files from the main-script and nested-script directories; main-script-relative resolution was selected."})
    if amod["missing_references"]:
        warnings.append({"code": "MISSING_AMOD_REFERENCES", "message": f"{len(amod['missing_references'])} AMOD include reference(s) could not be resolved."})
    if amod["unsafe_references"]:
        warnings.append({"code": "UNSAFE_AMOD_REFERENCES", "message": f"{len(amod['unsafe_references'])} unsafe AMOD include reference(s) were found."})
    if amod["cycles"]:
        warnings.append({"code": "AMOD_INCLUDE_CYCLE", "message": f"AMOD include cycle(s) were detected: {', '.join(amod['cycles'])}"})
    if amod_files and not amod["entrypoints"]:
        warnings.append({"code": "AMOD_NO_ENTRYPOINT", "message": "AMOD scripts were found but no independent install entry point could be identified (only uninstall scripts or include cycles may be present)."})
    if nfsms_files and not nfsms["entrypoints"]:
        warnings.append({"code": "NFSMS_NO_ENTRYPOINT", "message": "NFSMS scripts were found but no independent install entry point could be identified (only uninstall scripts may be present)."})
    if nfsms.get("entrypoints") and amod.get("entrypoints"):
        warnings.append({"code": "MULTIPLE_DATABASE_SCRIPT_FORMATS", "message": "Both NFSMS and AMOD install entry points are present; the installer will not guess which database installer to run."})
    if binary_missing_references:
        warnings.append({"code": "MISSING_BINARY_REFERENCES", "message": f"{len(binary_missing_references)} Binary package reference(s) could not be resolved."})
    if save_patcher_files:
        warnings.append({"code": "SAVE_PATCHER_MANUAL_ONLY", "message": "A save/profile patcher configuration is present. The installer will not modify career saves automatically."})
    for manifest in binary_manifests:
        if not manifest.get("valid") or not manifest.get("endscript_exists"):
            warnings.append({"code": "INVALID_BINARY_MANIFEST", "message": f"Binary manifest {manifest['path']} is invalid or its Endscript is missing."})
    if tool_requirements:
        warnings.append({"code": "TOOL_VERSION_REQUIREMENTS", "message": "Package readme/scripts declare tool-version requirements; the installer cannot independently validate all GUI tool versions. Confirm them before continuing."})

    return {
        "schema_version": "1.0",
        "package_root": str(root),
        "file_count": len(files),
        "total_bytes": sum(p.stat().st_size for p in files),
        "car_ids": sorted(car_ids),
        "profiles": profiles,
        "declared_tool_requirements": tool_requirements,
        "components": {
            "model_files_present": has_model_files,
            "model_directories": model_directories,
            "unlimiter_configs": unlimiter_configs,
            "save_patcher_files": save_patcher_files,
            "nfsms": nfsms,
            "amod": amod,
            "amod_scripts": [p.relative_to(root).as_posix() for p in amod_files],
            "direct_model_payload": direct_model_payload,
            "binary_manifests": binary_manifests,
            "binary_scripts": binary_script_report,
            "binary_missing_references": binary_missing_references,
            "binary_file_moves": binary_file_moves,
            "binary_uninstall_available": any("uninstall" in x["path"].casefold() for x in binary_script_report),
            "binary_target_game_files": sorted(binary_target_game_files | {p for m in binary_manifests for p in m.get("game_files", [])} | {x.get("File") for m in binary_manifests for x in m.get("links", []) if x.get("File")}),
            "binary_uninstall_target_game_files": sorted({p for item in binary_script_report if item.get("uninstall_script") for p in item.get("uninstall_target_files", [])}),
            "mwps": mwps,
            "ed_payload": ed_payload,
            "replacement_payload": replacement_files,
            "legacy_modloader_payload": legacy_modloader_payload,
            "modern_modloader_payload": modern_modloader_payload,
        },
        "warnings": warnings,
        "safety": {
            "writes_performed": False,
            "automatic_installation_approved": False,
            "note": "Analysis only. Binary, VLT, Ed and ModLoader operations have distinct execution requirements; do not treat file presence as proof of a working in-game car.",
        },
    }
