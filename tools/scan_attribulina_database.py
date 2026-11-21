from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent
INVENTORY = PROJECT / "reports" / "mw-database-inventory.json"

ATTRIBULINA = Path(
    r"D:\softwares\NFS-hack\utils\Attribulina\attribcli.exe"
)

VEHICLE_CLASSES = {
    "pvehicle",
    "ecar",
    "engine",
    "induction",
    "transmission",
    "brakes",
    "chassis",
    "tires",
    "camerainfo",
    "acceltrans",
    "nos",
    "shiftpattern",
    "presetride",
    "rigidbodyspecs",
    "engineaudio",
    "turbosfx",
    "damagespecs",
}

TIMEOUT = 300


def native_path(value):
    """Convert Git Bash /d/... paths into Windows-compatible paths."""
    value = str(value)
    match = re.match(r"^/([a-zA-Z])/(.*)$", value)

    if match:
        return Path(f"{match.group(1).upper()}:/{match.group(2)}")

    return Path(value)


def safe_name(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_")


class Scanner:
    def __init__(self, executable, output):
        self.executable = executable
        self.output = output
        self.log = []
        self.stats = {
            "commands": 0,
            "success": 0,
            "failed": 0,
            "timeouts": 0,
            "exports": 0,
            "collections_read": 0,
        }

    def run(self, args, output_file=None):
        self.stats["commands"] += 1

        try:
            result = subprocess.run(
                [str(self.executable), *map(str, args)],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=TIMEOUT,
            )

            stdout = result.stdout or ""
            stderr = result.stderr or ""

            if output_file:
                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_text(
                    stdout + (
                        "\n\n--- STDERR ---\n" + stderr
                        if stderr else ""
                    ),
                    encoding="utf-8",
                )

            success = result.returncode == 0

            self.stats["success" if success else "failed"] += 1

            self.log.append({
                "command": [str(x) for x in args],
                "returncode": result.returncode,
                "success": success,
                "output_file": str(output_file) if output_file else None,
                "stderr": stderr[-2000:],
            })

            return success, stdout, stderr

        except subprocess.TimeoutExpired:
            self.stats["timeouts"] += 1
            self.stats["failed"] += 1

            self.log.append({
                "command": [str(x) for x in args],
                "success": False,
                "error": f"Timed out after {TIMEOUT} seconds",
            })

        except Exception as exc:
            self.stats["failed"] += 1

            self.log.append({
                "command": [str(x) for x in args],
                "success": False,
                "error": repr(exc),
            })

        return False, "", ""

    def scan_database(self, database_name, database_info):
        db = native_path(database_info["path"])

        if not db.exists():
            self.log.append({
                "database": database_name,
                "error": f"Database not found: {db}",
            })
            print(f"[MISSING] {database_name}: {db}")
            return

        root = self.output / safe_name(database_name)
        root.mkdir(parents=True, exist_ok=True)

        print(f"\n========== DATABASE: {database_name} ==========")
        print(f"Path: {db}")

        # General database information and installed mods.
        self.run(
            ["info", db],
            root / "database-info.txt",
        )

        self.run(
            ["mods", db],
            root / "installed-mods.txt",
        )

        classes = database_info.get("classes", {})

        # Save the complete collection inventory.
        (root / "inventory.json").write_text(
            json.dumps(classes, indent=2),
            encoding="utf-8",
        )

        class_names = sorted(classes)

        print(f"Classes discovered: {len(class_names)}")

        for index, class_name in enumerate(class_names, 1):
            class_root = root / "classes" / safe_name(class_name)
            class_root.mkdir(parents=True, exist_ok=True)

            collections = classes[class_name].get("collections", [])

            print(
                f"[{index}/{len(class_names)}] "
                f"{class_name}: {len(collections)} collections"
            )

            # List actual class collections.
            self.run(
                ["list", db, class_name],
                class_root / "list.txt",
            )

            # Extract class header and field type definitions.
            self.run(
                ["header", db, class_name, "--types"],
                class_root / "header-types.txt",
            )

            # Export all collections and child data for this class.
            export_file = class_root / "complete-export.amod"

            ok, _, _ = self.run(
                [
                    "export", db, class_name,
                    "--children",
                    "-o", export_file,
                ],
                class_root / "export-log.txt",
            )

            if ok and export_file.exists():
                self.stats["exports"] += 1

            # The complete class export already contains the collection values.
            # Avoid issuing one `get` per collection: nested paths in the inventory
            # are not necessarily valid Attribulina get identifiers, and this
            # duplicated thousands of reads without adding reliable data.
            if class_name in VEHICLE_CLASSES and ok and export_file.exists():
                self.stats["collections_read"] += len(collections)

    def save_report(self):
        report = {
            "scan_version": "1.0.0",
            "created": datetime.now().astimezone().isoformat(),
            "read_only": True,
            "writes_to_game_database": False,
            "statistics": self.stats,
            "commands": self.log,
        }

        (self.output / "scan-report.json").write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )

        lines = [
            "ATTRIBULINA DATABASE SCAN",
            "=========================",
            f"Commands: {self.stats['commands']}",
            f"Successful: {self.stats['success']}",
            f"Failed: {self.stats['failed']}",
            f"Timeouts: {self.stats['timeouts']}",
            f"Class exports: {self.stats['exports']}",
            f"Collections represented by class exports: {self.stats['collections_read']}",
            "",
            "Failures and errors:",
        ]

        for item in self.log:
            if not item.get("success", True):
                lines.append(json.dumps(item, ensure_ascii=False))

        (self.output / "scan-summary.txt").write_text(
            "\n".join(lines),
            encoding="utf-8",
        )


def main():
    parser = argparse.ArgumentParser(
        description="Read-only Attribulina database scanner"
    )

    parser.add_argument(
        "--inventory",
        default=str(INVENTORY),
    )

    parser.add_argument(
        "--attribulina",
        default=str(ATTRIBULINA),
    )

    parser.add_argument(
        "--output",
        default=None,
    )

    args = parser.parse_args()

    inventory_path = native_path(args.inventory)
    executable = native_path(args.attribulina)

    if not inventory_path.exists():
        sys.exit(f"Inventory not found: {inventory_path}")

    if not executable.exists():
        sys.exit(f"Attribulina executable not found: {executable}")

    with inventory_path.open(encoding="utf-8") as file:
        inventory = json.load(file)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output = (
        native_path(args.output)
        if args.output
        else PROJECT / "reports" / f"database-scan-{timestamp}"
    )

    output.mkdir(parents=True, exist_ok=True)

    scanner = Scanner(executable, output)

    print("ATTRIBULINA DATABASE SCANNER")
    print("============================")
    print("Mode: READ ONLY")
    print("Database writes: DISABLED")
    print(f"Output: {output}")

    for database_name, database_info in inventory["databases"].items():
        scanner.scan_database(database_name, database_info)

    scanner.save_report()

    print("\n========== SCAN COMPLETE ==========")
    print(f"Commands: {scanner.stats['commands']}")
    print(f"Successful: {scanner.stats['success']}")
    print(f"Failed: {scanner.stats['failed']}")
    print(f"Exports: {scanner.stats['exports']}")
    print(f"Collections read: {scanner.stats['collections_read']}")
    print(f"\nReport folder:\n{output}")


if __name__ == "__main__":
    main()
