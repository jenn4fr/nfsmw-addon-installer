"""Safe extraction for ZIP and external 7-Zip-supported archives."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


def _safe_member(name: str) -> str:
    normalized = name.replace("\\", "/")
    if not normalized or normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        raise ValueError(f"Archive contains an absolute path: {name!r}")
    parts = PurePosixPath(normalized).parts
    if not parts or any(part in {"..", ""} for part in parts):
        raise ValueError(f"Archive contains path traversal or an empty path: {name!r}")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    for part in parts:
        if ":" in part or part.endswith((".", " ")) or part.split(".", 1)[0].upper() in reserved:
            raise ValueError(f"Archive contains a Windows-unsafe path component: {name!r}")
    return "/".join(parts)


def _check_unique_members(entries: list[dict[str, Any]]) -> None:
    seen: dict[str, str] = {}
    for entry in entries:
        normalized = _safe_member(entry["path"])
        key = normalized.casefold()
        if key in seen:
            raise ValueError(f"Archive contains duplicate/case-colliding paths: {seen[key]!r} and {entry['path']!r}")
        seen[key] = entry["path"]


def _inside(root: Path, target: Path) -> bool:
    return target == root or root in target.parents


def find_7zip(explicit: str | Path | None = None) -> Path | None:
    if explicit:
        p = Path(explicit).expanduser()
        if p.is_file():
            return p.resolve()
        raise FileNotFoundError(f"7-Zip executable not found: {p}")
    for name in ("7z", "7zz", "7z.exe", "7zz.exe"):
        found = shutil.which(name)
        if found:
            return Path(found).resolve()
    if os.name == "nt":
        for candidate in (
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "7-Zip" / "7z.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "7-Zip" / "7z.exe",
        ):
            if candidate.is_file():
                return candidate.resolve()
    return None


def _list_7z(archive: Path, seven_zip: Path, timeout: int) -> list[dict[str, Any]]:
    completed = subprocess.run(
        [str(seven_zip), "l", "-slt", str(archive)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"7-Zip could not list archive: {completed.stderr.strip() or completed.stdout.strip()}")
    entries: list[dict[str, Any]] = []
    block: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        if not line.strip() or line.startswith("----------"):
            if block.get("Path") and block.get("Path") != str(archive):
                entries.append(block)
            block = {}
            continue
        if " = " in line:
            key, value = line.split(" = ", 1)
            block[key.strip()] = value.strip()
    if block.get("Path") and block.get("Path") != str(archive):
        entries.append(block)
    result = []
    for item in entries:
        name = item.get("Path", "")
        _safe_member(name)
        if item.get("Symbolic Link") or item.get("Hard Link"):
            raise ValueError(f"Archive links are not accepted: {name}")
        size = int(item.get("Size", "0") or 0)
        is_dir = item.get("Attributes", "").startswith("D") or name.endswith(("/", "\\"))
        result.append({"path": name, "size": size, "is_dir": is_dir})
    _check_unique_members(result)
    return result


def inspect_archive(path: str | Path, *, seven_zip: str | Path | None = None,
                    timeout: int = 180, max_unpacked_bytes: int = 5_000_000_000) -> dict[str, Any]:
    archive = Path(path).expanduser().resolve()
    if not archive.is_file():
        raise FileNotFoundError(f"Archive not found: {archive}")
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            entries = []
            total = 0
            for info in zf.infolist():
                _safe_member(info.filename)
                mode = (info.external_attr >> 16) & 0xFFFF
                if mode and (mode & 0o170000) == 0o120000:
                    raise ValueError(f"ZIP symbolic link is not accepted: {info.filename}")
                if info.is_dir():
                    entries.append({"path": info.filename, "size": 0, "is_dir": True})
                    continue
                total += info.file_size
                entries.append({"path": info.filename, "size": info.file_size, "is_dir": False})
            _check_unique_members(entries)
            if total > max_unpacked_bytes:
                raise ValueError(f"Archive expands to {total} bytes, over the configured limit")
            return {"archive": str(archive), "format": "zip", "entries": entries,
                    "file_count": sum(not e["is_dir"] for e in entries), "total_unpacked_bytes": total}
    seven = find_7zip(seven_zip)
    if not seven:
        raise RuntimeError("RAR/7z extraction requires 7-Zip. Install 7-Zip or pass --7zip PATH.")
    entries = _list_7z(archive, seven, timeout)
    total = sum(e["size"] for e in entries if not e["is_dir"])
    if total > max_unpacked_bytes:
        raise ValueError(f"Archive expands to {total} bytes, over the configured limit")
    return {"archive": str(archive), "format": "7zip", "entries": entries,
            "file_count": sum(not e["is_dir"] for e in entries),
            "total_unpacked_bytes": total, "seven_zip": str(seven)}


def extract_archive(path: str | Path, destination: str | Path, *,
                    seven_zip: str | Path | None = None, timeout: int = 300,
                    max_unpacked_bytes: int = 5_000_000_000) -> dict[str, Any]:
    archive = Path(path).expanduser().resolve()
    target = Path(destination).expanduser().resolve()
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"Extraction destination is not empty: {target}")
    target.mkdir(parents=True, exist_ok=True)
    info = inspect_archive(archive, seven_zip=seven_zip, timeout=min(timeout, 180),
                           max_unpacked_bytes=max_unpacked_bytes)
    try:
        if info["format"] == "zip":
            with zipfile.ZipFile(archive) as zf:
                for member in zf.infolist():
                    if member.is_dir():
                        continue
                    rel = _safe_member(member.filename)
                    out = (target / Path(*PurePosixPath(rel).parts)).resolve()
                    if not _inside(target, out):
                        raise ValueError(f"Archive member escapes extraction root: {member.filename}")
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, out.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
        else:
            seven = Path(info["seven_zip"])
            completed = subprocess.run(
                [str(seven), "x", str(archive), f"-o{target}", "-y", "-aoa"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=timeout, check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(f"7-Zip extraction failed: {completed.stderr.strip() or completed.stdout.strip()}")
            # Verify the extracted tree after extraction too (defence in depth).
            for p in target.rglob("*"):
                resolved = p.resolve()
                if not _inside(target, resolved):
                    raise ValueError(f"Extracted path escaped destination: {p}")
        actual_files = [p for p in target.rglob("*") if p.is_file()]
        return {**info, "destination": str(target), "extracted_file_count": len(actual_files),
                "extraction_verified": True}
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise
