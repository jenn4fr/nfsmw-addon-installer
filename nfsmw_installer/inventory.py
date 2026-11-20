from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


_CLASS_RE = re.compile(r"^([A-Za-z0-9_]+)\s+\((\d+)\)$")


def parse_class_list(output: str) -> list[tuple[str, int]]:
    """Parse attribcli list DATABASE output into (class, collection_count)."""
    result = []

    for line in output.splitlines():
        match = _CLASS_RE.match(line.strip())
        if match:
            result.append((match.group(1), int(match.group(2))))

    return result


def parse_collection_tree(output: str, class_name: str) -> list[dict]:
    """Parse an indented attribcli class listing, preserving full paths."""
    records = []
    stack = []

    for raw in output.splitlines():
        if not raw.strip():
            continue

        name = raw.strip()
        indent = len(raw) - len(raw.lstrip())

        while stack and stack[-1]["indent"] >= indent:
            stack.pop()

        parent_path = stack[-1]["path"] if stack else ""
        path = f"{parent_path}/{name}" if parent_path else name

        records.append({
            "class": class_name,
            "name": name,
            "path": path,
            "depth": len(stack),
            "parent": parent_path or None,
        })

        stack.append({"indent": indent, "path": path})

    return records


def _run(executable: Path, args: list[str], timeout: int) -> str:
    completed = subprocess.run(
        [str(executable), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(
            f"Attribulina command failed ({completed.returncode}): {message}"
        )

    return completed.stdout


def build_inventory(
    executable: Path,
    databases: dict[str, Path],
    timeout: int = 180,
) -> dict:
    """Read-only inventory builder for multiple MW databases."""
    nodes = set()
    collections = set()
    fields = []
    database_reports = {}

    for database_name, database_path in databases.items():
        database_path = Path(database_path)

        class_output = _run(
            executable,
            ["list", str(database_path)],
            timeout,
        )
        classes = parse_class_list(class_output)

        class_reports = {}

        for class_name, count in classes:
            tree_output = _run(
                executable,
                ["list", str(database_path), class_name],
                timeout,
            )
            records = parse_collection_tree(tree_output, class_name)

            for record in records:
                full_path = record["path"]
                leaf_name = record["name"]

                # Full hierarchy plus leaf alias support the current analyzer.
                nodes.add(f"{class_name}/{leaf_name}")
                nodes.add(f"{class_name}/{full_path}")

                # Store both complete paths and class/leaf aliases.
                collections.add(f"{class_name}/{full_path}")
                collections.add(f"{class_name}/{leaf_name}")

            class_reports[class_name] = {
                "collection_count_reported": count,
                "collections": records,
            }

        database_reports[database_name] = {
            "path": str(database_path.resolve()),
            "class_count": len(classes),
            "classes": class_reports,
        }

    return {
        "inventory_version": 1,
        "tool": "nfsmw-addon-installer",
        "nodes": sorted(nodes),
        "collections": sorted(collections),
        "fields": fields,
        "databases": database_reports,
        "source_paths": [
            str(Path(path).resolve()) for path in databases.values()
        ],
    }


def write_inventory(inventory: dict, output: Path) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(inventory, indent=2),
        encoding="utf-8",
    )
    return output
