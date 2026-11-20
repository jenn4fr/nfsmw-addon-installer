from __future__ import annotations
import json, re, zipfile, shutil, subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

TEXT_EXTS = {'.txt', '.md', '.ini', '.nfsms', '.mwps', '.xml', '.json', '.cfg'}
MODEL_NAMES = {'geometry.bin', 'textures.bin'}

@dataclass
class FileInfo:
    path: str
    size: int
    kind: str

@dataclass
class ScriptCommand:
    line: int
    command: str
    args: list[str]
    raw: str

@dataclass
class Finding:
    severity: str
    code: str
    message: str
    line: int | None = None


def classify_file(name: str) -> str:
    p = Path(name); low = p.name.lower(); parts = [x.lower() for x in p.parts]
    if low in MODEL_NAMES: return 'car_model_or_texture'
    if low.endswith('.nfsms'): return 'vlt_script'
    if low.endswith('.mwps'): return 'binary_patch_script'
    if low == 'car.ini' or low.endswith('.ini'):
        return 'modloader_car_config' if low == 'car.ini' else 'unlimiter_or_mod_config'
    if low.endswith('.dds'): return 'texture_or_logo'
    if low in {'attributes.bin','fe_attrib.bin','secondarylogo.bin','globalmemoryfile.bin'}: return 'game_database_or_logo_binary'
    if 'cars_replace' in parts: return 'modloader_replacement_payload'
    if 'config' in parts and 'nfsmw' in parts: return 'unlimiter_config'
    if 'resources' in parts: return 'frontend_or_game_resource'
    if p.suffix.lower() in {'.txt','.md'}: return 'readme_or_documentation'
    return 'other'


def _read_archive(path: Path) -> tuple[list[FileInfo], dict[str, bytes], list[str]]:
    files: list[FileInfo] = []; data: dict[str, bytes] = {}; warnings=[]
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for i in z.infolist():
                if i.is_dir(): continue
                files.append(FileInfo(i.filename, i.file_size, classify_file(i.filename)))
                if Path(i.filename).suffix.lower() in TEXT_EXTS and i.file_size <= 2_000_000:
                    try: data[i.filename] = z.read(i)
                    except Exception as e: warnings.append(f'Could not read {i.filename}: {e}')
        return files, data, warnings
    seven = shutil.which('7z') or shutil.which('7zz')
    if seven:
        proc = subprocess.run([seven, 'l', '-slt', str(path)], capture_output=True, text=True)
        if proc.returncode == 0:
            for block in proc.stdout.split('----------'):
                m = re.search(r'^Path = (.+)$', block, re.M); sz = re.search(r'^Size = (\d+)$', block, re.M)
                if m and sz and not m.group(1).endswith('/'):
                    name=m.group(1); files.append(FileInfo(name, int(sz.group(1)), classify_file(name)))
            warnings.append('Archive listing only: extract this archive to a folder for content inspection and staging.')
            return files, data, warnings
    warnings.append('Unsupported archive for built-in reading. Extract it manually, then inspect the extracted folder. ZIP is supported directly; RAR/7z listing requires 7-Zip on PATH.')
    return files, data, warnings


def scan_folder(root: Path) -> tuple[list[FileInfo], dict[str, bytes], list[str]]:
    files=[]; data={}; warnings=[]
    for p in root.rglob('*'):
        if not p.is_file(): continue
        rel=p.relative_to(root).as_posix(); size=p.stat().st_size
        files.append(FileInfo(rel,size,classify_file(rel)))
        if p.suffix.lower() in TEXT_EXTS and size <= 2_000_000:
            try: data[rel]=p.read_bytes()
            except Exception as e: warnings.append(f'Could not read {rel}: {e}')
    return files,data,warnings


def strip_comment(line: str) -> str:
    # NFSMS comments use #; preserve quoted text if present.
    out=[]; quote=None
    for ch in line:
        if quote:
            if ch == quote: quote=None
            out.append(ch)
        elif ch in ('"', "'"):
            quote=ch; out.append(ch)
        elif ch == '#': break
        else: out.append(ch)
    return ''.join(out).strip()


def parse_nfsms(text: str) -> list[ScriptCommand]:
    result=[]
    for n,line in enumerate(text.splitlines(),1):
        clean=strip_comment(line)
        if not clean: continue
        # Ignore UI-only directives but retain them as commands for reporting.
        parts=re.findall(r'"[^"\n]*"|\S+', clean)
        parts=[x[1:-1] if len(x)>=2 and x[0]==x[-1] and x[0] in ('"',"'") else x for x in parts]
        result.append(ScriptCommand(n,parts[0].lower(),parts[1:],clean))
    return result


def discover_layout(files: list[FileInfo]) -> dict:
    kinds={}
    for f in files: kinds[f.kind]=kinds.get(f.kind,0)+1
    paths=[f.path.replace('\\','/').lower() for f in files]
    has_nfsms=any(p.endswith('.nfsms') for p in paths)
    has_mwps=any(p.endswith('.mwps') for p in paths)
    has_replace=any('cars_replace/' in p for p in paths)
    has_addon_model=any('/rebel/' in '/'+p or '/cars/' in '/'+p for p in paths) and any(Path(p).name in MODEL_NAMES for p in paths)
    types=[]
    if has_nfsms: types.append('VLT/NFSMS database installation')
    if has_mwps: types.append('Binary/MWPS patch installation')
    if has_replace: types.append('ModLoader replacement payload')
    if has_addon_model and not has_replace: types.append('Possible Unlimiter add-on model payload')
    if not types: types.append('Unclassified or manual installation')
    return {'detected_types':types,'file_type_counts':kinds,'confidence':'heuristic; verify against author instructions'}



def _analyze_scripts(text_files: dict[str, bytes], inventory: dict | None = None):
    """Analyze commands and build an ordered, per-script dependency graph."""
    commands = []
    findings = []
    graph = {"scripts": [], "nodes_created": [], "dependencies": []}
    inv_nodes = set((inventory or {}).get("nodes", []))
    inv_collections = set((inventory or {}).get("collections", []))

    for path, raw in text_files.items():
        if not path.lower().endswith(".nfsms"):
            continue

        text = raw.decode("utf-8-sig", errors="replace")
        parsed = parse_nfsms(text)
        future_creations = {}

        for index, command in enumerate(parsed):
            if command.command == "copy_node" and len(command.args) >= 4:
                cls, _src, _parent, dst = command.args[:4]
                future_creations.setdefault(f"{cls}/{dst}", []).append(index)

        created = {}
        script_created = []

        for index, command in enumerate(parsed):
            a = command.args
            cmd = command.command
            commands.append({
                "file": path, **asdict(command), "sequence": index + 1
            })

            if cmd == "copy_node" and len(a) >= 4:
                cls, src, parent, dst = a[:4]
                donor = f"{cls}/{src}"
                destination = f"{cls}/{dst}"
                donor_status = "inventory" if donor in inv_nodes else "unverified"

                graph["dependencies"].append({
                    "file": path, "line": command.line,
                    "sequence": index + 1, "kind": "copy_donor",
                    "reference": donor, "status": donor_status,
                })

                if inventory is not None and donor not in inv_nodes:
                    findings.append(Finding(
                        "warning", "DONOR_NODE_NOT_IN_INVENTORY",
                        f"Cannot confirm donor node {donor} exists in supplied inventory.",
                        command.line,
                    ))

                if parent.lower() != "default":
                    parent_node = f"{cls}/{parent}"

                    if parent_node in created:
                        parent_status = "created_earlier"
                        parent_line = created[parent_node]
                    elif parent_node in inv_nodes:
                        parent_status = "inventory_node"
                        parent_line = None
                    elif parent in inv_collections:
                        parent_status = "inventory_collection"
                        parent_line = None
                    else:
                        parent_status = "unverified"
                        parent_line = None

                    dependency = {
                        "file": path, "line": command.line,
                        "sequence": index + 1, "kind": "copy_parent",
                        "reference": parent_node, "status": parent_status,
                    }
                    if parent_line is not None:
                        dependency["created_at_line"] = parent_line
                    graph["dependencies"].append(dependency)

                if destination in created:
                    findings.append(Finding(
                        "warning", "DUPLICATE_NODE_CREATION",
                        f"Node {destination} is created more than once in this script.",
                        command.line,
                    ))

                created[destination] = command.line
                script_created.append(destination)
                graph["nodes_created"].append({
                    "file": path, "line": command.line,
                    "sequence": index + 1, "node": destination,
                    "donor": donor, "parent": parent,
                })

            elif cmd == "update_field" and len(a) >= 3:
                cls, node = a[:2]
                target = f"{cls}/{node}"

                dependency = {
                    "file": path, "line": command.line,
                    "sequence": index + 1, "kind": "update_target",
                    "reference": target,
                }

                if target in created:
                    dependency["status"] = "created_earlier"
                    dependency["created_at_line"] = created[target]
                elif target in inv_nodes:
                    dependency["status"] = "inventory"
                else:
                    later = [
                        n for n in future_creations.get(target, [])
                        if n > index
                    ]
                    if later:
                        creation = parsed[later[0]]
                        dependency["status"] = "created_later"
                        dependency["created_at_line"] = creation.line
                        findings.append(Finding(
                            "warning", "NODE_USED_BEFORE_CREATION",
                            f"Target node {target} is updated before its later copy_node creation on line {creation.line}.",
                            command.line,
                        ))
                    else:
                        dependency["status"] = "unverified"
                        if inventory is not None:
                            findings.append(Finding(
                                "warning", "TARGET_NODE_NOT_IN_INVENTORY",
                                f"Cannot confirm target node {target} exists in supplied inventory.",
                                command.line,
                            ))

                graph["dependencies"].append(dependency)

                if len(a) >= 5 and a[3].lower() == "collection":
                    ref = a[4]
                    field_class = a[2].split("[", 1)[0].lower()
                    collection_node = f"{field_class}/{ref}"

                    if collection_node in created:
                        collection_status = "created_earlier"
                        creation_line = created[collection_node]
                    elif (
                        collection_node in inv_collections
                        or collection_node in inv_nodes
                    ):
                        collection_status = "inventory"
                        creation_line = None
                    else:
                        later = [
                            n for n in future_creations.get(collection_node, [])
                            if n > index
                        ]
                        if later:
                            creation = parsed[later[0]]
                            collection_status = "created_later"
                            creation_line = creation.line
                            findings.append(Finding(
                                "warning", "COLLECTION_USED_BEFORE_CREATION",
                                f"Collection {collection_node!r} is referenced before its copy_node creation on line {creation.line}.",
                                command.line,
                            ))
                        else:
                            collection_status = "unverified"
                            creation_line = None
                            if inventory is not None:
                                findings.append(Finding(
                                    "warning", "COLLECTION_NOT_IN_INVENTORY",
                                    f"Collection reference {collection_node!r} is not listed in supplied inventory.",
                                    command.line,
                                ))

                    dependency = {
                        "file": path, "line": command.line,
                        "sequence": index + 1,
                        "kind": "collection_reference",
                        "reference": collection_node,
                        "status": collection_status,
                    }
                    if creation_line is not None:
                        dependency["created_at_line"] = creation_line

                    graph["dependencies"].append(dependency)

            elif cmd in {"file_copy", "copy_file"} and len(a) < 2:
                findings.append(Finding(
                    "error", "MALFORMED_FILE_COPY",
                    "file_copy command has fewer than two arguments.",
                    command.line,
                ))

            elif cmd == "script" and not a:
                findings.append(Finding(
                    "error", "MALFORMED_SCRIPT_INCLUDE",
                    "script include has no path.", command.line,
                ))

        graph["scripts"].append({
            "file": path,
            "command_count": len(parsed),
            "created_nodes": script_created,
        })

    unique = {
        (f.severity, f.code, f.message, f.line): f
        for f in findings
    }
    return commands, list(unique.values()), graph


def analyze_scripts(
    text_files: dict[str, bytes], inventory: dict | None = None
) -> tuple[list[dict], list[Finding]]:
    """Backward-compatible analysis API."""
    commands, findings, _graph = _analyze_scripts(text_files, inventory)
    return commands, findings

def make_report(source: Path, files: list[FileInfo], text_files: dict[str,bytes], warnings: list[str], inventory: dict|None=None) -> dict:
    layout=discover_layout(files); commands, findings, dependency_graph=_analyze_scripts(text_files,inventory)
    for w in warnings: findings.append(Finding('warning','SCAN_LIMITATION',w))
    ext_counts={}
    for f in files:
        ext=Path(f.path).suffix.lower() or '[no extension]'; ext_counts[ext]=ext_counts.get(ext,0)+1
    return {'tool_version':'0.1.0','source':str(source),'layout':layout,'file_count':len(files),'extension_counts':dict(sorted(ext_counts.items())),
            'files':[asdict(f) for f in files],'nfsms_commands':commands,'dependency_graph':dependency_graph,'findings':[asdict(f) for f in findings],
            'inventory_loaded':inventory is not None,
            'safety_note':'Analysis only. No game files or databases were modified.'}


def load_inventory(path: Path) -> dict:
    obj=json.loads(path.read_text(encoding='utf-8'))
    for key in ('nodes','collections','fields'):
        if key not in obj: obj[key]=[]
        if not isinstance(obj[key],list): raise ValueError(f'Inventory key {key!r} must be a list.')
    return obj
