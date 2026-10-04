#!/usr/bin/env python3
"""Keyboard-driven MAME Explorer.

The user specifies a single MAME package (an archive, an extracted
directory, or the mame executable itself). Everything else -
extraction, running ``-listxml``, and locating ``hash/*.xml`` - is
resolved automatically. The tree is built only from that XML.
"""

from __future__ import annotations

import argparse
import curses
import hashlib
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ARCHIVE_SUFFIXES = {".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz"}


@dataclass
class Node:
    label: str
    properties: list[tuple[str, str]] = field(default_factory=list)
    loader: Callable[[], list["Node"]] | None = None
    children: list["Node"] = field(default_factory=list)
    expanded: bool = False
    loaded: bool = False

    def load(self) -> None:
        if not self.loaded and self.loader is not None:
            self.children = self.loader()
            self.loaded = True


# --- Package resolution -----------------------------------------------

def is_archive(path: Path) -> bool:
    return path.is_file() and (path.suffix in ARCHIVE_SUFFIXES or path.suffixes[-2:] == [".tar", ".gz"])


def extract_archive(archive: Path, cache_root: Path) -> Path:
    destination = cache_root / archive.stem
    if not destination.exists():
        destination.mkdir(parents=True)
        shutil.unpack_archive(str(archive), str(destination))
    return destination


def find_executable(base: Path) -> Path:
    for name in ("mame", "mame.exe"):
        direct = base / name
        if direct.is_file():
            return direct
    for name in ("mame", "mame.exe"):
        for candidate in base.rglob(name):
            if candidate.is_file():
                return candidate
    raise FileNotFoundError(f"mame executable not found under {base}")


def find_hash_dir(base: Path, executable: Path) -> Path | None:
    name = executable.stem
    candidates = (
        executable.parent / "hash",
        base / "hash",
        # FHS-style installs (e.g. Debian/Ubuntu apt packages) split the
        # executable (/usr/games/mame) from its data (/usr/share/games/mame/hash).
        executable.parent.parent / "share" / "games" / name / "hash",
        executable.parent.parent / "share" / name / "hash",
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    for candidate in base.rglob("hash"):
        if candidate.is_dir() and any(candidate.glob("*.xml")):
            return candidate
    return None


@dataclass
class Package:
    executable: Path
    hash_dir: Path | None


def resolve_package(path: Path) -> Package:
    if not path.exists():
        raise FileNotFoundError(f"Package not found: {path}")

    if path.is_file() and not is_archive(path):
        base = path.parent
        executable = path
    else:
        base = extract_archive(path, path.parent / ".mame-explorer-cache") if path.is_file() else path
        executable = find_executable(base)

    return Package(executable, find_hash_dir(base, executable))


def fetch_listxml(executable: Path) -> str:
    result = subprocess.run(
        [str(executable), "-listxml"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"-listxml failed: {result.stderr.strip()}")
    return result.stdout


def parse_listxml(text: str) -> ET.Element:
    root = ET.fromstring(text)
    if root.tag != "mame":
        raise ValueError("-listxml output did not have a <mame> root element.")
    return root


def run_listxml(executable: Path) -> ET.Element:
    return parse_listxml(fetch_listxml(executable))


# --- Real CHD verification (romdir cache; on-demand only, see run()) -----

def sha1_of_file(path: Path) -> str:
    hasher = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


# --- XML -> logical tree -------------------------------------------------

def element_properties(element: ET.Element, node_type: str) -> list[tuple[str, str]]:
    return [("type", node_type), *sorted(element.attrib.items())]


def is_file_rom(rom: ET.Element) -> bool:
    return "name" in rom.attrib and rom.get("loadflag", "") not in {
        "fill", "reload", "continue", "ignore", "reload_plain"
    }


def rom_node(rom: ET.Element) -> Node:
    properties = element_properties(rom, "ROM")
    properties.append(("isFileRom", "yes" if is_file_rom(rom) else "no"))
    return Node(rom.get("name", "(unnamed ROM)"), properties)


def disk_node(disk: ET.Element, part: ET.Element | None = None) -> Node:
    properties = element_properties(disk, "Disk")
    properties.append(("chdFileName", f"{disk.get('name', '')}.chd"))
    if part is not None:
        properties.append(("interface", part.get("interface", "")))
    return Node(f"{disk.get('name', '')}.chd", properties)


def part_node(part: ET.Element, rom_index: dict[str, list[str]] | None = None) -> Node:
    def load() -> list[Node]:
        nodes = [
            rom_node(rom)
            for area in part.findall("dataarea")
            for rom in area.findall("rom")
            if is_file_rom(rom)
        ]
        disks = [
            disk
            for area in part.findall("diskarea")
            for disk in area.findall("disk")
        ]
        if rom_index is not None:
            disks = [d for d in disks if _disk_name_in_index(d, rom_index)]
        nodes.extend(disk_node(disk, part) for disk in disks)
        return nodes

    label = f"{part.get('name', '')} [{part.get('interface', '')}]"
    return Node(label, element_properties(part, "Part"), load)


def software_node(software: ET.Element, rom_index: dict[str, list[str]] | None = None) -> Node:
    label = software.findtext("description") or software.get("name", "")

    def load() -> list[Node]:
        parts = software.findall("part")
        if rom_index is not None:
            # Keep only parts that contain at least one matching Disk
            kept: list[Node] = []
            for part in parts:
                has_disk = any(
                    _disk_name_in_index(disk, rom_index)
                    for area in part.findall("diskarea")
                    for disk in area.findall("disk")
                )
                if has_disk:
                    kept.append(part_node(part, rom_index))
            return kept
        return [part_node(part) for part in parts]

    return Node(label, element_properties(software, "Software"), load)


def software_list_node(path: Path) -> Node:
    def load() -> list[Node]:
        root = ET.parse(path).getroot()
        if root.tag != "softwarelist":
            return [Node("Unsupported XML", [("path", str(path))])]
        return [software_node(software) for software in root.findall("software")]

    root = ET.parse(path).getroot()
    label = root.get("description") or root.get("name") or path.name
    properties = element_properties(root, "Software List") + [("path", str(path))]
    return Node(label, properties, load)


def machine_node(machine: ET.Element, rom_index: dict[str, list[str]] | None = None) -> Node:
    def load() -> list[Node]:
        disks = machine.findall("disk")
        if rom_index is not None:
            disks = [d for d in disks if _disk_name_in_index(d, rom_index)]
        return [
            *[rom_node(rom) for rom in machine.findall("rom") if is_file_rom(rom)],
            *[disk_node(disk) for disk in disks],
        ]

    label = machine.findtext("description") or machine.get("name", "")
    return Node(label, element_properties(machine, "Arcade Game"), load)


def build_roots(package: Package) -> list[Node]:
    def load_arcade() -> list[Node]:
        return [machine_node(machine) for machine in run_listxml(package.executable).findall("machine")]

    roots = [Node("Arcade", [("type", "MAME listxml"), ("path", str(package.executable))], load_arcade)]

    if package.hash_dir is not None:
        files = sorted(package.hash_dir.glob("*.xml"))
        roots.append(Node(
            "Software Lists",
            [("type", "Software List directory"), ("path", str(package.hash_dir)), ("files", str(len(files)))],
            lambda: [software_list_node(path) for path in files],
        ))
    return roots


# --- Cache ("read arcade|softwarelist|romdir") ----------------------------

def cache_root() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return base / "mame-explorer"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_arcade_cache(source: Path, cache_dir: Path) -> str:
    package = resolve_package(source)
    text = fetch_listxml(package.executable)
    root = parse_listxml(text)
    (cache_dir / "arcade.xml").write_text(text)
    meta = {"source": str(package.executable), "build": root.get("build"), "created": _now()}
    (cache_dir / "arcade.meta.json").write_text(json.dumps(meta, indent=2))
    machine_count = len(root.findall("machine"))
    return f"Arcade cache written: {machine_count} machines, build={meta['build']} ({cache_dir / 'arcade.xml'})"


def resolve_hash_dir(source: Path) -> Path:
    if source.is_dir() and any(source.glob("*.xml")):
        return source
    package = resolve_package(source)
    if package.hash_dir is None:
        raise FileNotFoundError(f"No hash directory found from: {source}")
    return package.hash_dir


def write_softwarelist_cache(source: Path, cache_dir: Path) -> str:
    hash_dir = resolve_hash_dir(source)
    files = sorted(hash_dir.glob("*.xml"))
    meta = {"hash_dir": str(hash_dir), "files": len(files), "created": _now()}
    (cache_dir / "softwarelist.meta.json").write_text(json.dumps(meta, indent=2))
    return f"Software List cache written: {len(files)} XML files from {hash_dir}"


def write_romdir_cache(rom_dir: Path, cache_dir: Path) -> str:
    if not rom_dir.is_dir():
        raise FileNotFoundError(f"Not a directory: {rom_dir}")
    index: dict[str, list[str]] = {}
    for chd_path in rom_dir.rglob("*.chd"):
        if chd_path.is_file():
            index.setdefault(chd_path.name, []).append(str(chd_path))
    total_files = sum(len(v) for v in index.values())
    meta = {"root": str(rom_dir), "files": total_files, "created": _now()}
    (cache_dir / "romdir.meta.json").write_text(json.dumps(meta, indent=2))
    (cache_dir / "romdir.index.json").write_text(json.dumps(index, indent=2))
    return f"ROM directory cache written: {total_files} .chd files, {len(index)} unique name(s) from {rom_dir}"


def load_rom_index(cache_dir: Path) -> dict[str, list[str]] | None:
    path = cache_dir / "romdir.index.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def build_roots_from_cache(cache_dir: Path) -> list[Node]:
    roots: list[Node] = []

    arcade_xml = cache_dir / "arcade.xml"
    arcade_meta_path = cache_dir / "arcade.meta.json"
    if arcade_xml.is_file():
        meta = json.loads(arcade_meta_path.read_text()) if arcade_meta_path.is_file() else {}

        def load_arcade() -> list[Node]:
            root = parse_listxml(arcade_xml.read_text())
            return [machine_node(machine) for machine in root.findall("machine")]

        properties = [("type", "MAME listxml (cached)")] + [(k, str(v)) for k, v in meta.items()]
        roots.append(Node("Arcade", properties, load_arcade))

    softwarelist_meta_path = cache_dir / "softwarelist.meta.json"
    if softwarelist_meta_path.is_file():
        meta = json.loads(softwarelist_meta_path.read_text())
        hash_dir = Path(meta["hash_dir"])
        files = sorted(hash_dir.glob("*.xml")) if hash_dir.is_dir() else []
        properties = [("type", "Software List directory (cached)")] + [(k, str(v)) for k, v in meta.items()]
        roots.append(Node(
            "Software Lists",
            properties,
            lambda: [software_list_node(path) for path in files],
        ))

    return roots


def _disk_name_in_index(disk: ET.Element, rom_index: dict[str, list[str]]) -> bool:
    name = disk.get("name")
    if not name:
        return False
    return f"{name}.chd" in rom_index


def _machine_has_matching_disk(machine: ET.Element, rom_index: dict[str, list[str]]) -> bool:
    return any(_disk_name_in_index(disk, rom_index) for disk in machine.findall("disk"))


def _software_has_matching_disk(software: ET.Element, rom_index: dict[str, list[str]]) -> bool:
    for part in software.findall("part"):
        for area in part.findall("diskarea"):
            for disk in area.findall("disk"):
                if _disk_name_in_index(disk, rom_index):
                    return True
    return False


def build_roots_chd_mode(cache_dir: Path, rom_index: dict[str, list[str]]) -> list[Node]:
    """Same two roots as normal cache browse, but only keep branches that have a Disk present in rom_index."""
    roots: list[Node] = []

    arcade_xml = cache_dir / "arcade.xml"
    arcade_meta_path = cache_dir / "arcade.meta.json"
    if arcade_xml.is_file():
        meta = json.loads(arcade_meta_path.read_text()) if arcade_meta_path.is_file() else {}

        def load_arcade() -> list[Node]:
            root = parse_listxml(arcade_xml.read_text())
            return [
                machine_node(machine, rom_index)
                for machine in root.findall("machine")
                if _machine_has_matching_disk(machine, rom_index)
            ]

        properties = [
            ("type", "MAME listxml (cached, CHD mode)"),
            ("filter", "only machines with a Disk present in romdir cache"),
        ] + [(k, str(v)) for k, v in meta.items()]
        roots.append(Node("Arcade", properties, load_arcade))

    softwarelist_meta_path = cache_dir / "softwarelist.meta.json"
    if softwarelist_meta_path.is_file():
        meta = json.loads(softwarelist_meta_path.read_text())
        hash_dir = Path(meta["hash_dir"])
        files = sorted(hash_dir.glob("*.xml")) if hash_dir.is_dir() else []

        def load_software_lists() -> list[Node]:
            result: list[Node] = []
            for path in files:
                try:
                    root = ET.parse(path).getroot()
                except ET.ParseError:
                    continue
                if root.tag != "softwarelist":
                    continue
                matching = [
                    software_node(software, rom_index)
                    for software in root.findall("software")
                    if _software_has_matching_disk(software, rom_index)
                ]
                if not matching:
                    continue
                label = root.get("description") or root.get("name") or path.name
                properties = element_properties(root, "Software List") + [
                    ("path", str(path)),
                    ("filter", "only software with a Disk present in romdir cache"),
                ]
                # Pre-loaded children so the list itself is already filtered
                node = Node(label, properties)
                node.children = matching
                node.loaded = True
                result.append(node)
            return result

        properties = [
            ("type", "Software List directory (cached, CHD mode)"),
            ("filter", "only lists/software with a Disk present in romdir cache"),
        ] + [(k, str(v)) for k, v in meta.items()]
        roots.append(Node("Software Lists", properties, load_software_lists))

    return roots


# --- Keyboard-driven CUI --------------------------------------------------

def visible_nodes(nodes: list[Node], depth: int = 0) -> list[tuple[Node, int]]:
    rows: list[tuple[Node, int]] = []
    for node in nodes:
        rows.append((node, depth))
        if node.expanded:
            node.load()
            rows.extend(visible_nodes(node.children, depth + 1))
    return rows


def node_property(node: Node, key: str) -> str | None:
    for name, value in node.properties:
        if name == key:
            return value
    return None


def build_candidates(node: Node, rom_index: dict[str, list[str]]) -> list[dict]:
    chd_name = node_property(node, "chdFileName")
    if not chd_name:
        return []
    candidates = []
    for path_str in rom_index.get(chd_name, []):
        path = Path(path_str)
        try:
            stat = path.stat()
            size: int | None = stat.st_size
            mtime: str | None = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
        except OSError:
            size = None
            mtime = None
        candidates.append({"path": path_str, "size": size, "mtime": mtime, "sha1_result": None})
    return candidates


def _default_extract_output(chd_path: Path, interface: str | None) -> Path:
    """Default output path in the current directory, extension based on interface."""
    stem = chd_path.stem
    iface = (interface or "").lower()
    if "hdd" in iface or "harddisk" in iface or "sasi" in iface:
        return Path.cwd() / f"{stem}.img"
    # cdrom and everything else: cue (chdman extractcd also writes bin)
    return Path.cwd() / f"{stem}.cue"


def _chdman_command(chd_path: Path, output: Path, interface: str | None) -> list[str]:
    iface = (interface or "").lower()
    if "hdd" in iface or "harddisk" in iface or "sasi" in iface:
        return ["chdman", "extracthd", "-i", str(chd_path), "-o", str(output)]
    return ["chdman", "extractcd", "-i", str(chd_path), "-o", str(output)]


def extract_chd(chd_path: Path, output: Path, interface: str | None) -> str:
    """Run chdman extract. Returns a short status message."""
    if shutil.which("chdman") is None:
        return "chdman not found (install mame-tools or MAME)."
    if not chd_path.is_file():
        return f"CHD not found: {chd_path}"
    if output.exists():
        return f"Output exists, refuse to overwrite: {output}"
    cmd = _chdman_command(chd_path, output, interface)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError as error:
        return f"Failed to run chdman: {error}"
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip().splitlines()
        detail = err[-1] if err else f"exit {result.returncode}"
        return f"chdman failed: {detail}"
    return f"Extracted: {output}"


def draw(
    screen: curses.window,
    rows: list[tuple[Node, int]],
    selected: int,
    offset: int,
    show_properties: bool,
    status: str,
    focus_mode: str,
    candidates: list[dict],
    candidate_selected: int,
) -> None:
    screen.erase()
    height, width = screen.getmaxyx()
    visible_height = max(1, height - 2)
    left_width = width if not show_properties else max(30, width * 3 // 5)
    header = "MAME Explorer  Enter: open  Left: close  /: search  P: properties  Tab: CHD candidates  Q: quit"
    screen.addnstr(0, 0, header, width - 1)
    for i, (node, depth) in enumerate(rows[offset : offset + visible_height]):
        row = i + 1
        has_children = bool(node.loader) or (node.loaded and bool(node.children))
        marker = "+" if node.expanded else ">" if has_children else " "
        attribute = curses.A_REVERSE if focus_mode == "tree" and offset + i == selected else curses.A_NORMAL
        screen.addnstr(row, 0, f"{'  ' * depth}{marker} {node.label}", left_width - 1, attribute)
    if show_properties and rows:
        screen.vline(1, left_width, curses.ACS_VLINE, height - 2)
        if candidates:
            screen.addnstr(1, left_width + 2, f"{len(candidates)} CHD candidate(s):", width - left_width - 3)
            for row, candidate in enumerate(candidates[: height - 3], 2):
                index = row - 2
                result = candidate["sha1_result"] or "not checked"
                text = f"{candidate['path']}  size={candidate['size']}  mtime={candidate['mtime']}  sha1={result}"
                attribute = curses.A_REVERSE if focus_mode == "detail" and index == candidate_selected else curses.A_NORMAL
                screen.addnstr(row, left_width + 2, text, width - left_width - 3, attribute)
        else:
            node = rows[min(selected, len(rows) - 1)][0]
            for row, (key, value) in enumerate(node.properties[: height - 2], 1):
                screen.addnstr(row, left_width + 2, f"{key}: {value}", width - left_width - 3)
    screen.addnstr(height - 1, 0, status, width - 1, curses.A_DIM)
    screen.refresh()


def prompt(screen: curses.window, label: str) -> str:
    height, _ = screen.getmaxyx()
    screen.move(height - 1, 0)
    screen.clrtoeol()
    screen.addstr(height - 1, 0, label)
    curses.echo()
    value = screen.getstr(height - 1, len(label)).decode(errors="replace").strip()
    curses.noecho()
    return value


def run(screen: curses.window, roots: list[Node], rom_index: dict[str, list[str]] | None = None) -> None:
    curses.curs_set(0)
    selected = 0
    offset = 0
    show_properties = True
    status = "Select a node."
    focus_mode = "tree"
    candidates: list[dict] = []
    candidate_selected = 0
    disk_interface: str | None = None
    while True:
        rows = visible_nodes(roots)
        selected = max(0, min(selected, len(rows) - 1))
        height, _ = screen.getmaxyx()
        visible_height = max(1, height - 2)
        if selected < offset:
            offset = selected
        elif selected >= offset + visible_height:
            offset = selected - visible_height + 1
        offset = max(0, min(offset, max(0, len(rows) - visible_height)))
        draw(screen, rows, selected, offset, show_properties, status, focus_mode, candidates, candidate_selected)
        key = screen.getch()
        if key in (ord("q"), ord("Q")):
            return
        if key == 9:  # Tab
            if focus_mode == "tree":
                node = rows[selected][0]
                if rom_index is not None and node_property(node, "type") == "Disk":
                    candidates = build_candidates(node, rom_index)
                    disk_interface = node_property(node, "interface")
                    candidate_selected = 0
                    if candidates:
                        focus_mode = "detail"
                        status = f"{len(candidates)} candidate(s). Enter: extract. Tab: back to tree."
                    else:
                        status = "No CHD candidates found."
                else:
                    status = "Not a Disk node, or no romdir cache loaded."
            else:
                focus_mode = "tree"
            continue
        if focus_mode == "detail":
            if key == curses.KEY_UP:
                candidate_selected = max(0, candidate_selected - 1)
            elif key == curses.KEY_DOWN:
                candidate_selected = min(len(candidates) - 1, candidate_selected + 1)
            elif key in (10, 13):
                # Not a ROM checker: just extract. Success = chdman exited cleanly.
                candidate = candidates[candidate_selected]
                chd_path = Path(candidate["path"])
                default_out = _default_extract_output(chd_path, disk_interface)
                answer = prompt(screen, f"Output [{default_out}]: ").strip()
                output = Path(answer) if answer else default_out
                status = extract_chd(chd_path, output, disk_interface)
            continue
        if key == curses.KEY_UP:
            selected -= 1
        elif key == curses.KEY_DOWN:
            selected += 1
        elif key in (10, 13, curses.KEY_RIGHT):
            node = rows[selected][0]
            if node.loader:
                try:
                    node.load()
                    node.expanded = True
                except Exception as error:
                    status = f"Error: {error}"
            elif node.loaded and node.children:
                # Pre-loaded children (e.g. CHD mode Software List nodes)
                node.expanded = True
        elif key == curses.KEY_LEFT:
            rows[selected][0].expanded = False
        elif key in (ord("p"), ord("P")):
            show_properties = not show_properties
        elif key == ord("/"):
            query = prompt(screen, "Search: ").lower()
            matches = [index for index, (node, _) in enumerate(rows) if query in node.label.lower()]
            status = "No match." if not matches else f"{len(matches)} match(es)."
            if matches:
                selected = matches[0]


USAGE_EXAMPLES = """\
Usage examples:
  mame_explorer.py /usr/games/mame
  mame_explorer.py read arcade /usr/games/mame
  mame_explorer.py read softwarelist /usr/games/mame
  mame_explorer.py read romdir /path/to/chd/root
  mame_explorer.py
  mame_explorer.py chd
"""


def main() -> None:
    args = sys.argv[1:]
    if "--usage" in args:
        print(USAGE_EXAMPLES, end="")
        return
    if args and args[0] == "read":
        main_read(args[1:])
        return
    if args and args[0] == "chd":
        main_chd(args[1:])
        return
    main_browse(args)


def main_read(args: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="mame-explorer read",
        description="Build a cache used by 'mame_explorer.py' (no 'package' argument) for browsing.",
    )
    parser.add_argument(
        "kind",
        choices=["arcade", "softwarelist", "romdir"],
        help=(
            "arcade: mame executable/package (runs -listxml); "
            "softwarelist: hash directory, or mame executable/package (hash dir auto-detected); "
            "romdir: directory to search recursively for *.chd files"
        ),
    )
    parser.add_argument("path", type=Path, help="Path matching the chosen 'kind' (see above).")
    parsed = parser.parse_args(args)

    cache_dir = cache_root()
    cache_dir.mkdir(parents=True, exist_ok=True)

    try:
        if parsed.kind == "arcade":
            summary = write_arcade_cache(parsed.path, cache_dir)
        elif parsed.kind == "softwarelist":
            summary = write_softwarelist_cache(parsed.path, cache_dir)
        else:
            summary = write_romdir_cache(parsed.path, cache_dir)
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        parser.error(str(error))
        return
    print(summary)


def main_chd(args: list[str]) -> None:
    """Browse caches in CHD mode: only branches that have a Disk present in the romdir cache."""
    parser = argparse.ArgumentParser(
        prog="mame-explorer chd",
        description=(
            "Browse Arcade / Software Lists caches in CHD mode.\n"
            "Only keeps branches that contain at least one Disk whose .chd file exists\n"
            "in the romdir cache (built by 'mame_explorer.py read romdir <path>').\n"
            "Requires a romdir cache; exits with an error if it is missing."
        ),
    )
    parser.parse_args(args)  # accept no extra args; still gives -h

    cache_dir = cache_root()
    rom_index = load_rom_index(cache_dir)
    if rom_index is None:
        parser.error(
            "No romdir cache found. Run 'mame_explorer.py read romdir <directory>' first."
        )
        return

    roots = build_roots_chd_mode(cache_dir, rom_index)
    if not roots:
        parser.error(
            "No Arcade / Software List cache found. "
            "Run 'mame_explorer.py read arcade|softwarelist <path>' first."
        )
        return

    curses.wrapper(run, roots, rom_index)


def main_browse(args: list[str]) -> None:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Keyboard-driven MAME Explorer.\n"
            "\n"
            "  mame_explorer.py <package>\n"
            "     Browses Arcade / Software Lists from <package> (a mame executable, a\n"
            "     directory containing one, or an archive containing one). Reads\n"
            "     listxml/hash fresh every run. This is the standard way to use this tool.\n"
            "\n"
            "Extension - build caches once, then reuse them:\n"
            "\n"
            "  mame_explorer.py read arcade <mame executable/package>\n"
            "  mame_explorer.py read softwarelist <hash dir, or mame executable/package>\n"
            "  mame_explorer.py read romdir <directory to search for *.chd files>\n"
            "  mame_explorer.py                 (no argument; browses the caches above)\n"
            "  mame_explorer.py chd             (CHD mode: only branches with a Disk\n"
            "                                   present in the romdir cache)\n"
            "\n"
            "'read romdir' adds real ROM/CHD verification (press Tab on a Disk node),\n"
            "which is not available when running with <package> directly.\n"
            "'chd' requires the romdir cache and prunes the tree to matching branches only.\n"
        ),
        epilog="Run 'mame_explorer.py --usage' for copy-pasteable command examples.",
    )
    parser.add_argument(
        "package",
        type=Path,
        nargs="?",
        help="MAME package for the standard direct mode (see above). Omit to browse cached 'read' data instead.",
    )
    parsed = parser.parse_args(args)

    cache_dir = cache_root()
    rom_index = load_rom_index(cache_dir)

    if parsed.package is not None:
        try:
            package = resolve_package(parsed.package)
        except (FileNotFoundError, ValueError) as error:
            parser.error(str(error))
            return
        roots = build_roots(package)
    else:
        roots = build_roots_from_cache(cache_dir)
        if not roots:
            parser.error("No cached data found. Run 'mame-explorer read arcade|softwarelist|romdir <path>' first.")
            return

    curses.wrapper(run, roots, rom_index)


if __name__ == "__main__":
    main()
