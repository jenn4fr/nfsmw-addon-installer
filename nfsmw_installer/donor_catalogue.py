from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_HEADER_RE = re.compile(
    r"^\s*collection\s+([A-Za-z0-9_]+)/(.+?)\s+under\s+.*?\s+vault\s+db\s*\{",
    re.IGNORECASE,
)
_FIELD_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def _scalar(value: str) -> Any:
    value = value.strip().rstrip(",")
    if not value:
        return ""
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if re.fullmatch(r"[-+]?\d+", value):
        try:
            return int(value)
        except ValueError:
            pass
    if re.fullmatch(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?", value):
        try:
            return float(value)
        except ValueError:
            pass
    return value


def parse_amod_export(text: str) -> list[dict[str, Any]]:
    """Parse collection blocks from Attribulina's textual AMOD export.

    Nested values are retained as raw text; simple scalar fields are typed.
    This deliberately avoids pretending to understand every VLT value type.
    """
    lines = text.splitlines()
    records: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        match = _HEADER_RE.match(lines[i])
        if not match:
            i += 1
            continue
        class_name, collection_path = match.groups()
        depth = lines[i].count("{") - lines[i].count("}")
        body: list[str] = []
        i += 1
        while i < len(lines) and depth > 0:
            line = lines[i]
            depth += line.count("{") - line.count("}")
            if depth > 0:
                body.append(line)
            i += 1

        fields: dict[str, Any] = {}
        nested = 0
        for line in body:
            stripped = line.strip()
            if nested == 0:
                field_match = _FIELD_RE.match(line)
                if field_match:
                    key, value = field_match.groups()
                    if value and not value.startswith(("{", "[")):
                        fields[key] = _scalar(value)
                    elif value:
                        fields[key] = value
            nested += line.count("{") - line.count("}")
            if nested < 0:
                nested = 0

        records.append({
            "class": class_name.lower(),
            "collection": collection_path,
            "leaf": collection_path.rsplit("/", 1)[-1],
            "fields": fields,
        })
    return records


def build_donor_catalogue(scan_root: Path) -> dict[str, Any]:
    """Build a read-only catalogue from scanner complete-export.amod files."""
    scan_root = Path(scan_root)
    databases: dict[str, dict[str, list[dict[str, Any]]]] = {}
    errors: list[dict[str, str]] = []

    for export in sorted(scan_root.glob("*/classes/*/complete-export.amod")):
        database = export.parts[-4]
        class_name = export.parts[-2].lower()
        try:
            records = parse_amod_export(export.read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            errors.append({"file": str(export), "error": str(exc)})
            continue
        databases.setdefault(database, {}).setdefault(class_name, []).extend(records)

    # Vehicle profiles are deliberately data-driven: each profile is a collection
    # record, not an assumption that identically named leaves are interchangeable.
    profiles: dict[str, dict[str, Any]] = {}
    vehicle_classes = {
        "pvehicle", "ecar", "engine", "induction", "transmission",
        "brakes", "chassis", "tires", "camerainfo", "acceltrans",
        "nos", "shiftpattern", "presetride", "rigidbodyspecs",
        "engineaudio", "turbosfx", "damagespecs",
    }
    for database, classes in databases.items():
        for class_name in sorted(vehicle_classes.intersection(classes)):
            for record in classes[class_name]:
                key = f"{database}:{record['leaf']}".lower()
                profile = profiles.setdefault(key, {
                    "name": record["leaf"],
                    "database": database,
                    "configurations": {},
                })
                profile["configurations"].setdefault(class_name, []).append({
                    "collection": record["collection"],
                    "fields": record["fields"],
                })

    return {
        "catalogue_version": 1,
        "source": str(scan_root.resolve()),
        "read_only": True,
        "databases": {
            db: {
                cls: len(records)
                for cls, records in sorted(classes.items())
            }
            for db, classes in sorted(databases.items())
        },
        "collection_count": sum(
            len(records) for classes in databases.values()
            for records in classes.values()
        ),
        "vehicle_profiles": profiles,
        "errors": errors,
        "safety_note": (
            "Catalogue only. No game database writes or donor configuration "
            "changes are performed."
        ),
    }


def write_donor_catalogue(catalogue: dict[str, Any], output: Path) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalogue, indent=2), encoding="utf-8")
    return output
