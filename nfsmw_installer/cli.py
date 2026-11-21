from __future__ import annotations

import argparse
import json
import os
import re
import sys
import subprocess
import hashlib
from pathlib import Path

from .core import scan_folder, _read_archive, make_report, load_inventory
from .attribulina import AttribulinaAdapter
from .inventory import build_inventory, write_inventory
from .donor_catalogue import build_donor_catalogue, write_donor_catalogue
from .planner import build_install_plan
from .donor_matcher import rank_donors, build_configuration_proposal, parse_target_collections, write_json
from .apply_plan import apply_file_plan, rollback_journal
from .archive import extract_archive
from .package_analysis import analyze_package
from .workflow import build_workflow_plan, execute_guided_install, rollback_guided_install


def resolve_path(value: str | Path) -> Path:
    """Accept native Windows paths and Git Bash /c/... paths."""
    raw = os.fspath(value)



    if os.name == "nt":
        match = re.match(r"^/([a-zA-Z])/(.*)$", raw)
        if match:
            raw = f"{match.group(1).upper()}:/{match.group(2)}"

    return Path(raw).expanduser()



def print_result(label, result):
    print(f"\n========== {label} ==========")
    print("Success:", result.ok)
    print("Exit code:", result.returncode)

    if result.stdout:
        print(result.stdout.rstrip())

    if result.stderr:
        print("STDERR:", result.stderr.rstrip())

    if result.timed_out:
        print("ERROR: Attribulina operation timed out.")


def inspect_command(args, parser):
    src = resolve_path(args.source).resolve()



    if not src.exists():
        parser.error(f"Source does not exist: {src}")



    if src.is_dir():
        files, texts, warnings = scan_folder(src)
    else:
        files, texts, warnings = _read_archive(src)



    inventory_path = (
        resolve_path(args.inventory) if args.inventory else None
    )
    inventory = load_inventory(inventory_path) if inventory_path else None



    report = make_report(src, files, texts, warnings, inventory)



    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")



    print(
        f"Scanned: {src}\n"
        f"Files: {len(files)}\n"
        f"Detected: {', '.join(report['layout']['detected_types'])}\n"
        f"NFSMS commands: {len(report['nfsms_commands'])}\n"
        f"Findings: {len(report['findings'])}\n"
        f"Report: {output.resolve()}"
    )



    for finding in report["findings"]:
        loc = (
            f" (line {finding['line']})"
            if finding.get("line")
            else ""
        )
        print(
            f"[{finding['severity'].upper()}] "
            f"{finding['code']}{loc}: {finding['message']}"
        )



    print("\nNo game files were changed.")
    return 0



def validate_db_command(args):
    script = resolve_path(args.script).resolve()
    database = resolve_path(args.database).resolve()
    executable = resolve_path(args.attribulina).resolve()



    output = (
        resolve_path(args.output)
        if args.output
        else Path("reports") / f"{script.stem}-attribulina.amod"
    )



    adapter = AttribulinaAdapter(
        executable=executable,
        database=database,
        timeout=args.timeout,
    )



    print("NFSMS script:", script)
    print("Database:", database)
    print("Attribulina:", executable)
    print("AMOD output:", output.resolve())



    converted = adapter.convert(script, output)
    print_result("1. CONVERSION", converted)



    if not converted.ok:
        print("\nStopped: conversion failed.")
        return 2



    checked = adapter.check(output)
    print_result("2. DATABASE CHECK", checked)



    if not checked.ok:
        print("\nStopped: database validation failed.")
        return 2



    dry = adapter.dry_run(output)
    print_result("3. STRICT DRY-RUN", dry)



    if not dry.ok:
        print("\nStopped: strict dry-run failed.")
        return 2



    print("\n========== VALIDATION COMPLETE ==========")
    print("AMOD:", output.resolve())
    print("Actual database installation: NOT PERFORMED")
    return 0



def inventory_db_command(args):
    executable = resolve_path(args.attribulina).resolve()
    attributes = resolve_path(args.attributes).resolve()
    frontend = resolve_path(args.frontend).resolve()
    output = resolve_path(args.output)



    for label, path in (
        ("Attribulina executable", executable),
        ("ATTRIBUTES.BIN", attributes),
        ("FE_ATTRIB.BIN", frontend),
    ):
        if not path.is_file():
            print(f"ERROR: {label} not found: {path}", file=sys.stderr)
            return 2



    databases = {
        "ATTRIBUTES.BIN": attributes,
        "FE_ATTRIB.BIN": frontend,
    }



    print("Attribulina:", executable)
    print("Attributes database:", attributes)
    print("Frontend database:", frontend)
    print("\nBuilding read-only database inventory...")



    inventory = build_inventory(
        executable=executable,
        databases=databases,
        timeout=args.timeout,
    )
    write_inventory(inventory, output)



    total_classes = sum(
        db["class_count"]
        for db in inventory["databases"].values()
    )



    print("\n========== INVENTORY COMPLETE ==========")
    print("Database files scanned:", len(databases))
    print("Total class listings:", total_classes)
    print("Unique node references:", len(inventory["nodes"]))
    print("Unique collection references:", len(inventory["collections"]))
    print("Output:", output.resolve())
    print("Database files modified: NO")
    return 0


def plan_install_command(args):
    package = resolve_path(args.source).resolve()
    game_root = resolve_path(args.game_root).resolve() if args.game_root else None
    output = resolve_path(args.output)

    plan = build_install_plan(package, game_root=game_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    print("Package:", package)
    print("Game root:", game_root if game_root else "not supplied")
    print("Operations:", len(plan["operations"]))
    print("Unresolved components:", len(plan["unresolved_mappings"]))
    conflicts = len(plan["conflicts"])
    print("Existing-file conflicts:", conflicts)
    print("Plan:", output.resolve())
    print("Mode: READ-ONLY; no installation performed")
    return 0




def build_donor_catalogue_command(args):
    scan_root = resolve_path(args.scan_root).resolve()
    output = resolve_path(args.output)
    if not scan_root.is_dir():
        print(f"ERROR: scan directory not found: {scan_root}", file=sys.stderr)
        return 2
    catalogue = build_donor_catalogue(scan_root)
    write_donor_catalogue(catalogue, output)
    print("Scan directory:", scan_root)
    print("Collections parsed:", catalogue["collection_count"])
    print("Vehicle profiles:", len(catalogue["vehicle_profiles"]))
    print("Parse/read errors:", len(catalogue["errors"]))
    print("Catalogue:", output.resolve())
    print("Mode: READ-ONLY; no database changes")
    return 0



def donor_assist_command(args):
    catalogue_path = resolve_path(args.catalogue).resolve()
    catalogue = json.loads(catalogue_path.read_text(encoding="utf-8"))
    package = resolve_path(args.source).resolve()
    if not package.is_dir():
        print(f"ERROR: addon folder not found: {package}", file=sys.stderr)
        return 2
    target = args.target or package.name
    result = rank_donors(catalogue, target_name=target, limit=args.limit, database=args.database, target_profile=args.target_profile)
    if args.donor:
        key = args.donor if args.donor in catalogue.get("vehicle_profiles", {}) else None
        if key is None:
            matches = [k for k, v in catalogue.get("vehicle_profiles", {}).items()
                       if v.get("name", "").lower() == args.donor.lower()]
            key = matches[0] if matches else None
        if key is None:
            print(f"ERROR: donor not found: {args.donor}", file=sys.stderr)
            return 2
        target_collections = None
        if args.amod:
            amod_path = resolve_path(args.amod).resolve()
            if not amod_path.is_file():
                print(f"ERROR: target AMOD not found: {amod_path}", file=sys.stderr)
                return 2
            target_collections = parse_target_collections(amod_path.read_text(encoding="utf-8", errors="replace"))
        result["configuration_proposal"] = build_configuration_proposal(
            catalogue, key, target, target_collections=target_collections)
    output = resolve_path(args.output)
    write_json(result, output)
    print("Target vehicle:", target)
    print("Candidates:", result["candidate_count"])
    print("Recommendations:")
    for i, item in enumerate(result["recommendations"], 1):
        print(f"{i:2}. {item['name']:<24} score={item['score']:>5} coverage={item['coverage_score']:>5}% classes={len(item['available_classes'])}")
    if args.donor:
        print("Review-only configuration proposal included.")
    print("Report:", output.resolve())
    print("Ranking basis:", result.get("ranking_basis"))
    print("Physical compatibility verified: NO")
    print("Game/database writes: NO")
    return 0


def apply_plan_command(args):
    result = apply_file_plan(resolve_path(args.plan), execute=args.execute,
                             overwrite=args.overwrite, backup_root=resolve_path(args.backup_root) if args.backup_root else None)
    print(json.dumps(result, indent=2))
    return 0


def rollback_command(args):
    journal_path = resolve_path(args.journal)
    try:
        obj = json.loads(journal_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        obj = {}
    if obj.get("kind") == "guided_install":
        result = rollback_guided_install(journal_path)
    else:
        result = rollback_journal(journal_path)
    print(json.dumps(result, indent=2))
    return 0



def _prepare_package_source(source: Path, workspace: Path | None = None, seven_zip: str | None = None) -> Path:
    source = source.resolve()
    if source.is_dir():
        return source
    if not source.is_file():
        raise FileNotFoundError(f"Package source not found: {source}")
    digest_hash = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest_hash.update(chunk)
    digest = digest_hash.hexdigest()
    if workspace is None:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".cache")) / "NFSMW-Addon-Installer" / "packages"
    else:
        base = workspace.expanduser().resolve()
    package_cache = base / digest
    payload = package_cache / "payload"
    marker = package_cache / "source.sha256"
    if payload.is_dir() and marker.is_file():
        if marker.read_text(encoding="utf-8").strip() == digest:
            return payload
        raise RuntimeError(f"Package cache marker mismatch: {package_cache}")
    package_cache.mkdir(parents=True, exist_ok=True)
    result = extract_archive(source, payload, seven_zip=seven_zip)
    marker.write_text(digest + "\n", encoding="utf-8")
    return payload


def analyze_package_command(args):
    source = resolve_path(args.source).resolve()
    package = _prepare_package_source(source, resolve_path(args.workspace) if args.workspace else None,
                                      str(resolve_path(args.seven_zip)) if args.seven_zip else None)
    report = analyze_package(package)
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Package: {package}\nFiles: {report['file_count']}\nCars: {', '.join(report['car_ids']) or 'not identified'}")
    print("Profiles:", ", ".join(p["id"] for p in report["profiles"]) or "none")
    print("NFSMS entry points:", ", ".join(report["components"]["nfsms"]["entrypoints"]) or "none")
    print("Binary manifests:", len(report["components"]["binary_manifests"]))
    print("MWPS files:", len(report["components"]["mwps"]))
    print("Warnings:", len(report["warnings"]))
    print("Report:", output.resolve())
    print("No game files were changed.")
    return 0


def _discover_executable(name: str, roots: list[Path]) -> Path | None:
    wanted = name.casefold()
    candidates: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.name.casefold() == wanted:
                candidates.append(path.resolve())
    if not candidates:
        return None
    candidates = sorted(set(candidates), key=lambda p: str(p).casefold())
    if len(candidates) > 1:
        choices = "\n  ".join(str(p) for p in candidates)
        raise RuntimeError(f"Multiple {name} executables found. Pass an explicit path with the matching option:\n  {choices}")
    return candidates[0]


def install_command(args):
    source = resolve_path(args.source).resolve()
    package = _prepare_package_source(source, resolve_path(args.workspace) if args.workspace else None,
                                      str(resolve_path(args.seven_zip)) if args.seven_zip else None)
    game = resolve_path(args.game_root).resolve()
    roots = [resolve_path(args.tools_root).resolve()] if args.tools_root else []
    if args.execute:
        roots.extend([game.parent / "NFS-hack" / "utils", game.parent / "NFS-hack" / "tools", game.parent / "utils"])
        roots = list(dict.fromkeys(p for p in roots if p.is_dir()))
        binary_path = resolve_path(args.binary).resolve() if args.binary else _discover_executable("Binary.exe", roots)
        attribulina_path = resolve_path(args.attribulina_installer).resolve() if args.attribulina_installer else _discover_executable("AttribulinaModInstaller.exe", roots)
        attribcli_path = resolve_path(args.attribcli).resolve() if args.attribcli else (_discover_executable("attribcli.exe", roots) or (attribulina_path.with_name("attribcli.exe") if attribulina_path else None))
        ed_exe_path = resolve_path(args.ed_exe).resolve() if args.ed_exe else _discover_executable("Ed.exe", roots)
    else:
        binary_path = resolve_path(args.binary).resolve() if args.binary else None
        attribulina_path = resolve_path(args.attribulina_installer).resolve() if args.attribulina_installer else None
        attribcli_path = resolve_path(args.attribcli).resolve() if args.attribcli else None
        ed_exe_path = resolve_path(args.ed_exe).resolve() if args.ed_exe else None
    if args.ed_root:
        ed_root = resolve_path(args.ed_root).resolve()
        if args.ed_exe:
            ed_exe_path = resolve_path(args.ed_exe).resolve()
        elif (ed_root / "Ed.exe").is_file():
            ed_exe_path = ed_root / "Ed.exe"
        elif ed_exe_path and ed_exe_path.parent != ed_root:
            ed_exe_path = None
    else:
        ed_root = ed_exe_path.parent if ed_exe_path else None
    plan = build_workflow_plan(package, game, profile=args.profile, ed_root=ed_root, car_ids_extra=args.car_id)
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"Package: {package}\nGame: {game}\nProfile: {plan['profile']['id']}")
    if plan.get("profile_selection") == "target_compatible_auto":
        print("Profile selection: automatically selected the only route compatible with this game folder")
    if plan.get("database_script_entrypoint_relative"):
        print(f"Database script ({plan.get('database_script_format')}): {plan['database_script_entrypoint_relative']}")
    if roots:
        print("Tool search roots:", ", ".join(str(p) for p in roots))
    for label, path in (("Binary", binary_path), ("Attribulina Mod Installer", attribulina_path), ("attribcli", attribcli_path), ("Ed", ed_exe_path)):
        if path:
            print(f"Detected {label}: {path}")
    for check in plan["compatibility_checks"]:
        print(f"{'PASS' if check['passed'] else 'BLOCK'} - {check['check']}: {check['reason']}")
    if plan["warnings"]:
        print("Warnings:")
        for warning in plan["warnings"]:
            print(f"  - {warning['code']}: {warning['message']}")
    print("Plan:", output.resolve())
    if not args.execute:
        print("Mode: DRY RUN. No game files or databases were changed.")
        print("To run the guided installer, repeat with --execute. Tools are auto-detected under --tools-root; explicit paths can be supplied if needed.")
        return 0 if plan["ready"] else 2
    result = execute_guided_install(
        package, game, profile=args.profile, car_ids_extra=args.car_id,
        binary_exe=binary_path,
        attribulina_installer=attribulina_path,
        attribcli=attribcli_path,
        ed_root=ed_root,
        ed_exe=ed_exe_path,
        overwrite=args.overwrite,
        backup_root=resolve_path(args.backup_root) if args.backup_root else None,
        confirm_game_test=not args.skip_game_test,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="nfsmw-installer",
        description=(
            "Discovery and validation assistant for NFS Most Wanted (2005). "
            "Analysis and preflight are read-only; guided installation writes only with explicit --execute."
        ),
    )



    sub = parser.add_subparsers(dest="action", required=True)



    inspect = sub.add_parser(
        "inspect",
        help="Inspect an extracted folder or ZIP/RAR/7z archive",
    )
    inspect.add_argument("source")
    inspect.add_argument(
        "-o", "--output",
        default="nfsmw-report.json",
    )
    inspect.add_argument(
        "--inventory",
        help="Optional JSON inventory of VLT nodes and collections",
    )



    validate = sub.add_parser(
        "validate-db",
        help="Convert, check and dry-run an NFSMS script against a game database",
    )
    validate.add_argument("script", help="Input NFSMS installation script")
    validate.add_argument(
        "--database",
        required=True,
        help="Combined game database, normally FE_ATTRIB.BIN",
    )
    validate.add_argument(
        "--attribulina",
        required=True,
        help="Path to attribcli.exe",
    )
    validate.add_argument(
        "-o", "--output",
        help="Output AMOD path (must not already exist)",
    )
    validate.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Timeout in seconds for each Attribulina operation (default: 180)",
    )



    inventory_cmd = sub.add_parser(
        "inventory-db",
        help="Build a read-only inventory of both MW databases",
    )
    inventory_cmd.add_argument("--attribulina", required=True)
    inventory_cmd.add_argument("--attributes", required=True)
    inventory_cmd.add_argument("--frontend", required=True)
    inventory_cmd.add_argument(
        "-o", "--output",
        default="reports/mw-database-inventory.json",
    )
    inventory_cmd.add_argument("--timeout", type=int, default=180)



    plan_cmd = sub.add_parser(
        "plan-install",
        help="Build a read-only installation plan for an addon package",
    )
    plan_cmd.add_argument("source", help="Addon package root folder")
    plan_cmd.add_argument(
        "--game-root",
        help="Optional game root to check existing destination conflicts",
    )
    plan_cmd.add_argument(
        "-o", "--output",
        default="reports/install-plan.json",
        help="JSON plan output path (default: reports/install-plan.json)",
    )



    donor_cmd = sub.add_parser(
        "build-donor-catalogue",
        help="Build a read-only vehicle donor catalogue from scanner exports",
    )
    donor_cmd.add_argument("scan_root", help="Database scan output directory")
    donor_cmd.add_argument(
        "-o", "--output",
        default="reports/donor-catalogue.json",
    )

    assist_cmd = sub.add_parser("donor-assist", help="Rank donor vehicles and optionally create a review-only configuration proposal")
    assist_cmd.add_argument("source", help="Extracted add-on package folder")
    assist_cmd.add_argument("--catalogue", required=True, help="donor-catalogue.json")
    assist_cmd.add_argument("--target", help="Target vehicle name; defaults to package folder name")
    assist_cmd.add_argument("--target-profile", help="Optional existing vehicle profile key/name for measured local-feature comparison")
    assist_cmd.add_argument("--donor", help="Optional donor profile key or vehicle leaf name")
    assist_cmd.add_argument("--amod", help="Optional converted target AMOD; explicit create directives map target collections")
    assist_cmd.add_argument("--database", default="attributes.bin")
    assist_cmd.add_argument("--limit", type=int, default=10)
    assist_cmd.add_argument("-o", "--output", default="reports/donor-assist.json")

    apply_cmd = sub.add_parser("apply-file-plan", help="Apply file-copy operations from a reviewed plan; dry-run unless --execute")
    apply_cmd.add_argument("plan")
    apply_cmd.add_argument("--execute", action="store_true", help="Explicitly enable game-file copying")
    apply_cmd.add_argument("--overwrite", action="store_true", help="Back up and replace existing files")
    apply_cmd.add_argument("--backup-root", help="Optional backup directory")

    rollback_cmd = sub.add_parser("rollback-install", help="Restore files using an install journal")
    rollback_cmd.add_argument("journal")

    package_cmd = sub.add_parser("analyze-package", help="Analyze a real addon package and all installation mechanisms")
    package_cmd.add_argument("source", help="Extracted folder or ZIP/RAR/7z archive")
    package_cmd.add_argument("--workspace", help="Optional package extraction cache folder")
    package_cmd.add_argument("--7zip", dest="seven_zip", help="Path to 7z.exe for RAR/7z archives")
    package_cmd.add_argument("-o", "--output", default="reports/package-analysis.json")

    install_cmd = sub.add_parser("install", help="One-command guided addon installation (dry-run unless --execute)")
    install_cmd.add_argument("source", help="Extracted folder or ZIP/RAR/7z archive")
    install_cmd.add_argument("--game-root", required=True, help="Target NFS MW game directory")
    install_cmd.add_argument("--profile", choices=["unlimiter_addon", "classic_modloader_replacement", "nfsmw_modular_loader"], help="Choose an install route when package has alternatives")
    install_cmd.add_argument("--car-id", action="append", help="Add an explicit pvehicle ID; repeat for multi-car packages")
    install_cmd.add_argument("--workspace", help="Optional package extraction cache folder")
    install_cmd.add_argument("--tools-root", help="Folder to search recursively for Binary, Attribulina and Ed executables")
    install_cmd.add_argument("--7zip", dest="seven_zip", help="Path to 7z.exe for RAR/7z archives")
    install_cmd.add_argument("--binary", help="Path to Binary.exe (required for Binary .end packages)")
    install_cmd.add_argument("--attribulina-installer", help="Path to AttribulinaModInstaller.exe (required for NFSMS packages)")
    install_cmd.add_argument("--attribcli", help="Path to attribcli.exe for database read-back verification")
    install_cmd.add_argument("--ed-root", help="Ed application folder containing Ed.exe")
    install_cmd.add_argument("--ed-exe", help="Path to Ed.exe")
    install_cmd.add_argument("--overwrite", action="store_true", help="Back up and replace existing destination files")
    install_cmd.add_argument("--backup-root", help="Optional backup folder (default inside game root)")
    install_cmd.add_argument("--execute", action="store_true", help="Run the guided installation after preflight")
    install_cmd.add_argument("--skip-game-test", action="store_true", help="Stop after file/database verification; final status remains unverified")
    install_cmd.add_argument("-o", "--output", default="reports/guided-install-plan.json")

    args = parser.parse_args(argv)



    try:
        if args.action == "inspect":
            return inspect_command(args, parser)



        if args.action == "validate-db":
            return validate_db_command(args)



        if args.action == "inventory-db":
            return inventory_db_command(args)



        if args.action == "plan-install":
            return plan_install_command(args)


        if args.action == "build-donor-catalogue":
            return build_donor_catalogue_command(args)

        if args.action == "donor-assist":
            return donor_assist_command(args)

        if args.action == "apply-file-plan":
            return apply_plan_command(args)

        if args.action == "rollback-install":
            return rollback_command(args)

        if args.action == "analyze-package":
            return analyze_package_command(args)

        if args.action == "install":
            return install_command(args)


    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2



    return 1



if __name__ == "__main__":
    sys.exit(main())
