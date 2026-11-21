#!/usr/bin/env python3
"""Verify preserved reference archive bytes and saved real-package analysis evidence."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reference_packages" / "manifest.json"
REPORTS = {
    "amc_rebel": (ROOT / "reports" / "reference-amc-rebel-analysis.json", "REBEL", {"unlimiter_addon"}),
    "bugatti_chiron": (ROOT / "reports" / "reference-bugatti-chiron-analysis.json", "CHIRON16", {"unlimiter_addon", "classic_modloader_replacement"}),
    "fast_n_furious_flip_car": (ROOT / "reports" / "reference-flip-car-analysis.json", "FLIPCAR", {"unlimiter_addon"}),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    archive_results = []
    errors = []
    for item in manifest.get("archives", []):
        path = ROOT / "reference_packages" / item["filename"]
        exists = path.is_file()
        actual_size = path.stat().st_size if exists else None
        actual_hash = sha256(path) if exists else None
        ok = exists and actual_size == item["size_bytes"] and actual_hash == item["sha256"]
        archive_results.append({"filename": item["filename"], "exists": exists,
                                "expected_size": item["size_bytes"], "actual_size": actual_size,
                                "expected_sha256": item["sha256"], "actual_sha256": actual_hash,
                                "status": "PASS" if ok else "FAIL"})
        if not ok:
            errors.append(f"Reference archive missing or changed: {item['filename']}")

    report_results = []
    for name, (path, expected_car, expected_profiles) in REPORTS.items():
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            cars = set(report.get("car_ids", []))
            profiles = {entry.get("id") for entry in report.get("profiles", [])}
            ok = expected_car in cars and profiles == expected_profiles
            detail = {"name": name, "exists": True, "car_ids": sorted(cars),
                      "profiles": sorted(profiles), "status": "PASS" if ok else "FAIL"}
        except (OSError, json.JSONDecodeError) as exc:
            ok = False
            detail = {"name": name, "exists": False, "error": str(exc), "status": "FAIL"}
        report_results.append(detail)
        if not ok:
            errors.append(f"Reference analysis report invalid: {name}")

    return {"schema_version": "1.0", "status": "PASS" if not errors else "FAIL",
            "archive_checks": archive_results, "analysis_report_checks": report_results,
            "errors": errors}


def main() -> int:
    result = verify()
    out = ROOT / "reports" / "reference-bundle-verification.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for item in result["archive_checks"]:
        print(f"{item['status']}: archive {item['filename']}")
    for item in result["analysis_report_checks"]:
        print(f"{item['status']}: analysis {item['name']} ({', '.join(item.get('car_ids', []))})")
    print("Report:", out)
    print("Overall:", result["status"])
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
