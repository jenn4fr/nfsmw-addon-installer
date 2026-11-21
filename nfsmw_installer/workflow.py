"""Guided, journaled installer orchestration for NFS MW addon packages.

Binary and Ed are GUI applications. AttribulinaModInstaller is also a guided
GUI installer. This module orchestrates those supported tools, backs up their
targets, verifies file/database evidence, and never pretends that a GUI stage
or in-game car test succeeded without user confirmation.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from .package_analysis import analyze_package


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return "MISSING"
    for path in sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.relative_to(root).as_posix().casefold()):
        rel = path.relative_to(root).as_posix().encode("utf-8", errors="replace")
        digest.update(len(rel).to_bytes(4, "little"))
        digest.update(rel)
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def _snapshot_directory(target: Path, backup_root: Path, journal: dict[str, Any], label: str) -> dict[str, Any]:
    record: dict[str, Any] = {"path": str(target), "label": label, "existed": target.is_dir()}
    if target.is_dir():
        backup = backup_root / f"directory-{label}" / target.name
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(target, backup, dirs_exist_ok=True)
        record["backup"] = str(backup)
        record["before_tree_hash"] = _tree_hash(target)
    journal.setdefault("directory_snapshots", []).append(record)
    return record


def _safe_relative(value: str) -> Path:
    normalized = value.replace("\\", "/")
    p = PurePosixPath(normalized)
    if p.is_absolute() or any(part in {"..", ""} for part in p.parts) or (p.parts and ":" in p.parts[0]):
        raise ValueError(f"Unsafe relative path: {value}")
    return Path(*p.parts)


def _resolve_case_insensitive(root: Path, rel: str) -> Path:
    rel_path = _safe_relative(rel)
    current = root
    for index, part in enumerate(rel_path.parts):
        if not current.is_dir():
            return current.joinpath(*rel_path.parts[index:])
        matches = [p for p in current.iterdir() if p.name.casefold() == part.casefold()]
        if matches:
            current = sorted(matches, key=lambda p: p.name)[0]
        else:
            current = current / part
    return current


def detect_game_capabilities(game_root: str | Path) -> dict[str, Any]:
    root = Path(game_root).expanduser().resolve()
    scripts = root / "scripts"
    speed = root / "speed.exe"
    classic = (root / "d3d9.dll").is_file() and (root / "modloader.ini").is_file()
    unlimiter = (scripts / "NFSMWUnlimiter.asi").is_file()
    modular_loader = (scripts / "NFSMW-ML.asi").is_file()
    asi_loader = (root / "dinput8.dll").is_file()
    return {
        "game_root": str(root),
        "exists": root.is_dir(),
        "speed_exe": speed.is_file(),
        "speed_exe_size": speed.stat().st_size if speed.is_file() else None,
        "is_mw_1_3_size": speed.is_file() and speed.stat().st_size == 6_029_312,
        "classic_modloader": classic,
        "unlimiter": unlimiter,
        "nfsmw_modular_loader": modular_loader,
        "asi_loader": asi_loader,
        "loader_conflict": classic and (unlimiter or asi_loader),
    }


def _select_profile(analysis: dict[str, Any], profile: str | None,
                    capabilities: dict[str, Any] | None = None) -> dict[str, Any]:
    profiles = analysis.get("profiles", [])
    if not profiles:
        raise ValueError("No supported installation profile was detected in this package")
    if profile:
        found = [p for p in profiles if p["id"] == profile]
        if not found:
            choices = ", ".join(p["id"] for p in profiles)
            raise ValueError(f"Profile {profile!r} is not available. Detected: {choices}")
        return found[0]
    if len(profiles) == 1:
        return profiles[0]
    if capabilities:
        compatible = []
        for candidate in profiles:
            kind = candidate["id"]
            if kind == "unlimiter_addon" and capabilities.get("unlimiter") and not capabilities.get("loader_conflict"):
                compatible.append(candidate)
            elif kind == "nfsmw_modular_loader" and capabilities.get("nfsmw_modular_loader") and capabilities.get("asi_loader"):
                compatible.append(candidate)
            elif kind == "classic_modloader_replacement" and capabilities.get("classic_modloader") and not capabilities.get("loader_conflict"):
                compatible.append(candidate)
        if len(compatible) == 1:
            return compatible[0]
        if not compatible:
            raise ValueError("Package has multiple install routes, but none matches the target game's detected loaders. Pass an explicit --profile only after fixing the target compatibility.")
        choices = ", ".join(f"{p['id']} ({p['label']})" for p in compatible)
        raise ValueError(f"More than one install route is compatible with this target. Choose --profile from: {choices}")
    choices = ", ".join(f"{p['id']} ({p['label']})" for p in profiles)
    raise ValueError(f"Package has multiple install routes. Choose --profile from: {choices}")


def _entry_script(package_root: Path, analysis: dict[str, Any]) -> Path | None:
    components = analysis["components"]
    nfsms_entries = components.get("nfsms", {}).get("entrypoints", [])
    amod_entries = components.get("amod", {}).get("entrypoints", [])
    if nfsms_entries and amod_entries:
        raise ValueError(f"Package contains both NFSMS and AMOD install entry points; separate the route: NFSMS={nfsms_entries}, AMOD={amod_entries}")
    entries = nfsms_entries or amod_entries
    if not entries:
        return None
    if len(entries) != 1:
        raise ValueError(f"Multiple database install entry points need a package-specific choice: {entries}")
    return package_root / _safe_relative(entries[0])


def build_workflow_plan(package_root: str | Path, game_root: str | Path,
                        profile: str | None = None, ed_root: str | Path | None = None,
                        car_ids_extra: list[str] | None = None) -> dict[str, Any]:
    package = Path(package_root).expanduser().resolve()
    game = Path(game_root).expanduser().resolve()
    if not package.is_dir():
        raise ValueError(f"Extracted package directory not found: {package}")
    if not game.is_dir():
        raise ValueError(f"Game directory not found: {game}")
    analysis = analyze_package(package)
    capabilities = detect_game_capabilities(game)
    selected = _select_profile(analysis, profile, capabilities)
    profile_id = selected["id"]
    car_ids = sorted(set(analysis["car_ids"]) | {str(x).strip().upper() for x in (car_ids_extra or [])})
    if any(not re.fullmatch(r"[A-Z0-9_]+", x) for x in car_ids):
        raise ValueError("Car IDs must contain only letters, numbers and underscores")
    compatibility: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    compatibility.append({"check": "NFS MW executable", "passed": capabilities["speed_exe"],
                          "reason": "speed.exe must exist in the target game folder"})
    if capabilities["speed_exe"] and not capabilities["is_mw_1_3_size"]:
        # The size is a useful heuristic, not a definitive executable identity check.
        pass

    if profile_id == "unlimiter_addon":
        compatibility.append({"check": "Unlimiter", "passed": capabilities["unlimiter"],
                              "reason": "scripts/NFSMWUnlimiter.asi must exist"})
        compatibility.append({"check": "Addon car ID", "passed": bool(car_ids),
                              "reason": "A pvehicle car ID must be identified for independent database read-back"})
        compatibility.append({"check": "No Classic ModLoader conflict", "passed": not capabilities["loader_conflict"],
                              "reason": "Classic d3d9 ModLoader must not be mixed with the Unlimiter/ASI-loader setup"})
    elif profile_id == "classic_modloader_replacement":
        compatibility.append({"check": "Classic ModLoader", "passed": capabilities["classic_modloader"],
                              "reason": "d3d9.dll and modloader.ini must exist"})
        compatibility.append({"check": "No Unlimiter/ASI-loader conflict", "passed": not (capabilities["unlimiter"] or capabilities["asi_loader"]),
                              "reason": "Classic ModLoader replacement path is kept separate from the Unlimiter/ASI-loader installation"})
    elif profile_id == "nfsmw_modular_loader":
        compatibility.append({"check": "NFSMW-ML", "passed": capabilities["nfsmw_modular_loader"],
                              "reason": "scripts/NFSMW-ML.asi must exist"})
        compatibility.append({"check": "ASI loader", "passed": capabilities["asi_loader"],
                              "reason": "dinput8.dll must be present for NFSMW-ML"})

    binary_manifests = analysis["components"]["binary_manifests"] if profile_id == "unlimiter_addon" else []
    binary_file_moves = analysis["components"].get("binary_file_moves", []) if profile_id == "unlimiter_addon" else []
    if capabilities["speed_exe"] and not capabilities["is_mw_1_3_size"]:
        warnings.append({"code": "SPEED_EXE_SIZE_UNUSUAL", "message": "speed.exe is present but its size differs from the known 1.3 reference (6,029,312 bytes); verify game version manually."})
    nfsms_entry = _entry_script(package, analysis) if profile_id == "unlimiter_addon" else None
    ed_files = analysis["components"]["ed_payload"] if profile_id == "unlimiter_addon" else []
    if ed_files and not ed_root:
        compatibility.append({"check": "Ed tool folder", "passed": False,
                              "reason": "This package includes Ed Files; pass --ed-root pointing to the folder containing Ed.exe"})
    elif ed_files:
        ed_path = Path(ed_root).expanduser().resolve()
        compatibility.append({"check": "Ed.exe", "passed": (ed_path / "Ed.exe").is_file(),
                              "reason": f"Expected {(ed_path / 'Ed.exe')}"})

    binary_targets: set[str] = set()
    for manifest in binary_manifests:
        if not manifest.get("valid") or not manifest.get("endscript_exists"):
            compatibility.append({"check": "Binary manifest", "passed": False,
                                  "reason": f"Invalid manifest or missing Endscript: {manifest['path']}"})
        binary_targets.update(analysis["components"].get("binary_target_game_files", []))
        for rel in sorted(set(manifest.get("game_files", [])) | {x.get("File") for x in manifest.get("links", []) if x.get("File")}):
            target = _resolve_case_insensitive(game, rel)
            compatibility.append({"check": f"Binary dependency {rel}", "passed": target.is_file(),
                                  "reason": "Binary installer expects this game data file to exist"})
    binary_missing = analysis["components"].get("binary_missing_references", [])
    if binary_missing:
        compatibility.append({"check": "Binary package references", "passed": False,
                              "reason": f"{len(binary_missing)} package source/reference file(s) are missing"})
    missing_moves = [x for x in binary_file_moves if not x.get("source_exists")]
    if missing_moves:
        compatibility.append({"check": "Binary move_file sources", "passed": False,
                              "reason": f"{len(missing_moves)} Binary move_file source(s) are missing"})
    for rel in sorted(binary_targets):
        if rel.casefold().startswith(("cars/", "scripts/unlimiterdata/")):
            continue
        target = _resolve_case_insensitive(game, rel)
        compatibility.append({"check": f"Binary target {rel}", "passed": target.is_file(),
                              "reason": "Binary script targets this existing game data file"})
    if profile_id == "unlimiter_addon" and (analysis["components"].get("unlimiter_configs") or any(x.casefold().startswith("scripts/unlimiterdata/") for x in binary_targets)):
        data_dir = _resolve_case_insensitive(game, "scripts/UnlimiterData")
        compatibility.append({"check": "UnlimiterData directory", "passed": data_dir.is_dir(),
                              "reason": "Unlimiter per-car data directory must exist"})

    nfsms = analysis["components"]["nfsms"] if profile_id == "unlimiter_addon" else None
    if nfsms or analysis["components"].get("amod_scripts"):
        for rel in ("GLOBAL/ATTRIBUTES.BIN", "GLOBAL/FE_ATTRIB.BIN"):
            target = _resolve_case_insensitive(game, rel)
            compatibility.append({"check": f"VLT database {rel}", "passed": target.is_file(),
                                  "reason": "Required game database file must exist before applying car registration"})
    script_targets = []
    amod = analysis["components"].get("amod", {}) if profile_id == "unlimiter_addon" else {}
    if profile_id == "unlimiter_addon" and (analysis["components"].get("nfsms", {}).get("scripts") or analysis["components"].get("amod_scripts")) and not nfsms_entry:
        compatibility.append({"check": "Database install entry point", "passed": False,
                              "reason": "No unambiguous NFSMS/AMOD install entry point was identified"})
    if amod.get("missing_references") or amod.get("unsafe_references") or amod.get("cycles") or (analysis["components"].get("amod_scripts") and not amod.get("entrypoints")):
        compatibility.append({"check": "AMOD include graph", "passed": False,
                              "reason": "Missing, unsafe or cyclic AMOD includes/entry points exist"})
    if nfsms:
        for operation in nfsms.get("file_copy_operations", []):
            script_targets.append(operation["destination"])
            if not operation.get("source_exists"):
                compatibility.append({"check": "NFSMS file_copy source", "passed": False,
                                      "reason": f"Missing source {operation['source']} referenced by {operation['script']}:{operation['line']}"})
        if nfsms.get("missing_references") or nfsms.get("unsafe_references"):
            compatibility.append({"check": "NFSMS include graph", "passed": False,
                                  "reason": "Missing or unsafe script references exist"})

    modloader_payload = []
    unmapped_legacy_modloader_payload = []
    direct_model_payload = analysis["components"].get("direct_model_payload", []) if profile_id == "unlimiter_addon" else []
    if profile_id == "classic_modloader_replacement":
        legacy_files = analysis["components"].get("legacy_modloader_payload", [])
        for rel in [*analysis["components"].get("replacement_payload", []), *legacy_files]:
            # Both REPLACE/ADDONS/<payload> and Modloader/ADDONS/<payload>
            # become the classic game-root ADDONS/<payload> tree.
            normalized = rel.replace("\\", "/")
            marker = "/REPLACE/ADDONS/"
            idx = ("/" + normalized).casefold().find(marker.casefold())
            if idx >= 0:
                relative = normalized[idx + len(marker):]
            else:
                parts = normalized.split("/")
                try:
                    addon_index = next(i for i, part in enumerate(parts) if part.casefold() == "addons")
                    relative = "/".join(parts[addon_index + 1:])
                except StopIteration:
                    continue
            modloader_payload.append({"source": rel, "destination": f"ADDONS/{relative}"})
    elif profile_id == "nfsmw_modular_loader":
        for rel in analysis["components"].get("modern_modloader_payload", []):
            modloader_payload.append({"source": rel, "destination": rel})
        package_slug = re.sub(r"[^A-Za-z0-9_-]+", "_", package.name).strip("_") or "AddonMod"
        for rel in analysis["components"].get("legacy_modloader_payload", []):
            parts = rel.replace("\\", "/").split("/")
            try:
                idx = next(i for i, part in enumerate(parts) if part.casefold() == "addons")
                group = parts[idx + 1].upper()
                tail = parts[idx + 2:]
            except (StopIteration, IndexError):
                continue
            game_folder = {"CARS_REPLACE": "CARS", "CARS": "CARS", "FRONTEND": "FRONTEND",
                           "GLOBAL": "GLOBAL", "LANGUAGES": "LANGUAGES", "SCRIPTS": "scripts"}.get(group)
            if not game_folder:
                unmapped_legacy_modloader_payload.append(rel)
                continue
            destination = "/".join(["modloader", package_slug, game_folder, *tail])
            modloader_payload.append({"source": rel, "destination": destination})

    if profile_id == "nfsmw_modular_loader" and unmapped_legacy_modloader_payload:
        compatibility.append({"check": "Legacy ModLoader payload mapping", "passed": False,
                              "reason": "Unsupported Modloader/ADDONS subfolder(s): " + ", ".join(unmapped_legacy_modloader_payload)})

    return {
        "schema_version": "1.1",
        "package_root": str(package),
        "package_file_count": analysis["file_count"],
        "package_total_bytes": analysis["total_bytes"],
        "game_root": str(game),
        "profile": selected,
        "profile_selection": "explicit" if profile else ("target_compatible_auto" if len(analysis.get("profiles", [])) > 1 else "single_detected_profile"),
        "capabilities": capabilities,
        "compatibility_checks": compatibility,
        "binary_manifests": binary_manifests,
        "binary_file_moves": binary_file_moves,
        "binary_target_paths": sorted(binary_targets),
        "nfsms_entrypoint": str(nfsms_entry) if nfsms_entry else None,
        "nfsms_entrypoint_relative": str(nfsms_entry.relative_to(package).as_posix()) if nfsms_entry else None,
        "database_script_entrypoint": str(nfsms_entry) if nfsms_entry else None,
        "database_script_entrypoint_relative": str(nfsms_entry.relative_to(package).as_posix()) if nfsms_entry else None,
        "database_script_format": nfsms_entry.suffix.casefold().lstrip(".") if nfsms_entry else None,
        "nfsms_target_paths": sorted(set(script_targets)),
        "nfsms_file_copy_operations": nfsms.get("file_copy_operations", []) if nfsms else [],
        "direct_model_payload": direct_model_payload,
        "ed_root": str(Path(ed_root).expanduser().resolve()) if ed_root else None,
        "ed_payload": ed_files,
        "modloader_payload": modloader_payload,
        "unmapped_legacy_modloader_payload": unmapped_legacy_modloader_payload,
        "car_ids": car_ids,
        "warnings": [*[w for w in analysis["warnings"] if profile_id == "unlimiter_addon" or w.get("code") != "TOOL_VERSION_REQUIREMENTS"], *warnings],
        "declared_tool_requirements": analysis.get("declared_tool_requirements", {}) if profile_id == "unlimiter_addon" else {},
        "save_patcher_files": analysis["components"].get("save_patcher_files", []),
        "ready": bool(compatibility) and all(x["passed"] for x in compatibility),
        "writes_performed": False,
    }


def _backup_file(source: Path, game_root: Path, backup_root: Path, journal: dict[str, Any], label: str) -> None:
    if not source.exists() or not source.is_file():
        journal["snapshots"].append({"path": str(source), "existed": False, "label": label})
        return
    try:
        relative = source.relative_to(game_root)
        backup_path = backup_root / label / relative
    except ValueError:
        backup_path = backup_root / label / source.name
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, backup_path)
    journal["snapshots"].append({"path": str(source), "existed": True,
                                 "backup": str(backup_path), "sha256": sha256_file(source), "label": label})


def _snapshot_targets(game: Path, package: Path, plan: dict[str, Any], backup_root: Path,
                      journal: dict[str, Any]) -> None:
    rels = set(plan.get("binary_target_paths", []))
    rels.update(plan.get("nfsms_target_paths", []))
    if plan["profile"]["id"] == "unlimiter_addon" and plan.get("nfsms_entrypoint"):
        rels.update({"GLOBAL/ATTRIBUTES.BIN", "GLOBAL/FE_ATTRIB.BIN"})
    if plan.get("ed_payload"):
        rels.update({"FRONTEND/FRONTA.BUN", "FRONTEND/FRONTB.LZC", "GLOBAL/GLOBALB.LZC",
                     "GLOBAL/ATTRIBUTES.BIN", "GLOBAL/FE_ATTRIB.BIN", "LANGUAGES/Labels.bin", "LANGUAGES/Labels_Global.bin"})
    if plan["profile"]["id"] in {"classic_modloader_replacement", "nfsmw_modular_loader"}:
        rels.update(item["destination"] for item in plan.get("modloader_payload", []))
    rels.update(item["destination"] for item in plan.get("direct_model_payload", []))
    for rel in sorted(rels):
        target = _resolve_case_insensitive(game, rel)
        _backup_file(target, game, backup_root, journal, "pre-install")


def _copy_ed_payload(package: Path, ed_root: Path, plan: dict[str, Any], backup_root: Path,
                     journal: dict[str, Any], overwrite: bool) -> None:
    for item in plan["ed_payload"]:
        if item["source"].casefold().endswith(".bak"):
            continue
        source = package / _safe_relative(item["source"])
        if not source.is_file():
            raise FileNotFoundError(f"Ed package file missing: {source}")
        dest_rel = _safe_relative(item["ed_relative"])
        dest = (ed_root / dest_rel).resolve()
        if ed_root not in dest.parents and dest != ed_root:
            raise ValueError(f"Ed destination escapes Ed root: {dest}")
        if dest.exists():
            if not overwrite:
                raise FileExistsError(f"Ed destination exists; rerun with --overwrite after review: {dest}")
            backup_path = backup_root / "ed" / dest_rel
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, backup_path)
            journal["snapshots"].append({"path": str(dest), "existed": True, "backup": str(backup_path),
                                         "sha256": sha256_file(dest), "label": "ed"})
        else:
            journal["snapshots"].append({"path": str(dest), "existed": False, "label": "ed"})
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        journal["copied_files"].append({"source": str(source), "destination": str(dest),
                                        "sha256": sha256_file(dest), "label": "ed"})


def _copy_modloader_payload(package: Path, game: Path, plan: dict[str, Any], backup_root: Path,
                            journal: dict[str, Any], overwrite: bool) -> None:
    for item in plan.get("modloader_payload", []):
        source = package / _safe_relative(item["source"])
        dest = game / _safe_relative(item["destination"])
        if not source.is_file():
            raise FileNotFoundError(f"ModLoader payload missing: {source}")
        if dest.exists():
            if not overwrite:
                raise FileExistsError(f"Destination exists; rerun with --overwrite after review: {dest}")
            backup_path = backup_root / "game" / _safe_relative(item["destination"])
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, backup_path)
            journal["snapshots"].append({"path": str(dest), "existed": True, "backup": str(backup_path),
                                         "sha256": sha256_file(dest), "label": "game"})
        else:
            journal["snapshots"].append({"path": str(dest), "existed": False, "label": "game"})
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        journal["copied_files"].append({"source": str(source), "destination": str(dest),
                                        "sha256": sha256_file(dest), "label": "game"})


def _launch_tool(executable: Path, args: list[str], label: str,
                 input_fn: Callable[[str], str], launcher: Callable[..., Any],
                 instructions: str = "") -> None:
    if not executable.is_file():
        raise FileNotFoundError(f"{label} executable not found: {executable}")
    launcher([str(executable), *args])
    input_fn(
        f"\n{label} has been opened. {instructions} "
        "When the tool reports success, close or return here and press Enter. "
        "If it reports an error, press Ctrl+C instead. "
    )


def _changed_paths(game: Path, rels: list[str], snapshots: list[dict[str, Any]], label: str) -> list[str]:
    before = {x["path"]: x for x in snapshots if x.get("label") == label}
    changed = []
    for rel in rels:
        target = _resolve_case_insensitive(game, rel)
        prior = before.get(str(target))
        if not target.is_file():
            continue
        now = sha256_file(target)
        if prior is None or not prior.get("existed") or prior.get("sha256") != now:
            changed.append(rel)
    return changed


def execute_guided_install(package_root: str | Path, game_root: str | Path, *,
                           profile: str | None = None, car_ids_extra: list[str] | None = None,
                           binary_exe: str | Path | None = None,
                           attribulina_installer: str | Path | None = None,
                           attribcli: str | Path | None = None,
                           ed_root: str | Path | None = None, ed_exe: str | Path | None = None,
                           overwrite: bool = False, backup_root: str | Path | None = None,
                           input_fn: Callable[[str], str] = input,
                           launcher: Callable[..., Any] = subprocess.Popen,
                           confirm_game_test: bool = True) -> dict[str, Any]:
    package = Path(package_root).expanduser().resolve()
    game = Path(game_root).expanduser().resolve()
    plan = build_workflow_plan(package, game, profile=profile, ed_root=ed_root, car_ids_extra=car_ids_extra)
    failed = [x for x in plan["compatibility_checks"] if not x["passed"]]
    if failed:
        details = "; ".join(f"{x['check']}: {x['reason']}" for x in failed)
        raise RuntimeError(f"Preflight failed; no installation changes were made. {details}")

    selected = plan["profile"]["id"]
    binary_manifests = plan.get("binary_manifests", [])
    if binary_manifests and not binary_exe:
        raise ValueError("This package needs Binary User Mode. Pass --binary PATH to Binary.exe")
    if plan.get("nfsms_entrypoint") and selected == "unlimiter_addon" and not attribulina_installer:
        raise ValueError("This package needs AttribulinaModInstaller.exe. Pass --attribulina-installer PATH")
    if attribulina_installer and not attribcli:
        sibling_cli = Path(attribulina_installer).expanduser().resolve().with_name("attribcli.exe")
        if sibling_cli.is_file():
            attribcli = sibling_cli
    if plan.get("ed_payload") and not ed_exe:
        candidate = Path(ed_root) / "Ed.exe" if ed_root else None
        if not candidate or not candidate.is_file():
            raise ValueError("This package includes Ed Files. Pass --ed-exe PATH to Ed.exe")
        ed_exe = candidate
    if binary_manifests:
        binary_path = Path(binary_exe).expanduser().resolve()
        if not binary_path.is_file():
            raise FileNotFoundError(f"Binary.exe not found: {binary_path}")
        if "binarius" in binary_path.name.casefold():
            raise ValueError("This package needs MaxHwoy's Binary.exe, not Binarius.exe")
    if selected == "unlimiter_addon" and not attribcli:
        raise ValueError("attribcli.exe is required for independent pvehicle database read-back. Pass --attribcli PATH or add it to --tools-root.")
    if plan.get("nfsms_entrypoint") and selected == "unlimiter_addon":
        installer_path = Path(attribulina_installer).expanduser().resolve()
        if not installer_path.is_file():
            raise FileNotFoundError(f"AttribulinaModInstaller.exe not found: {installer_path}")
    if plan.get("ed_payload"):
        ed_path_exe = Path(ed_exe).expanduser().resolve()
        if not ed_path_exe.is_file():
            raise FileNotFoundError(f"Ed.exe not found: {ed_path_exe}")
    if attribcli and not Path(attribcli).expanduser().resolve().is_file():
        raise FileNotFoundError(f"attribcli.exe not found: {attribcli}")

    # Check every file destination before any external tool or copy operation.
    conflicts = []
    if selected in {"classic_modloader_replacement", "nfsmw_modular_loader"}:
        for item in plan.get("modloader_payload", []):
            if _resolve_case_insensitive(game, item["destination"]).exists() and not overwrite:
                conflicts.append(item["destination"])
    else:
        for rel in plan.get("nfsms_target_paths", []):
            if _resolve_case_insensitive(game, rel).exists() and not overwrite:
                conflicts.append(rel)
        for item in plan.get("direct_model_payload", []):
            if _resolve_case_insensitive(game, item["destination"]).exists() and not overwrite:
                conflicts.append(item["destination"])
        for rel in plan.get("binary_target_paths", []):
            if rel.casefold().startswith(("cars/", "scripts/unlimiterdata/")) and _resolve_case_insensitive(game, rel).exists() and not overwrite:
                conflicts.append(rel)
    if plan.get("ed_payload") and ed_root:
        ed_base = Path(ed_root).expanduser().resolve()
        for item in plan["ed_payload"]:
            if item["source"].casefold().endswith(".bak"):
                continue
            if (ed_base / _safe_relative(item["ed_relative"])).exists() and not overwrite:
                conflicts.append(f"Ed/{item['ed_relative']}")
    if conflicts:
        raise FileExistsError("Existing destinations require explicit --overwrite (backups are made first): " + ", ".join(sorted(set(conflicts))))

    requirements = plan.get("declared_tool_requirements", {})
    for tool_name in ("Unlimiter", "Binary"):
        requirement = requirements.get(tool_name)
        if requirement and ("required" in requirement.casefold() or "or higher" in requirement.casefold()):
            answer = input_fn(f"Package declares {tool_name} version requirement: {requirement}. Have you confirmed your installed {tool_name} meets this requirement? [y/N]: ").strip().casefold()
            if answer not in {"y", "yes"}:
                raise RuntimeError(f"{tool_name} version requirement was not confirmed; no installation changes were made")

    vlt_requirement = requirements.get("VltEd")
    if vlt_requirement and plan.get("database_script_format") == "nfsms":
        answer = input_fn(
            f"The package Readme lists {vlt_requirement}. This workflow will apply its NFSMS script with Attribulina Mod Installer instead of VltEd. Do you accept this substitution? [y/N]: "
        ).strip().casefold()
        if answer not in {"y", "yes"}:
            raise RuntimeError("Attribulina-for-VltEd substitution was not accepted; no installation changes were made")

    run_id = time.strftime("%Y%m%d-%H%M%S")
    backup = Path(backup_root).expanduser().resolve() if backup_root else game / "_nfsmw_installer_backups" / run_id
    protected_game_trees = [game / name for name in ("GLOBAL", "FRONTEND", "CARS", "scripts", "ADDONS", "modloader", "LANGUAGES")]
    def _within(path: Path, parent: Path) -> bool:
        return path == parent or parent in path.parents
    if backup == game or _within(game, backup) or _within(package, backup) or _within(backup, package):
        raise ValueError("Backup root must be a dedicated folder, not the game root, package root, or a parent of either")
    if any(_within(backup, tree.resolve()) for tree in protected_game_trees):
        raise ValueError("Backup root cannot be inside a game directory that the installer snapshots or modifies (GLOBAL/FRONTEND/CARS/scripts/ADDONS/modloader/LANGUAGES)")
    if ed_root and (_within(backup, Path(ed_root).expanduser().resolve()) or _within(Path(ed_root).expanduser().resolve(), backup)):
        raise ValueError("Backup root must be separate from the Ed tool folder")
    backup.mkdir(parents=True, exist_ok=True)
    speed_exe = _resolve_case_insensitive(game, "speed.exe")
    journal: dict[str, Any] = {
        "schema_version": "1.1", "kind": "guided_install", "installer_version": "0.6.1", "run_id": run_id,
        "package_root": str(package), "package_tree_sha256": _tree_hash(package),
        "package_file_count": plan["package_file_count"], "package_total_bytes": plan["package_total_bytes"],
        "car_ids": plan.get("car_ids", []),
        "game_root": str(game), "speed_exe_sha256": sha256_file(speed_exe) if speed_exe.is_file() else None,
        "profile": selected, "backup_root": str(backup),
        "tools": {"binary": str(binary_exe) if binary_exe else None,
                  "attribulina_mod_installer": str(attribulina_installer) if attribulina_installer else None,
                  "attribcli": str(attribcli) if attribcli else None,
                  "ed": str(ed_exe) if ed_exe else None},
        "declared_tool_requirements": plan.get("declared_tool_requirements", {}),
        "warnings": plan.get("warnings", []),
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "snapshots": [], "directory_snapshots": [], "copied_files": [],
        "stages": [], "status": "in_progress", "in_game_confirmed": False,
    }
    _snapshot_targets(game, package, plan, backup, journal)
    journal_path = backup / "install-run.json"

    def save_journal():
        journal_path.write_text(json.dumps(journal, indent=2), encoding="utf-8")

    save_journal()
    try:
        if selected in {"classic_modloader_replacement", "nfsmw_modular_loader"}:
            _copy_modloader_payload(package, game, plan, backup, journal, overwrite)
            stage_name = "classic_modloader_file_install" if selected == "classic_modloader_replacement" else "nfsmw_ml_mod_install"
            journal["stages"].append({"stage": stage_name, "status": "completed"})
        else:
            if binary_manifests:
                binary = Path(binary_exe).expanduser().resolve()
                manifest = binary_manifests[0]
                manifest_path = package / _safe_relative(manifest["path"])
                expected_moves = []
                for move in plan.get("binary_file_moves", []):
                    source_file = package / _safe_relative(move["source"])
                    expected_moves.append({"source": move["source"], "destination": move["destination"],
                                           "expected_sha256": sha256_file(source_file) if source_file.is_file() else None})
                _launch_tool(
                    binary, [], "Binary User Mode", input_fn, launcher,
                    instructions=(f"In User Mode, open this installer file: {manifest_path}. "
                                  f"Select the game folder {game}, follow the package Readme's optional choices, "
                                  "choose Install (not Uninstall), and save."),
                )
                binary_confirm = input_fn("Did Binary report success and did you save the changes? [y/N]: ").strip().casefold() in {"y", "yes"}
                changed = _changed_paths(game, plan["binary_target_paths"], journal["snapshots"], "pre-install")
                move_checks = []
                for move in expected_moves:
                    destination = _resolve_case_insensitive(game, move["destination"])
                    actual_hash = sha256_file(destination) if destination.is_file() else None
                    move_checks.append({**move, "actual_sha256": actual_hash,
                                        "match": bool(move["expected_sha256"] and actual_hash == move["expected_sha256"])})
                moves_ok = all(x["match"] for x in move_checks)
                journal["stages"].append({"stage": "binary", "status": "completed" if changed and binary_confirm and moves_ok else "verification_failed",
                                          "changed_target_files": changed, "move_file_checks": move_checks,
                                          "user_confirmed_success": binary_confirm})
                save_journal()
                if not changed or not binary_confirm or not moves_ok:
                    raise RuntimeError("Binary stage was not confirmed, did not change declared targets, or a move_file destination failed its source-hash check. Check the selected .end file and save operation.")

            if plan.get("direct_model_payload"):
                _copy_modloader_payload(package, game, {"modloader_payload": plan["direct_model_payload"]}, backup, journal, overwrite)
                journal["stages"].append({"stage": "direct_unlimiter_model_payload", "status": "completed"})
                save_journal()

            if plan.get("ed_payload"):
                ed_path = Path(ed_root).expanduser().resolve()
                _copy_ed_payload(package, ed_path, plan, backup, journal, overwrite)
                frontend_snapshot = _snapshot_directory(game / "FRONTEND", backup, journal, "before-ed")
                save_journal()
                _launch_tool(
                    Path(ed_exe).expanduser().resolve(), [], "Ed", input_fn, launcher,
                    instructions=(f"Run Ed as Administrator. Open the game folder {game} with Ctrl+O. "
                                  "If the config is not listed, use Ctrl+B to browse the Config folder and F5 to refresh. "
                                  "Then use Alt+A / Apply. Wait for the 'New cars added successfully' message."),
                )
                ed_confirm = input_fn("Did Ed show 'New cars added successfully'? [y/N]: ").strip().casefold() in {"y", "yes"}
                frontend_snapshot["after_tree_hash"] = _tree_hash(game / "FRONTEND")
                journal["stages"].append({"stage": "ed", "status": "completed" if ed_confirm else "verification_failed",
                                          "user_confirmed_success": ed_confirm})
                save_journal()
                if not ed_confirm:
                    raise RuntimeError("Ed success was not confirmed. VLT installation was not started.")

            if plan.get("nfsms_entrypoint"):
                installer = Path(attribulina_installer).expanduser().resolve()
                script = Path(plan["nfsms_entrypoint"])
                for rel in ("GLOBAL/ATTRIBUTES.BIN", "GLOBAL/FE_ATTRIB.BIN"):
                    _backup_file(_resolve_case_insensitive(game, rel), game, backup, journal, "attribulina-before")
                global_snapshot = _snapshot_directory(game / "GLOBAL", backup, journal, "before-attribulina")
                _launch_tool(
                    installer, [str(script)], "Attribulina Mod Installer", input_fn, launcher,
                    instructions=(f"Install this script: {script}. Select Need for Speed Most Wanted and game folder {game}; "
                                  "choose Install (not Uninstall) and complete the installation."),
                )
                attrib_confirm = input_fn("Did Attribulina report a successful install with no failed script lines? [y/N]: ").strip().casefold() in {"y", "yes"}
                db_paths = ["GLOBAL/ATTRIBUTES.BIN", "GLOBAL/FE_ATTRIB.BIN"]
                changed_db = _changed_paths(game, db_paths, journal["snapshots"], "attribulina-before")
                global_snapshot["after_tree_hash"] = _tree_hash(game / "GLOBAL")
                model_targets = [x for x in plan["nfsms_target_paths"] if x.casefold().startswith("cars/")]
                model_targets.extend(x["destination"] for x in plan.get("direct_model_payload", []) if x["destination"].casefold().startswith("cars/"))
                present_models = [x for x in model_targets if _resolve_case_insensitive(game, x).is_file()]
                file_copy_checks = []
                for operation in plan.get("nfsms_file_copy_operations", []):
                    source = package / _safe_relative(operation["source"])
                    destination = _resolve_case_insensitive(game, operation["destination"])
                    source_hash = sha256_file(source) if source.is_file() else None
                    destination_hash = sha256_file(destination) if destination.is_file() else None
                    file_copy_checks.append({"source": operation["source"], "destination": operation["destination"],
                                             "source_sha256": source_hash, "destination_sha256": destination_hash,
                                             "match": bool(source_hash and destination_hash and source_hash == destination_hash)})
                copy_ok = all(x["match"] for x in file_copy_checks)
                journal["stages"].append({
                    "stage": "attribulina_database_script", "script_format": "amod" if script.suffix.casefold() == ".amod" else "nfsms",
                    "status": "completed" if changed_db and attrib_confirm and copy_ok else "verification_failed",
                    "changed_databases": changed_db, "model_files_present": present_models,
                    "file_copy_checks": file_copy_checks, "user_confirmed_success": attrib_confirm,
                })
                save_journal()
                if not changed_db or not attrib_confirm or not copy_ok:
                    raise RuntimeError("Attribulina stage was not confirmed, database files did not change, or one or more NFSMS file_copy hashes do not match. Check the selected script, target game and Install result.")


        if selected == "unlimiter_addon":
            cli = Path(attribcli).expanduser().resolve()
            readback_dir = backup / "database-readback"
            readback_dir.mkdir(parents=True, exist_ok=True)
            readback = []
            for car_id in plan.get("car_ids", []):
                out = readback_dir / f"{car_id.lower()}.amod"
                completed = subprocess.run(
                    [str(cli), "export", str(game / "GLOBAL"), f"pvehicle/{car_id.lower()}",
                     "--children", "-o", str(out)],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=180, check=False,
                )
                content = out.read_text(encoding="utf-8", errors="replace") if out.is_file() else ""
                ok = completed.returncode == 0 and f"pvehicle/{car_id.lower()}" in content.casefold()
                readback.append({"car_id": car_id, "ok": ok, "returncode": completed.returncode,
                                 "output": str(out), "stderr": completed.stderr[-2000:]})
            journal["database_readback"] = readback
            journal["database_verification"] = {
                "status": "read_back_passed" if readback and all(x["ok"] for x in readback) else "read_back_failed",
                "cars_checked": [x["car_id"] for x in readback],
            }
            if not readback or not all(x["ok"] for x in readback):
                raise RuntimeError("Attribulina read-back did not confirm every expected pvehicle collection. See database-readback reports.")

        # File-level verification after all selected stages.
        model_paths = set(plan.get("nfsms_target_paths", []))
        model_paths.update(x for x in plan.get("binary_target_paths", []) if x.casefold().startswith("cars/"))
        model_paths.update(item["destination"] for item in plan.get("modloader_payload", []))
        model_paths.update(item["destination"] for item in plan.get("direct_model_payload", []))
        model_check = []
        for rel in sorted(model_paths):
            target = _resolve_case_insensitive(game, rel)
            if rel.casefold().endswith(("geometry.bin", "textures.bin", "vinyls.bin")):
                model_check.append({"path": rel, "exists": target.is_file(),
                                    "size": target.stat().st_size if target.is_file() else None})
        missing_models = [x["path"] for x in model_check if not x["exists"]]
        copied_payload_checks = []
        for copied in journal.get("copied_files", []):
            dest = Path(copied["destination"])
            exists = dest.is_file()
            actual_hash = sha256_file(dest) if exists else None
            copied_payload_checks.append({"destination": str(dest), "exists": exists,
                                          "expected_sha256": copied["sha256"], "actual_sha256": actual_hash,
                                          "match": bool(exists and actual_hash == copied["sha256"])})
        bad_copied_payload = [x["destination"] for x in copied_payload_checks if not x["match"]]
        journal["file_verification"] = {"model_files": model_check, "missing_model_files": missing_models,
                                        "copied_payload_checks": copied_payload_checks}
        if missing_models or bad_copied_payload:
            raise RuntimeError(f"File verification failed. Missing model files: {', '.join(missing_models)}; copied payload mismatches: {', '.join(bad_copied_payload)}")

        if selected in {"classic_modloader_replacement", "nfsmw_modular_loader"}:
            journal["database_verification"] = {"status": "not_applicable", "reason": "Loader payload files are applied at runtime; no database script is part of this profile"}
        elif journal.get("database_verification", {}).get("status") != "read_back_passed":
            journal["database_verification"] = {"status": "read_back_failed", "reason": "Independent pvehicle read-back did not pass"}

        if confirm_game_test:
            answer = input_fn(
                "\nNow launch the game and test the new car in the garage/car lot. "
                "Can you see the car and drive it without errors? [y/N]: "
            ).strip().casefold()
            journal["in_game_confirmed"] = answer in {"y", "yes"}
        stages_ok = all(stage.get("status") == "completed" for stage in journal["stages"])
        database_ok = selected in {"classic_modloader_replacement", "nfsmw_modular_loader"} or journal["database_verification"]["status"] == "read_back_passed"
        journal["status"] = "PASS" if journal["in_game_confirmed"] and stages_ok and database_ok else "INSTALLED_AWAITING_IN_GAME_VERIFICATION"
        journal["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save_journal()
        return {"status": journal["status"], "journal": str(journal_path),
                "backup_root": str(backup), "profile": selected,
                "stages": journal["stages"], "file_verification": journal["file_verification"],
                "database_verification": journal["database_verification"],
                "in_game_confirmed": journal["in_game_confirmed"],
                "package_tree_sha256": journal["package_tree_sha256"]}
    except KeyboardInterrupt as exc:
        journal["status"] = "PARTIAL_OR_FAILED"
        journal["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        journal["error"] = "Interrupted by user. Close any external tool safely before rollback."
        save_journal()
        raise RuntimeError(f"Installation interrupted. Backups and run journal are preserved at {journal_path}") from exc
    except Exception as exc:
        journal["status"] = "PARTIAL_OR_FAILED"
        journal["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        journal["error"] = str(exc)
        save_journal()
        raise RuntimeError(f"Installation stopped: {exc}. Backups and run journal are preserved at {journal_path}") from exc


def rollback_guided_install(journal_path: str | Path) -> dict[str, Any]:
    journal_file = Path(journal_path).expanduser().resolve()
    journal = json.loads(journal_file.read_text(encoding="utf-8"))
    if journal.get("kind") != "guided_install":
        raise ValueError("Not a guided-install journal")
    restored = removed = restored_directories = removed_directories = 0
    directory_snapshots = list(reversed(journal.get("directory_snapshots", [])))
    file_snapshots = list(reversed(journal.get("snapshots", [])))
    # Validate every backup and post-install tree hash before changing anything.
    for snapshot in directory_snapshots:
        target = Path(snapshot["path"]).resolve()
        expected_after = snapshot.get("after_tree_hash")
        if expected_after and _tree_hash(target) != expected_after:
            raise RuntimeError(f"Refusing rollback: {target} changed after this install. Review/reconcile manually.")
        if snapshot.get("existed") and not Path(snapshot["backup"]).resolve().is_dir():
            raise FileNotFoundError(f"Rollback directory backup missing: {snapshot['backup']}")
    for snapshot in file_snapshots:
        if snapshot.get("existed") and not Path(snapshot["backup"]).resolve().is_file():
            raise FileNotFoundError(f"Rollback backup missing: {snapshot['backup']}")

    # Restore directory snapshots first. They capture Attribulina trace files
    # as well as database files, preserving the Mod Installer's installed-mod state.
    for snapshot in directory_snapshots:
        target = Path(snapshot["path"]).resolve()
        if snapshot.get("existed"):
            backup = Path(snapshot["backup"]).resolve()
            if target.exists():
                shutil.rmtree(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(backup, target)
            restored_directories += 1
        elif target.exists():
            shutil.rmtree(target)
            removed_directories += 1
    for snapshot in file_snapshots:
        target = Path(snapshot["path"]).resolve()
        if snapshot.get("existed"):
            backup = Path(snapshot["backup"]).resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)
            restored += 1
        elif target.is_file():
            target.unlink()
            removed += 1
    journal["status"] = "ROLLED_BACK"
    journal["rolled_back_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    journal["rollback"] = {"restored_files": restored, "removed_created_files": removed,
                           "restored_directories": restored_directories, "removed_directories": removed_directories}
    journal_file.write_text(json.dumps(journal, indent=2), encoding="utf-8")
    return journal["rollback"]
