from __future__ import annotations

from collections.abc import Callable
from pathlib import Path


def run_cmake_workflow(
    failures: list[str],
    project_label: str,
    cmake_preset_dirs: list[Path],
    *,
    run_command: Callable[..., bool],
) -> bool | None:
    for candidate_dir in cmake_preset_dirs:
        preset_path = candidate_dir / "CMakePresets.json"
        if not preset_path.is_file():
            continue

        print(f"Running CMake workflow from: {candidate_dir}")
        return run_command(
            failures,
            project_label,
            "cmake",
            ["cmake", "--workflow", "--preset", "project"],
            cwd=candidate_dir,
        )

    print("No CMake preset candidate found, falling back to makefiles.")
    return None
