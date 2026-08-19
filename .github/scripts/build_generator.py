#!/usr/bin/env python3
"""
Hardware assigner: convert templates.xml to a project-hardware mapping JSON.

For each example:
  - If boardCompatibility is non-empty (excluding com.silabs.board.none), assign
    a board by walking the preferred board list (first match wins). If no preferred
    board is compatible, warn and use the first compatible board.
  - Otherwise, assign a part by treating partCompatibility entries as regexes and
    checking them against the preferred part list (first match wins). If nothing
    matches, warn and leave the project without assigned hardware.
"""

import argparse
import fnmatch
import json
import re
import sys
import xml.etree.ElementTree as ET

# Preferred boards for Bluetooth LE projects.
DEFAULT_PREFERRED_BOARDS = [
    "brd2601b",
    "brd2602a",
    "brd2606a",
    "brd4109a",
    "brd2719a",
    "brd4185a",
    "brd4116a",
    "brd4184a",
    "brd4184b",
    "brd2608a",
]

# Preferred parts when boardCompatibility is empty (e.g. host apps).
DEFAULT_PREFERRED_PARTS = [
    "linux",
]


def get_property_value(descriptor: ET.Element, key: str) -> str | None:
    """Get the value of a property by key from a descriptor element."""
    for prop in descriptor.findall(".//properties"):
        if prop.get("key") == key:
            return prop.get("value")
    return None


def select_board(
    compatible_boards: list[str],
    preferred_boards: list[str],
    project_path: str,
) -> str | None:
    """Return the first preferred board that is compatible, else fall back."""
    compatible_set = set(compatible_boards)
    for board in preferred_boards:
        if board in compatible_set:
            return board
    if compatible_boards:
        print(
            f"Warning: no preferred board found for {project_path}; "
            f"using {compatible_boards[0]}",
            file=sys.stderr,
        )
        return compatible_boards[0]
    return None


def select_part(
    compatible_part_patterns: list[str],
    preferred_parts: list[str],
    project_path: str,
) -> str | None:
    """Return the first preferred part matching a partCompatibility regex."""
    for part in preferred_parts:
        for pattern in compatible_part_patterns:
            try:
                if re.search(pattern, part):
                    return part
            except re.error as exc:
                print(
                    f"Warning: invalid partCompatibility regex {pattern!r} "
                    f"for {project_path}: {exc}",
                    file=sys.stderr,
                )
    print(
        f"Warning: no preferred part matched for {project_path}; "
        f"not assigning hardware",
        file=sys.stderr,
    )
    return None


def parse_templates_xml(
    xml_path: str,
    toolchain: str,
    pattern: str | None = None,
    preferred_boards: list[str] | None = None,
    preferred_parts: list[str] | None = None,
    allow_hidden: bool = False,
) -> dict:
    """Parse templates.xml and return a project-hardware mapping."""
    if preferred_boards is None:
        preferred_boards = DEFAULT_PREFERRED_BOARDS
    if preferred_parts is None:
        preferred_parts = DEFAULT_PREFERRED_PARTS

    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Handle both with and without namespace (descriptors may be in no namespace)
    descriptors = root.findall(".//descriptors")
    if not descriptors:
        # Try with common namespace
        ns = {"model": "http://www.silabs.com/ss/Studio.ecore"}
        descriptors = root.findall(".//model:descriptors", ns)
    if not descriptors:
        descriptors = list(root.iter())
        descriptors = [e for e in descriptors if e.tag.endswith("descriptors") or e.tag == "descriptors"]

    projects: dict[str, dict[str, str]] = {}
    for desc in descriptors:
        name = desc.get("name")
        if not name:
            continue

        # Skip hidden entries unless explicitly allowed
        if not allow_hidden:
            hidden = get_property_value(desc, "hidden")
            if hidden == "true":
                continue

        project_file_paths_raw = get_property_value(desc, "projectFilePaths")
        board_compat_raw = get_property_value(desc, "boardCompatibility")
        part_compat_raw = get_property_value(desc, "partCompatibility")
        toolchains_raw = get_property_value(desc, "toolchainCompatibility")
        if not project_file_paths_raw or not toolchains_raw:
            continue
        if board_compat_raw is None and part_compat_raw is None:
            continue

        project_path = project_file_paths_raw.strip()
        boards = [
            b for b in (board_compat_raw or "").split()
            if b and b != "com.silabs.board.none"
        ]
        parts = [p for p in (part_compat_raw or "").split() if p]
        toolchains = toolchains_raw.split()

        if toolchain not in toolchains:
            continue

        if pattern and not fnmatch.fnmatch(project_path, pattern):
            continue

        if boards:
            hardware = select_board(boards, preferred_boards, project_path)
        elif parts:
            hardware = select_part(parts, preferred_parts, project_path)
        else:
            print(
                f"Warning: no board or part compatibility for {project_path}; "
                f"not assigning hardware",
                file=sys.stderr,
            )
            hardware = None

        entry: dict[str, str] = {}
        if hardware is not None:
            entry["hardware"] = hardware
        projects[project_path] = entry

    return {"projects": projects}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Assign hardware (board or part) to projects from templates.xml "
            "and emit a JSON mapping."
        ),
    )
    parser.add_argument(
        "xml_file",
        help="Path to templates.xml",
    )
    parser.add_argument(
        "-t", "--toolchain",
        default="gcc",
        help="Toolchain to filter for",
    )
    parser.add_argument(
        "-d", "--preferred-parts",
        help="Comma-separated preferred parts when boardCompatibility is empty "
             f"(default: {','.join(DEFAULT_PREFERRED_PARTS)})",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output JSON file (default: stdout)",
    )
    parser.add_argument(
        "-p", "--pattern",
        help="Pattern to filter project paths for",
    )
    parser.add_argument(
        "-b", "--preferred-boards",
        help="Comma-separated preferred boards (overrides the default list)",
    )
    parser.add_argument(
        "--allow-hidden",
        action="store_true",
        help="Include descriptors marked as hidden",
    )
    args = parser.parse_args()

    preferred_boards = DEFAULT_PREFERRED_BOARDS
    if args.preferred_boards:
        preferred_boards = [b.strip() for b in args.preferred_boards.split(",") if b.strip()]

    preferred_parts = DEFAULT_PREFERRED_PARTS
    if args.preferred_parts:
        preferred_parts = [p.strip() for p in args.preferred_parts.split(",") if p.strip()]

    try:
        result = parse_templates_xml(
            args.xml_file,
            args.toolchain,
            args.pattern,
            preferred_boards,
            preferred_parts,
            args.allow_hidden,
        )
    except FileNotFoundError:
        print(f"Error: file not found: {args.xml_file}", file=sys.stderr)
        return 1
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}", file=sys.stderr)
        return 1

    out = json.dumps(result, indent=4) + "\n"
    if args.output:
        with open(args.output, "w") as f:
            f.write(out)
    else:
        print(out, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
