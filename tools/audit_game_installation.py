#!/usr/bin/env python3
"""Read-only audit of an installed NFS Most Wanted (2005) game folder.

This tool never writes to the game root. It checks known installation
components, records hashes/metadata, and optionally runs Attribulina's
read-only `info` command against both game databases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

KNOWN_SPEED_EXE_SIZE = 6_029_312
KNOWN_SPEED_EXE_SHA256 = "b248271bf8eac8c9b283b8c95e3add672b713bf529b05f1780e58268493b9d06"

REQUIRED_FILES = (
    "speed.exe",
    "GLOBAL/ATTRIBUTES.BIN",
    "GLOBAL/FE_ATTRIB.BIN",
)
REQUIRED_DIRS = ("CARS", "GLOBAL", "FRONTEND", "scripts")
OPTIONAL_DIRS = (
    "modloader",
    "scripts/UnlimiterData",
    "UnlimiterData",
)
OPTIONAL_FILES = (
    "dinput8.dll",
    "scripts/NFSMW-ML.asi",
    "NFSMW-ML.asi",
    "scripts/NFSMWUnlimiter.asi",
    "scripts/Unlimiter.asi",
)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(root: Path, relative: str) -> dict[str, Any]:
    path = root / Path(relative)
    record: dict[str, Any] = {
        "path": relative.replace("\\", "/"),
        "exists": path.is_file(),
    }
    if path.is_file():
        stat = path.stat()
        record.update({
            "size_bytes": stat.st_size,
            "sha256": sha256_file(path),
        })
    return record


def _directory_record(root: Path, relative: str) -> dict[str, Any]:
    path = root / Path(relative)
    record: dict[str, Any] = {
        "path": relative.replace("\\", "/"),
        "exists": path.is_dir(),
    }
    if path.is_dir():
        try:
            record["immediate_entries"] = len(list(path.iterdir()))
        except OSError as exc:
            record["read_error"] = str(exc)
    return record


def _run_attribulina_info(executable: Path, database: Path, timeout: int) -> dict[str, Any]:
    if not executable.is_file():
        return {"status": "not-run", "reason": "Attribulina executable not found"}
    if not database.is_file():
        return {"status": "not-run", "reason": "Database file not found"}
    try:
        result = subprocess.run(
            [str(executable), "info", str(database)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "timeout_seconds": timeout,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }
    return {
        "status": "passed" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "command": [str(executable), "info", str(database)],
    }


def audit_game_installation(
    game_root: str | Path,
    *,
    attribulina: str | Path | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    root = Path(game_root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Game root is not a directory: {root}")
    if timeout < 1:
        raise ValueError("timeout must be at least 1 second")

    files = [_file_record(root, item) for item in REQUIRED_FILES]
    optional_files = [_file_record(root, item) for item in OPTIONAL_FILES]
    directories = [_directory_record(root, item) for item in REQUIRED_DIRS]
    optional_directories = [_directory_record(root, item) for item in OPTIONAL_DIRS]

    speed = next(item for item in files if item["path"] == "speed.exe")
    speed_checks = {
        "known_size_match": speed.get("size_bytes") == KNOWN_SPEED_EXE_SIZE,
        "known_sha256_match": speed.get("sha256", "").lower() == KNOWN_SPEED_EXE_SHA256,
        "reference_size_bytes": KNOWN_SPEED_EXE_SIZE,
        "reference_sha256": KNOWN_SPEED_EXE_SHA256,
        "note": "Reference values are from the user's previously reported executable; mismatch is a warning, not proof of an invalid game.",
    }

    ml_log = root / "modloader" / "NFSMW-ML.log"
    ml_log_record = _file_record(root, "modloader/NFSMW-ML.log")
    if ml_log_record["exists"]:
        try:
            ml_log_record["tail"] = ml_log.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
        except OSError as exc:
            ml_log_record["read_error"] = str(exc)

    attrib_results = {}
    if attribulina:
        exe = Path(attribulina).expanduser().resolve()
        for label, rel in (
            ("ATTRIBUTES.BIN", "GLOBAL/ATTRIBUTES.BIN"),
            ("FE_ATTRIB.BIN", "GLOBAL/FE_ATTRIB.BIN"),
        ):
            attrib_results[label] = _run_attribulina_info(exe, root / rel, timeout)

    missing_required_files = [item["path"] for item in files if not item["exists"]]
    missing_required_dirs = [item["path"] for item in directories if not item["exists"]]
    if missing_required_files or missing_required_dirs:
        status = "incomplete"
    elif attrib_results and any(v["status"] != "passed" for v in attrib_results.values()):
        status = "warning"
    else:
        status = "audited"

    return {
        "audit_version": "0.1.0",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "game_root": str(root),
        "platform": platform.platform(),
        "read_only": True,
        "writes_performed": False,
        "required_files": files,
        "required_directories": directories,
        "optional_files": optional_files,
        "optional_directories": optional_directories,
        "speed_exe_reference_check": speed_checks,
        "modloader_log": ml_log_record,
        "attribulina_info": attrib_results,
        "summary": {
            "required_files_present": sum(x["exists"] for x in files),
            "required_files_total": len(files),
            "required_directories_present": sum(x["exists"] for x in directories),
            "required_directories_total": len(directories),
            "optional_files_present": sum(x["exists"] for x in optional_files),
            "optional_directories_present": sum(x["exists"] for x in optional_directories),
        },
        "limitations": [
            "This is a preflight installation audit, not proof that an add-on is installed correctly.",
            "Database file hashes prove file identity only; they do not verify individual vehicle attributes.",
            "Attribulina info is metadata inspection only. No database apply command is invoked.",
            "Post-install attribute verification requires an installation-specific expected-value manifest and read-back queries for each affected class/collection/field.",
            "Game launch and in-game vehicle/menu checks remain separate manual or supervised end-to-end checks.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", required=True, help="NFS MW installation root")
    parser.add_argument("--attribulina", help="Optional path to attribcli.exe for read-only info checks")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("-o", "--output", default="reports/real-game-installation-audit.json")
    args = parser.parse_args(argv)

    try:
        report = audit_game_installation(
            args.game_root, attribulina=args.attribulina, timeout=args.timeout
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Audit status: {report['status']}")
    print(f"Game root: {report['game_root']}")
    print(
        "Required files: "
        f"{report['summary']['required_files_present']}/"
        f"{report['summary']['required_files_total']}"
    )
    print(
        "Required directories: "
        f"{report['summary']['required_directories_present']}/"
        f"{report['summary']['required_directories_total']}"
    )
    print(f"Read-only: YES | Writes performed: NO")
    print(f"Report: {output.resolve()}")
    return 0 if report["status"] in {"audited", "warning"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
