#!/usr/bin/env python3
"""Compute the next 0.0.N-style release from git tags and versioning.json."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONING_PATH = ROOT / "versioning.json"
PYPROJECT_PATH = ROOT / "pyproject.toml"
INIT_PATH = ROOT / "src" / "sceneify" / "__init__.py"
LOCK_PATH = ROOT / "uv.lock"
RELEASE_COMMIT_PREFIX = "chore(release):"
SKIP_RELEASE_TOKEN = "[skip release]"
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def run_git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def load_versioning() -> dict:
    data = json.loads(VERSIONING_PATH.read_text(encoding="utf-8"))
    for key in ("major", "minor"):
        value = data.get(key)
        if not isinstance(value, int) or value < 0:
            raise SystemExit(f"versioning.json: {key!r} must be a non-negative integer")
    data.setdefault("userNotes", "")
    data.setdefault("commits", [])
    if not isinstance(data["userNotes"], str):
        raise SystemExit("versioning.json: userNotes must be a string")
    if not isinstance(data["commits"], list):
        raise SystemExit("versioning.json: commits must be an array")
    return data


def parse_version(tag: str) -> tuple[int, int, int] | None:
    match = VERSION_RE.match(tag.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def list_tags() -> list[str]:
    output = run_git("tag", "--list", "--sort=-v:refname", check=False)
    return [line.strip() for line in output.splitlines() if line.strip()]


def last_tag_on_branch() -> str | None:
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    tag = result.stdout.strip()
    return tag or None


def next_patch(major: int, minor: int, tags: list[str]) -> int:
    patches = [
        parsed[2]
        for tag in tags
        if (parsed := parse_version(tag)) is not None and parsed[0] == major and parsed[1] == minor
    ]
    return (max(patches) + 1) if patches else 1


def collect_commits(since_tag: str | None) -> list[str]:
    args = ["log", "--no-merges", "--pretty=format:%h %s"]
    if since_tag:
        args.append(f"{since_tag}..HEAD")
    lines = [line.strip() for line in run_git(*args, check=False).splitlines() if line.strip()]
    return [line for line in lines if not line.split(" ", 1)[-1].startswith(RELEASE_COMMIT_PREFIX)]


def head_subject() -> str:
    return run_git("log", "-1", "--format=%s", check=False)


def head_is_tagged() -> bool:
    result = subprocess.run(
        ["git", "describe", "--tags", "--exact-match", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def replace_first(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"failed to update version in {path}")
    path.write_text(updated, encoding="utf-8")


def write_version_files(version: str) -> None:
    replace_first(PYPROJECT_PATH, r'^version = "[^"]+"', f'version = "{version}"')
    replace_first(INIT_PATH, r'__version__ = "[^"]+"', f'__version__ = "{version}"')
    replace_first(
        LOCK_PATH,
        r'(name = "sceneify"\nversion = ")[^"]+(")',
        rf"\g<1>{version}\2",
    )


def build_notes(user_notes: str, commits: list[str], since_tag: str | None) -> str:
    sections: list[str] = []
    notes = user_notes.strip()
    if notes:
        sections.append(notes)
    heading = f"## Commits since {since_tag}" if since_tag else "## Commits"
    if commits:
        body = "\n".join(f"- {line}" for line in commits)
        sections.append(f"{heading}\n\n{body}")
    elif not notes:
        sections.append("No user-facing commits in this release.")
    return "\n\n".join(sections).strip() + "\n"


def write_output(**values: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        for key, value in values.items():
            print(f"{key}={value}")
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            if "\n" in value:
                handle.write(f"{key}<<EOF\n{value}\nEOF\n")
            else:
                handle.write(f"{key}={value}\n")


def skip(reason: str) -> int:
    print(reason)
    write_output(skipped="true", version="", tag="", notes_path="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the next version without writing files",
    )
    parser.add_argument(
        "--stamp-version",
        metavar="VERSION",
        help="Rewrite local version files to VERSION without committing",
    )
    args = parser.parse_args()

    if args.stamp_version:
        version = args.stamp_version.removeprefix("v")
        if parse_version(version) is None:
            raise SystemExit(f"invalid version: {args.stamp_version}")
        write_version_files(version)
        print(f"Stamped version {version}")
        return 0

    if SKIP_RELEASE_TOKEN in head_subject():
        return skip(f"Skipping release because the latest commit contains {SKIP_RELEASE_TOKEN}")
    if head_is_tagged():
        return skip("Skipping release because HEAD is already tagged")

    data = load_versioning()
    tags = list_tags()
    since_tag = last_tag_on_branch()
    commits = collect_commits(since_tag)
    if not commits:
        return skip("Skipping release because there are no new commits since the last tag")

    patch = next_patch(data["major"], data["minor"], tags)
    version = f"{data['major']}.{data['minor']}.{patch}"
    notes = build_notes(data["userNotes"], commits, since_tag)
    notes_path = Path(os.environ.get("RUNNER_TEMP", ROOT)) / "release-notes.md"

    print(f"Next version: {version}")
    print(f"Commits included: {len(commits)}")
    if args.dry_run:
        print(notes)
        write_output(skipped="true", version=version, tag=version, notes_path="")
        return 0

    notes_path.write_text(notes, encoding="utf-8")
    write_output(
        skipped="false",
        version=version,
        tag=version,
        notes_path=str(notes_path),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
