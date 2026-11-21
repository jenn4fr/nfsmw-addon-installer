from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_HEADER_RE = re.compile(
    r"^\s*collection\s+([A-Za-z0-9_]+)/(.+?)\s+under\s+(.+?)\s+in\s+vault\s+db\s*\{",
    re.IGNORECASE,
)
_FIELD_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")

VEHICLE_CLASSES = {
    "pvehicle", "ecar", "engine", "induction", "transmission", "brakes",
    "chassis", "tires", "camerainfo", "acceltrans", "nos", "shiftpattern",
    "presetride", "rigidbodyspecs", "engineaudio", "turbosfx", "damagespecs",
}


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
    """Parse top-level scalar fields and collection ancestry from AMOD exports.

    Nested VLT blocks/arrays are intentionally not interpreted. Parent paths are
    retained because they distinguish playable racer vehicles from traffic,
    police, trailers and generic class defaults.
    """
    lines = text.splitlines()
    records: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        match = _HEADER_RE.match(lines[i])
        if not match:
            i += 1
            continue
        class_name, collection_path, parent_path = match.groups()
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
            if nested == 0:
                field_match = _FIELD_RE.match(line)
                if field_match:
                    key, value = field_match.groups()
                    if value and not value.startswith(("{", "[")):
                        fields[key] = _scalar(value)
                    elif value:
                        fields[key] = value
            nested += line.count("{") - line.count("}")
            nested = max(0, nested)

        records.append({
            "class": class_name.lower(),
            "collection": collection_path,
            "parent": parent_path.strip(),
            "leaf": collection_path.rsplit("/", 1)[-1],
            "fields": fields,
        })
    return records


def _numeric_features(configurations: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Extract grounded numeric descriptors; no inferred drivetrain/dimensions."""
    features: dict[str, Any] = {}
    numeric_fields = {
        "pvehicle": ("MASS", "brakes_upgrades", "induction_upgrades", "tires_upgrades",
                     "engine_upgrades", "transmission_upgrades", "nos_upgrades", "chassis_upgrades"),
        "ecar": ("RideHeight", "CamberFront", "CamberRear", "SteerSpeed", "WheelSpokeCount"),
    }
    for cls, keys in numeric_fields.items():
        for record in configurations.get(cls, []):
            fields = record.get("fields", {})
            for key in keys:
                value = fields.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    features[f"{cls}.{key}"] = value
    pv = next(iter(configurations.get("pvehicle", [])), None)
    if pv:
        fields = pv.get("fields", {})
        for key in ("HandlingRating", "TENSOR_SCALE"):
            raw = fields.get(key)
            if isinstance(raw, str):
                nums = re.findall(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?", raw)
                if nums:
                    features[f"pvehicle.{key}"] = [float(n) for n in nums]
        for key in ("CLASS", "MODEL", "DefaultPresetRide", "TrafficEngType", "VerbalType"):
            if key in fields and isinstance(fields[key], (str, int, float, bool)):
                features[f"pvehicle.{key}"] = fields[key]
    return features


def _extract_collection_refs(fields: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Return (field, class, collection) references from simple exported values."""
    refs: list[tuple[str, str, str]] = []
    pattern = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z][A-Za-z0-9_]*)/([A-Za-z0-9_]+)")
    for field_name, value in fields.items():
        if not isinstance(value, str):
            continue
        for match in pattern.finditer(value):
            refs.append((field_name, match.group(1).lower(), match.group(2)))
    return refs


def build_donor_catalogue(scan_root: Path) -> dict[str, Any]:
    """Build a read-only vehicle catalogue from Attribulina class exports.

    Playable road cars are anchored on pvehicle collections directly under
    pvehicle/racers. Related class records are joined by exact collection leaf;
    this is a candidate relationship, not proof that every field is interchangeable.
    """
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

    profiles: dict[str, dict[str, Any]] = {}
    relationship_edges: list[dict[str, str]] = []
    for database, classes in sorted(databases.items()):
        pvehicles = classes.get("pvehicle", [])
        racers = [r for r in pvehicles if r.get("parent", "").lower() == "pvehicle/racers"]
        # Backward-compatible behavior for minimal/older fixtures lacking ancestry.
        if not racers and pvehicles and not any(r.get("collection", "").lower() == "pvehicle/racers" for r in pvehicles):
            # Small synthetic exports may omit the actual category collection.
            racers = [r for r in pvehicles if r.get("leaf", "").lower() not in {"default", "cars", "racers", "traffic", "cops", "choppers", "trailers"}]
        for vehicle in racers:
            leaf = vehicle["leaf"]
            configurations: dict[str, list[dict[str, Any]]] = {}
            canonical = {"collection": vehicle["collection"], "parent": vehicle.get("parent", ""),
                         "fields": vehicle["fields"]}
            configurations["pvehicle"] = [canonical]
            # The pvehicle collection is the authoritative relationship hub: its
            # engine/brakes/tires/etc fields contain explicit VLT collection refs.
            explicit_refs = _extract_collection_refs(vehicle["fields"])
            reference_audit = []
            for field_name, ref_class, ref_leaf in explicit_refs:
                if ref_class not in VEHICLE_CLASSES:
                    continue
                if ref_class not in classes:
                    reference_audit.append({"field": field_name, "class": ref_class,
                                            "collection": ref_leaf, "resolved": False,
                                            "reason": "class-export-missing"})
                    continue
                matches = [r for r in classes[ref_class]
                           if r["leaf"].lower() == ref_leaf.lower()]
                reference_audit.append({"field": field_name, "class": ref_class,
                                        "collection": ref_leaf, "resolved": bool(matches)})
                if not matches:
                    continue
                bucket = configurations.setdefault(ref_class, [])
                for match in matches:
                    item = {"collection": match["collection"], "parent": match.get("parent", ""),
                            "fields": match["fields"], "reference_field": field_name,
                            "relationship": "explicit-pvehicle-reference"}
                    if not any(x["collection"].lower() == item["collection"].lower() for x in bucket):
                        bucket.append(item)
                    relationship_edges.append({
                        "vehicle": leaf, "class": ref_class,
                        "collection": match["collection"], "relationship": "explicit-pvehicle-reference",
                        "reference_field": field_name,
                    })
            # ecar contains handling/body setup and is associated by exact vehicle
            # leaf; it is not a donor physics subsystem referenced by pvehicle.
            for match in classes.get("ecar", []):
                if match["leaf"].lower() == leaf.lower():
                    configurations["ecar"] = [{
                        "collection": match["collection"], "parent": match.get("parent", ""),
                        "fields": match["fields"], "relationship": "exact-vehicle-leaf",
                    }]
                    relationship_edges.append({"vehicle": leaf, "class": "ecar",
                                               "collection": match["collection"],
                                               "relationship": "exact-vehicle-leaf"})
            key = f"{database}:{leaf}".lower()
            profiles[key] = {
                "name": leaf,
                "database": database,
                "canonical_collection": vehicle["collection"],
                "canonical_parent": vehicle.get("parent", ""),
                "vehicle_kind": "playable-racer-candidate",
                "configurations": configurations,
                "features": _numeric_features(configurations),
                "relationship_confidence": "explicit pvehicle collection references where present; ecar joined by exact vehicle leaf",
                "collection_references": reference_audit,
            }

    return {
        "catalogue_version": 3,
        "source": str(scan_root),
        "read_only": True,
        "databases": {
            db: {cls: len(records) for cls, records in sorted(classes.items())}
            for db, classes in sorted(databases.items())
        },
        "collection_count": sum(len(records) for classes in databases.values() for records in classes.values()),
        "vehicle_count": len(profiles),
        "vehicle_profiles": profiles,
        "relationship_edges": relationship_edges,
        "errors": errors,
        "limitations": [
            "Vehicle profiles are anchored to pvehicle/racers collections.",
            "Cross-class relationships currently use exact collection-leaf matches.",
            "Nested VLT references and array values are not decoded into compatibility features.",
            "Mass and handling values are descriptors, not a complete physical compatibility model.",
        ],
        "safety_note": "Catalogue only. No game database writes or donor configuration changes are performed.",
    }


def write_donor_catalogue(catalogue: dict[str, Any], output: Path) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalogue, indent=2), encoding="utf-8")
    return output
