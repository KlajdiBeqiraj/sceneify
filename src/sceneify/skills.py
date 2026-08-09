"""Bundled Agent Skills helpers for coding-agent hosts."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import as_file, files
from pathlib import Path

SKILL_NAME = "sceneify-mcp"

# Portable default first; host-specific paths for explicit installs.
TARGET_DIRS: dict[str, str] = {
    "agents": ".agents/skills",
    "cursor": ".cursor/skills",
    "claude": ".claude/skills",
    "codex": ".codex/skills",
}


def _repo_skill_dir() -> Path | None:
    candidate = Path(__file__).resolve().parents[2] / "skills" / SKILL_NAME
    return candidate if candidate.is_dir() else None


def _package_skill_resource():
    return files("sceneify").joinpath("skills", SKILL_NAME)


@contextmanager
def open_bundled_skill_dir() -> Iterator[Path]:
    """Yield a filesystem path to the bundled skill directory."""
    resource = _package_skill_resource()
    if resource.is_dir():
        with as_file(resource) as path:
            yield Path(path)
            return
    fallback = _repo_skill_dir()
    if fallback is not None:
        yield fallback
        return
    raise FileNotFoundError(
        f"Bundled skill {SKILL_NAME!r} was not found. Reinstall sceneify or run from the repo."
    )


def bundled_skill_dir() -> Path:
    """Return a stable path to the skill when available on disk (repo or extracted)."""
    fallback = _repo_skill_dir()
    if fallback is not None:
        return fallback
    resource = _package_skill_resource()
    if resource.is_dir():
        path_attr = getattr(resource, "_path", None)
        if isinstance(path_attr, Path) and path_attr.is_dir():
            return path_attr
    raise FileNotFoundError(
        f"Bundled skill {SKILL_NAME!r} is only available via install_skill() "
        "from this install layout. Use sceneify install-skill."
    )


def resolve_install_root(target: str, *, user: bool = False, base_dir: Path | None = None) -> Path:
    """Resolve the skills parent directory for a named host target."""
    key = target.lower()
    if key not in TARGET_DIRS:
        known = ", ".join([*sorted(TARGET_DIRS), "all"])
        raise ValueError(f"Unknown skill target {target!r}. Choose one of: {known}")
    relative = TARGET_DIRS[key]
    if user:
        return Path.home() / relative
    root = (base_dir or Path.cwd()).expanduser().resolve()
    return root / relative


def _copy_skill_tree(source: Path, destination: Path, *, force: bool) -> Path:
    if destination.exists():
        if not force:
            raise FileExistsError(
                f"{destination} already exists. Pass force=True / --force to replace it."
            )
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    return destination


def install_skill(
    *,
    target: str = "agents",
    user: bool = False,
    force: bool = False,
    base_dir: Path | None = None,
) -> list[Path]:
    """Copy the bundled sceneify MCP skill into one or more agent skill directories.

    Default ``target="agents"`` writes ``.agents/skills/sceneify-mcp``, the portable
    path recognized by Cursor, Codex, and other Agent Skills hosts. Use
    ``target="all"`` to also install Cursor/Claude/Codex-specific copies.
    """
    targets = list(TARGET_DIRS) if target.lower() == "all" else [target]
    installed: list[Path] = []
    with open_bundled_skill_dir() as source:
        for name in targets:
            parent = resolve_install_root(name, user=user, base_dir=base_dir)
            installed.append(_copy_skill_tree(source, parent / SKILL_NAME, force=force))
    return installed
