#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from build_projects_cmake import run_cmake_workflow
from build_projects_make import run_makefiles_in_export_dir


def parse_affected_projects(raw_json: str) -> list[str]:
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid --affected-projects-json value: {exc}") from exc

    if not isinstance(parsed, list):
        raise RuntimeError("--affected-projects-json must be a JSON list.")

    projects: list[str] = []
    for index, item in enumerate(parsed):
        if not isinstance(item, str):
            raise RuntimeError(
                "--affected-projects-json entries must be non-empty strings. "
                f"Invalid entry at index {index}: {item!r}"
            )

        project = item.strip()
        if not project:
            raise RuntimeError(
                "--affected-projects-json entries must be non-empty strings. "
                f"Invalid entry at index {index}: {item!r}"
            )

        projects.append(project)
    return projects


def record_failure(
    failures: list[str], project_label: str, phase: str, return_code: int | str
) -> None:
    print(f"FAILED: {project_label} :: {phase} (rc={return_code})")
    failures.append(f"{project_label} :: {phase} :: rc={return_code}")


def run_build_command(
    failures: list[str],
    project_label: str,
    phase: str,
    command: list[str],
    cwd: Path | None = None,
) -> bool:
    command_str = " ".join(command)
    if cwd:
        print(f"RUN: [{project_label}] phase={phase} cwd={cwd} cmd={command_str}")
    else:
        print(f"RUN: [{project_label}] phase={phase} cmd={command_str}")

    try:
        completed = subprocess.run(command, cwd=str(cwd) if cwd else None, check=False)
    except FileNotFoundError:
        record_failure(failures, project_label, phase, 127)
        return False
    except OSError as exc:
        record_failure(failures, project_label, phase, exc.errno or 1)
        return False

    if completed.returncode == 0:
        return True

    record_failure(failures, project_label, phase, completed.returncode)
    return False


def build_slc_generate_command(
    project_file: str,
    export_dir: Path,
    toolchain: str,
    hardware: str | None,
) -> list[str]:
    command = [
        "slc",
        "generate",
        project_file,
        f"--export-destination={export_dir}",
        f"--toolchain={toolchain}",
    ]
    if hardware:
        command.append(f"--with={hardware}")
    command.append("--new-project")
    command.append("--daemon")
    command.append("--copy-sources")
    return command


def clean_export_dir(path: Path, build_root: Path) -> None:
    path_resolved = path.resolve()
    build_root_resolved = build_root.resolve()

    try:
        path_resolved.relative_to(build_root_resolved)
    except ValueError as exc:
        raise RuntimeError(
            "Refusing to clean directory outside build root: "
            f"{path_resolved} (root: {build_root_resolved})"
        ) from exc

    print(f"Cleaning export directory: {path_resolved}")
    shutil.rmtree(path_resolved, ignore_errors=True)
    path_resolved.mkdir(parents=True, exist_ok=True)


def load_hardware_mapping(hardware_json_path: str) -> dict[str, str | None]:
    """Load project -> hardware mapping.

    Present entries with no assigned hardware map to None.
    Projects absent from the JSON are not included in the returned dict.
    """
    path = hardware_json_path.strip()
    if not path:
        raise RuntimeError("--hardware-json is required and cannot be empty.")

    json_path = Path(path)
    if not json_path.is_file():
        raise RuntimeError(f"--hardware-json file not found: {json_path}")

    try:
        raw = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"--hardware-json is not valid JSON: {exc}") from exc

    try:
        raw_projects = raw["projects"]
    except KeyError as exc:
        raise RuntimeError(
            "--hardware-json must contain a top-level 'projects' object "
            "mapping paths to hardware config."
        ) from exc

    if not isinstance(raw_projects, dict):
        raise RuntimeError("--hardware-json 'projects' value must be an object.")

    mapping: dict[str, str | None] = {}
    for project_path, config in raw_projects.items():
        if not isinstance(config, dict):
            raise RuntimeError(
                f"--hardware-json entry for '{project_path}' must be an object."
            )
        hardware = config.get("hardware")
        if hardware is None:
            mapping[str(project_path)] = None
            continue
        hardware_str = str(hardware).strip()
        mapping[str(project_path)] = hardware_str if hardware_str else None
    return mapping


def write_outputs(
    github_output: str,
    failed_builds: list[str],
    successful_builds: list[str],
) -> None:
    if not github_output:
        raise RuntimeError("GITHUB_OUTPUT path is not set. Pass --github-output or set GITHUB_OUTPUT.")

    failures_marker = "__BUILD_FAILURES__"
    successes_marker = "__BUILD_SUCCESSES__"
    total_builds = len(failed_builds) + len(successful_builds)
    lines = [
        f"builds_count={total_builds}",
        f"failures_count={len(failed_builds)}",
        f"successes_count={len(successful_builds)}",
        f"failures_list<<{failures_marker}",
        *failed_builds,
        failures_marker,
        f"successes_list<<{successes_marker}",
        *successful_builds,
        successes_marker,
    ]

    with Path(github_output).open("a", encoding="utf-8") as output_file:
        output_file.write("\n".join(lines))
        output_file.write("\n")


def cmake_candidate_dirs(
    export_dir: Path,
    project_stem: str,
    toolchain: str,
    is_workspace: bool,
) -> list[Path]:
    if is_workspace:
        return [
            export_dir / f"{project_stem}_{toolchain}_cmake",
            export_dir / f"{project_stem}_cmake",
        ]
    return [export_dir / f"cmake_{toolchain}"]


def preferred_makefile(project_stem: str, is_workspace: bool) -> str:
    if is_workspace:
        return f"{project_stem}.solution.Makefile"
    return f"{project_stem}.Makefile"


def build_project(
    failures: list[str],
    project_file: str,
    build_dir: Path,
    hardware: str | None,
    toolchain: str,
) -> bool:
    """Generate and build one project. Returns True on success."""
    project_path = Path(project_file)
    project_stem = project_path.stem
    is_workspace = project_file.endswith(".slcw")
    export_dir = build_dir / hardware if hardware else build_dir
    project_label = f"{project_file} [{hardware}]" if hardware else project_file
    failures_before = len(failures)

    clean_export_dir(export_dir, build_dir)
    if not run_build_command(
        failures,
        project_label,
        "generate",
        build_slc_generate_command(
            project_file=project_file,
            export_dir=export_dir,
            toolchain=toolchain,
            hardware=hardware,
        ),
    ):
        return False

    cmake_result = run_cmake_workflow(
        failures,
        project_label,
        cmake_candidate_dirs(export_dir, project_stem, toolchain, is_workspace),
        run_command=run_build_command,
    )
    if cmake_result is not None:
        return cmake_result

    run_makefiles_in_export_dir(
        failures,
        project_label,
        export_dir,
        preferred_makefile(project_stem, is_workspace),
        run_command=run_build_command,
        record_failure_entry=record_failure,
    )
    return len(failures) == failures_before


def project_label_for(project_file: str, hardware: str | None) -> str:
    return f"{project_file} [{hardware}]" if hardware else project_file


def build_projects(
    affected_projects: list[str],
    all_projects: bool,
    github_output: str,
    toolchain: str,
    hardware_json_path: str = "",
) -> int:
    failures: list[str] = []
    failed_builds: list[str] = []
    successful_builds: list[str] = []

    print("Building projects...")
    print(f"Projects: {json.dumps(affected_projects)}")
    print(f"All-projects mode: {'true' if all_projects else 'false'}")
    print(f"Toolchain: {toolchain}")
    print(f"Hardware JSON path: {hardware_json_path}")

    try:
        hardware_mapping = load_hardware_mapping(hardware_json_path)
    except (RuntimeError, KeyError, TypeError, AttributeError) as exc:
        print(str(exc), file=sys.stderr)
        record_failure(failures, "configuration", "hardware-selection", 1)
        failed_builds.append("configuration :: hardware-selection")
        write_outputs(github_output, failed_builds, successful_builds)
        return 1

    for project_file in affected_projects:
        if not project_file.endswith((".slcw", ".slcp")):
            raise RuntimeError(
                f"Unsupported project file type: {project_file}. "
                "Expected .slcw or .slcp."
            )

        project_path = Path(project_file)
        if not project_path.is_file():
            print(f"Warning: project file not found (likely deleted): {project_file}")
            continue

        build_dir = project_path.parent / "build"

        print("==============================================")
        print(f"Building project: {project_file}")
        print("==============================================")

        if project_file not in hardware_mapping:
            record_failure(failures, project_file, "hardware-resolution", 1)
            failed_builds.append(project_file)
            print(
                f"No hardware mapping entry found for project '{project_file}' "
                f"in hardware mapping JSON.",
                file=sys.stderr,
            )
            continue

        hardware = hardware_mapping[project_file]
        label = project_label_for(project_file, hardware)
        if hardware:
            print(f"Building {project_path.stem} for hardware {hardware}")
        else:
            print(f"Building {project_path.stem} with no hardware (--with omitted)")

        if build_project(
            failures,
            project_file,
            build_dir,
            hardware,
            toolchain,
        ):
            successful_builds.append(label)
        else:
            failed_builds.append(label)

    write_outputs(github_output, failed_builds, successful_builds)

    if not all_projects and failed_builds:
        print("One or more projects failed.")
        return 1

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build projects for CI workflow.")
    parser.add_argument(
        "--affected-projects-json",
        default=os.environ.get("AFFECTED_PROJECTS", "[]"),
        help="JSON array of affected project paths (.slcp / .slcw).",
    )
    parser.add_argument(
        "--all-projects",
        default=os.environ.get("ALL_PROJECTS", "false"),
        help="Whether all-projects mode is enabled ('true'/'false').",
    )
    parser.add_argument(
        "--github-output",
        default=os.environ.get("GITHUB_OUTPUT", ""),
        help="Path to GitHub output file.",
    )
    parser.add_argument(
        "--toolchain",
        default=os.environ.get("TOOLCHAIN", "gcc"),
        help="Toolchain name to pass through to slc generate (default: gcc).",
    )
    parser.add_argument(
        "--hardware-json",
        default=os.environ.get("HARDWARE_JSON_PATH", ""),
        help="Path to JSON mapping project paths to hardware identifiers.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    affected_projects = parse_affected_projects(args.affected_projects_json)
    toolchain = str(args.toolchain).strip()
    if not toolchain:
        raise RuntimeError("--toolchain cannot be empty.")

    raw_all_projects = args.all_projects
    normalized_all_projects = str(raw_all_projects).strip().lower()
    if normalized_all_projects == "true":
        all_projects = True
    elif normalized_all_projects == "false":
        all_projects = False
    else:
        raise RuntimeError(
            f"Invalid --all-projects value '{raw_all_projects}'. Expected true/false."
        )

    return build_projects(
        affected_projects=affected_projects,
        all_projects=all_projects,
        github_output=args.github_output,
        toolchain=toolchain,
        hardware_json_path=str(args.hardware_json),
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
