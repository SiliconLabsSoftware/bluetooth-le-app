from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

MAKEFILE_GLOB = "*.Makefile"


def run_makefiles_in_export_dir(
    failures: list[str],
    project_label: str,
    export_dir: Path,
    preferred_makefile: str,
    *,
    run_command: Callable[..., bool],
    record_failure_entry: Callable[..., None],
) -> None:
    jobs = os.cpu_count() or 1

    preferred_path = export_dir / preferred_makefile
    if preferred_path.is_file():
        print(f"Using preferred makefile: {preferred_makefile}")
        run_command(
            failures,
            project_label,
            "make",
            [
                "make",
                "-C",
                str(export_dir),
                "-f",
                preferred_makefile,
                f"-j{jobs}",
            ],
        )
        return

    found_makefile = False
    for makefile_path in sorted(export_dir.glob(MAKEFILE_GLOB)):
        if not makefile_path.is_file():
            continue
        found_makefile = True
        makefile_name = makefile_path.name
        print(f"Running makefile fallback: {makefile_name}")
        run_command(
            failures,
            project_label,
            "make",
            [
                "make",
                "-C",
                str(export_dir),
                "-f",
                makefile_name,
                f"-j{jobs}",
            ],
        )

    if not found_makefile:
        record_failure_entry(failures, project_label, "missing-makefile", 1)
