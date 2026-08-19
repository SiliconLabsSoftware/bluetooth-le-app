#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

# Posix style paths are expected.
SLC_FILE_INDEX_RELATIVE_PATH = "./slc_file_index.json"
FULL_COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")


def resolve_base_commit_sha(repo_root: Path, explicit_base_sha: str, pr_base_sha: str) -> str:

    explicit_base_sha = explicit_base_sha.strip()
    pr_base_sha = pr_base_sha.strip()

    if explicit_base_sha and not FULL_COMMIT_SHA_PATTERN.fullmatch(explicit_base_sha):
        raise RuntimeError(
            "Base commit SHA from --base-commit-sha/BASE_COMMIT_SHA must be a full 40-character hexadecimal commit SHA: "
            f"{explicit_base_sha!r}"
        )
    if pr_base_sha and not FULL_COMMIT_SHA_PATTERN.fullmatch(pr_base_sha):
        raise RuntimeError(
            "Base commit SHA from --pr-base-sha/PR_BASE_SHA must be a full 40-character hexadecimal commit SHA: "
            f"{pr_base_sha!r}"
        )

    base_commit_sha = explicit_base_sha or pr_base_sha
    if not base_commit_sha:
        raise RuntimeError(
            "Missing base commit SHA. No valid explicit_base_sha or pr_base was provided."
        )

    try:
        subprocess.run(
            ["git", "cat-file", "-e", f"{base_commit_sha}^{{commit}}"],
            cwd=str(repo_root),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        raise RuntimeError(
            f"Base commit SHA is not available in local git history: {base_commit_sha}\n"
            f"{stderr}\n"
            "Fetch the missing commit into the clone, or provide a reachable base commit SHA."
        ) from exc
    return base_commit_sha


def changed_files(repo_root: Path, base_commit_sha: str) -> list[str]:
    diff = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMRD", f"{base_commit_sha}...HEAD"],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=True,
    )
    changed = []
    seen = set()
    for line in diff.stdout.splitlines():
        item = line.strip()
        if item and item not in seen:
            seen.add(item)
            changed.append(item)
    return changed


def generate_index_file_from_conan(repo_root: Path) -> Path:
    slc_file_index_json = json.loads(
        subprocess.run(
            ["conan", "export", ".", "--format=json"],
            cwd=str(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    reference = str(slc_file_index_json.get("reference", "")).strip()

    cache_root = Path(
        subprocess.run(
            ["conan", "cache", "path", reference],
            cwd=str(repo_root),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    ).resolve(strict=False)
    index_file = cache_root / SLC_FILE_INDEX_RELATIVE_PATH
    if not index_file.is_file():
        raise RuntimeError(f"Expected index file not found: {index_file} Check the Conan export step.")
    return index_file


def detect_affected_projects(
    index_file: Path,
    changed_paths: list[str],
    repo_root: Path,
    all_projects: bool = False,
) -> list[str]:
    project_index: dict[str, list[str]] = json.loads(index_file.read_text(encoding="utf-8"))

    affected_slcp: set[str] = set()
    affected_slcw: set[str] = set()

    if all_projects:
        for project_key in project_index.keys():
            if project_key.endswith(".slcp"):
                affected_slcp.add(project_key)
            elif project_key.endswith(".slcw"):
                affected_slcw.add(project_key)
    else:
        for changed_path in changed_paths:
            for project_key, deps in project_index.items():
                project_deps = set(deps)
                project_deps.add(project_key)
                if changed_path not in project_deps:
                    continue
                if project_key.endswith(".slcp"):
                    affected_slcp.add(project_key)
                elif project_key.endswith(".slcw"):
                    affected_slcw.add(project_key)

    for slcp in list(affected_slcp):
        project_path = repo_root.joinpath(slcp)
        if not project_path.is_file():
            continue
        # If the slcp file contains a companion tag it means it can be built
        # only part of bigger slcw project. It will be checked as part of the slcw project later.
        slcp_data = yaml.safe_load(project_path.read_text(encoding="utf-8"))
        tags = slcp_data.get("tag", [])
        if not isinstance(tags, list):
            tags = [tags]
        companions = []
        for tag in tags:
            if isinstance(tag, str) and tag.startswith("companion:"):
                companions.append(tag.split(":", 1)[1])
        if companions:
            affected_slcp.discard(slcp)

    for slcp in affected_slcp:
        slcp_paths = set(project_index.get(slcp, [])) | {slcp}
        for slcw_key, deps in project_index.items():
            if not slcw_key.endswith(".slcw") or slcw_key in affected_slcw:
                continue
            if slcp_paths & (set(deps) | {slcw_key}):
                affected_slcw.add(slcw_key)

    return sorted(affected_slcp | affected_slcw)


def build_parser() -> argparse.ArgumentParser:
    expected_index_location = str(SLC_FILE_INDEX_RELATIVE_PATH)
    parser = argparse.ArgumentParser(
        description=(
            "Resolve affected .slcp/.slcw projects using the Conan export index. "
            "Affected-only mode compares HEAD against a base commit; --all-projects skips git diff filtering "
            "and returns all indexed .slcp/.slcw projects except companion-tagged .slcp projects."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Prerequisites:\n"
            "  - --repo-root must point at the repository root containing conanfile.py.\n"
            "  - conan must be installed and able to resolve the exported recipe cache.\n"
            f"  - The Conan cache must contain slc_file_index.json at: {expected_index_location}.\n"
            "  - Affected-only mode requires --base-commit-sha or --pr-base-sha/PR_BASE_SHA.\n"
            "\n"
            "Outputs:\n"
            "  - Default stdout prints status lines followed by a JSON object like:\n"
            '      {"affected_projects": ["example/foo.slcp"]}\n'
            "  - --json-only prints only that JSON object to stdout.\n"
            "  - --github-output appends affected_projects_json, affected_projects_count,\n"
            "    and affected_projects_list to the GitHub Actions output file.\n"
            "\n"
            "Examples:\n"
            "  - Affected-only mode with explicit base SHA:\n"
            "      python3 .github/scripts/detect_affected_projects.py --repo-root . \\\n"
            "        --base-commit-sha <40-character-sha>\n"
            "  - Affected-only mode using PR_BASE_SHA from the environment:\n"
            "      PR_BASE_SHA=<40-character-sha> python3 .github/scripts/detect_affected_projects.py --repo-root .\n"
            "  - All-projects mode:\n"
            "      python3 .github/scripts/detect_affected_projects.py --repo-root . --all-projects\n"
            "  - Machine-readable stdout only:\n"
            "      python3 .github/scripts/detect_affected_projects.py --repo-root . --all-projects --json-only\n"
        ),
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root path. Must point at the repo root containing conanfile.py.",
    )
    parser.add_argument(
        "--base-commit-sha",
        default="",
        help="Explicit full 40-character base commit SHA for git diff. Takes precedence over --pr-base-sha.",
    )
    parser.add_argument(
        "--pr-base-sha",
        default=os.environ.get("PR_BASE_SHA", ""),
        help="PR base commit SHA. Defaults to PR_BASE_SHA when omitted. Must be a full 40-character SHA.",
    )
    parser.add_argument(
        "--github-output",
        default=os.environ.get("GITHUB_OUTPUT", ""),
        help="Optional GitHub Actions output file path. Defaults to GITHUB_OUTPUT when set.",
    )
    parser.add_argument(
        "--all-projects",
        action="store_true",
        dest="all_projects",
        help="Return all indexed .slcp/.slcw projects (excluding companion-tagged .slcp)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print only the final JSON payload to stdout. Default mode prints status lines before the JSON payload.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve(strict=False)
    index_file = generate_index_file_from_conan(repo_root)
    if not index_file.is_file():
        raise RuntimeError(f"Index file not found: {index_file}")
    if args.all_projects:
        affected = detect_affected_projects(index_file, [], repo_root, all_projects=True)
        if not args.json_only:
            print("Using all-projects mode")
    else:
        base_commit_sha = resolve_base_commit_sha(repo_root, args.base_commit_sha, args.pr_base_sha)
        changed = changed_files(repo_root, base_commit_sha)
        affected = detect_affected_projects(index_file, changed, repo_root)
        if not args.json_only:
            print(f"Using base commit SHA: {base_commit_sha}")
            print(f"Changed files: {len(changed)}")
    if not args.json_only:
        print(f"Affected projects: {len(affected)}")
    print(json.dumps({"affected_projects": affected}, indent=2))

    if args.github_output:
        affected_json = json.dumps(affected)
        payload = [
            f"affected_projects_json={affected_json}",
            f"affected_projects_count={len(affected)}",
            "affected_projects_list<<__AFFECTED_PROJECTS__",
            *affected,
            "__AFFECTED_PROJECTS__",
        ]
        output_path = Path(args.github_output)
        with output_path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(payload))
            handle.write("\n")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
