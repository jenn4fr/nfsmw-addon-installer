from __future__ import annotations

import argparse
import json
import os
import re
import sys
import subprocess
from pathlib import Path

from .core import scan_folder, _read_archive, make_report, load_inventory
from .attribulina import AttribulinaAdapter
from .inventory import build_inventory, write_inventory
from .donor_catalogue import build_donor_catalogue, write_donor_catalogue
from .planner import build_install_plan


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


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="nfsmw-installer",
        description=(
            "Discovery and validation assistant for NFS Most Wanted (2005). "
            "Database validation and installation planning are read-only/dry-run."
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



    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2



    return 1



if __name__ == "__main__":
    sys.exit(main())
