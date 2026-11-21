"""Explainable donor ranking and conservative, non-executable config proposals."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Weights describe data coverage, not measured vehicle physics compatibility.
CLASS_WEIGHTS = {
    "pvehicle": 2.0, "engine": 1.5, "induction": 1.0,
    "transmission": 1.3, "brakes": 1.0, "chassis": 1.0,
    "tires": 1.0, "acceltrans": 0.8, "nos": 0.5,
    "shiftpattern": 0.5, "rigidbodyspecs": 0.7,
}
PERFORMANCE_CLASSES = tuple(CLASS_WEIGHTS)
# pvehicle contains both identity and performance data. Only these fields are
# eligible for a proposal; model/name/collection references are never copied.
PVEHICLE_PERFORMANCE_FIELDS = {
    "MASS", "brakes_upgrades", "induction_upgrades", "tires_upgrades",
    "engine_upgrades", "transmission_upgrades", "nos_upgrades",
    "chassis_upgrades", "TrafficEngType", "VerbalType",
}


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _candidate_name(profile: dict[str, Any]) -> str:
    configs = profile.get("configurations", {})
    pvehicle = configs.get("pvehicle", [])
    for item in pvehicle:
        path = item.get("collection", "")
        # Keep full path in report, but use the vehicle-like final path segment.
        leaf = path.rsplit("/", 1)[-1]
        if leaf:
            return leaf
    return str(profile.get("name", "unknown"))


def _profile_metrics(profile: dict[str, Any]) -> dict[str, Any]:
    configs = profile.get("configurations", {})
    available = [c for c in PERFORMANCE_CLASSES if configs.get(c)]
    weighted_total = sum(CLASS_WEIGHTS.values())
    weighted_present = sum(CLASS_WEIGHTS[c] for c in available)
    records = [r for c in PERFORMANCE_CLASSES for r in configs.get(c, [])]
    field_count = sum(len(r.get("fields", {})) for r in records)
    # Saturating richness factor prevents huge collections dominating the score.
    richness = min(1.0, field_count / 100.0)
    coverage = (weighted_present / weighted_total) if weighted_total else 0.0
    score = round((coverage * 80.0) + (richness * 20.0), 2)
    return {
        "score": score,
        "coverage_score": round(coverage * 100, 2),
        "richness_score": round(richness * 100, 2),
        "available_classes": available,
        "missing_classes": [c for c in PERFORMANCE_CLASSES if c not in available],
        "field_count": field_count,
        "record_count": len(records),
    }


def _feature_similarity(target: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Compare only shared numeric feature keys; missing fields are not guessed."""
    left = target.get("features", {})
    right = candidate.get("features", {})
    comparable = []
    for key in sorted(set(left) & set(right)):
        a, b = left[key], right[key]
        if isinstance(a, (int, float)) and not isinstance(a, bool) and isinstance(b, (int, float)) and not isinstance(b, bool):
            scale = max(abs(float(a)), abs(float(b)), 1.0)
            distance = min(1.0, abs(float(a) - float(b)) / scale)
            comparable.append((key, round((1.0 - distance) * 100, 2)))
        elif (isinstance(a, list) and isinstance(b, list) and len(a) == len(b)
              and a and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in a + b)):
            pair_scores = []
            for av, bv in zip(a, b):
                scale = max(abs(float(av)), abs(float(bv)), 1.0)
                pair_scores.append((1.0 - min(1.0, abs(float(av) - float(bv)) / scale)) * 100)
            comparable.append((key, round(sum(pair_scores) / len(pair_scores), 2)))
    if not comparable:
        return {"score": 0.0, "matched_features": 0, "features": [],
                "warning": "No shared numeric target features; no similarity can be established."}
    return {"score": round(sum(score for _, score in comparable) / len(comparable), 2),
            "matched_features": len(comparable),
            "features": [{"field": key, "similarity": score} for key, score in comparable],
            "warning": "Similarity uses only shared numeric scalar fields; it is not a physical fitment test."}


def rank_donors(catalogue: dict[str, Any], *, target_name: str = "",
                limit: int = 10, database: str = "attributes.bin",
                target_profile: str | None = None) -> dict[str, Any]:
    """Rank real vehicle profiles by configuration coverage and explain the score.

    Without target physics, this is a completeness shortlist, not a claim that
    the top result is physically compatible. Exact target identity is excluded.
    """
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    target_norm = _norm(target_name)
    target_data = None
    target_profile_key = None
    if target_profile:
        profiles = catalogue.get("vehicle_profiles", {})
        if target_profile in profiles:
            target_profile_key = target_profile
            target_data = profiles[target_profile]
        else:
            found = next(((k, p) for k, p in profiles.items()
                          if _norm(str(p.get("name", ""))) == _norm(target_profile)
                          and p.get("database", "").lower() == database.lower()), None)
            if found:
                target_profile_key, target_data = found
        if target_data is None:
            raise ValueError(f"target profile not found in database {database}: {target_profile}")
    candidates = []
    for key, profile in catalogue.get("vehicle_profiles", {}).items():
        if profile.get("database", "").lower() != database.lower():
            continue
        configs = profile.get("configurations", {})
        if not configs.get("pvehicle"):
            continue
        name = _candidate_name(profile)
        pvehicle_paths = [r.get("collection", "").lower() for r in configs.get("pvehicle", [])]
        # Police, traffic, and helicopter configurations are not normal road-car donors.
        if any(any(token in path for token in ("/cops/", "/choppers/", "/traffic/")) for path in pvehicle_paths):
            continue
        if (not name or name.lower() in {"default", "racers", "cops", "traffic", "choppers"}
                or (target_norm and _norm(name) == target_norm)
                or (target_profile_key and key.lower() == target_profile_key.lower())):
            continue
        metrics = _profile_metrics(profile)
        if metrics["record_count"] == 0:
            continue
        similarity = _feature_similarity(target_data, profile) if target_data else None
        final_score = metrics["score"] if similarity is None else round(metrics["score"] * 0.55 + similarity["score"] * 0.45, 2)
        reasons = [
            f"{len(metrics['available_classes'])}/{len(PERFORMANCE_CLASSES)} performance classes present",
            f"{metrics['field_count']} exported scalar fields",
        ]
        if similarity is not None:
            reasons.append(f"{similarity['matched_features']} comparable numeric features; similarity {similarity['score']}%")
        candidates.append({
            "key": key, "name": name, "database": profile.get("database"),
            **metrics,
            "score": final_score,
            "feature_similarity": similarity,
            "reason": "; ".join(reasons) + ".",
        })
    candidates.sort(key=lambda x: (-x["score"], -x["coverage_score"], x["name"].lower()))
    # Keep one best record per donor name.
    unique, seen = [], set()
    for item in candidates:
        n = item["name"].lower()
        if n in seen:
            continue
        seen.add(n)
        unique.append(item)
    return {
        "matcher_version": 2,
        "target": target_name or None,
        "database": database,
        "ranking_basis": ("configuration coverage plus numeric feature similarity to supplied local target profile"
                          if target_data else "configuration coverage and exported scalar-field richness"),
        "target_profile": target_profile_key,
        "physical_compatibility_verified": False,
        "score_interpretation": ("Coverage/richness blended with shared numeric descriptor similarity; heuristic only, not physical fitment."
                                 if target_data else "Configuration coverage/richness only; not physical compatibility."),
        "recommendations": unique[:limit],
        "candidate_count": len(unique),
        "limitations": [
            "Scores measure exported configuration coverage, not vehicle dimensions, drivetrain, wheelbase, or handling compatibility.",
            "A real target profile is required for physics-to-physics similarity scoring.",
            "Only ATTRIBUTES.BIN is ranked by default; FE_ATTRIB.BIN is for cross-checking identity/frontend references.",
        ],
    }


def build_configuration_proposal(catalogue: dict[str, Any], donor_key: str,
                                target_name: str) -> dict[str, Any]:
    """Create a review-only field proposal; never emit an executable AMOD/NFSMS."""
    profiles = catalogue.get("vehicle_profiles", {})
    if donor_key not in profiles:
        raise ValueError(f"Donor profile not found: {donor_key}")
    donor = profiles[donor_key]
    configs = donor.get("configurations", {})
    proposals = []
    preserved = ["vehicle identity", "model/geometry/texture references",
                 "frontend registration", "collection identity"]
    for cls in PERFORMANCE_CLASSES:
        records = configs.get(cls, [])
        for record in records:
            fields = record.get("fields", {})
            selected = {}
            omitted = []
            for field_name, value in fields.items():
                low = field_name.lower()
                if any(token in low for token in ("collection", "model", "name", "id", "ref", "frontend", "logo", "geometry", "texture")):
                    omitted.append(field_name)
                    continue
                if cls == "pvehicle" and field_name not in PVEHICLE_PERFORMANCE_FIELDS:
                    omitted.append(field_name)
                    continue
                # Until headers and VLT references are resolved, propose only
                # simple typed scalars. Raw nested blocks and path-like refs stay out.
                if not isinstance(value, (bool, int, float)):
                    omitted.append(field_name)
                    continue
                selected[field_name] = value
            if selected or omitted:
                proposals.append({
                    "class": cls,
                    "donor_collection": record.get("collection"),
                    "target_collection": None,
                    "fields": selected,
                    "omitted_fields": omitted,
                    "status": "review-required-target-mapping",
                })
    return {
        "proposal_version": 2,
        "mode": "hybrid-review-only",
        "target_vehicle": target_name,
        "donor_profile": donor_key,
        "donor_vehicle": _candidate_name(donor),
        "proposals": proposals,
        "preserved_identity_domains": preserved,
        "excluded_classes": ["ecar", "camerainfo", "frontend", "pvehicle identity fields"],
        "executable": False,
        "writes_performed": False,
        "required_before_execution": [
            "Resolve target collection names from the add-on NFSMS and local database inventory.",
            "Validate field types against Attribulina headers for every proposed field.",
            "Review external references and dependencies; do not transplant donor collection IDs blindly.",
            "Generate AMOD and pass Attribulina check plus strict dry-run.",
        ],
        "safety_note": "Review-only proposal. No database changes or executable install script generated.",
    }


def write_json(data: dict[str, Any], output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path
