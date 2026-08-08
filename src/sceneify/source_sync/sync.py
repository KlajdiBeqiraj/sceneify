"""High-level save/report API for editor <-> Python source sync."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from sceneify.scene import Scene
from sceneify.source_sync.ast_patch import analyze_source, patch_source_ast
from sceneify.source_sync.emit import emit_build_scene
from sceneify.source_sync.markers import (
    BEGIN_MARKER,
    END_MARKER,
    replace_marked_region,
    wrap_with_markers,
)

SyncMode = Literal["json", "markers", "ast", "auto"]


@dataclass
class SourceSyncReport:
    mode: str
    patchable: bool
    patchable_ids: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    has_markers: bool = False
    script_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def source_sync_report(path: str | Path | None = None, source: str | None = None) -> SourceSyncReport:
    text = source
    script_path = str(path) if path is not None else None
    if text is None and path is not None:
        file_path = Path(path)
        text = file_path.read_text(encoding="utf-8") if file_path.is_file() else ""
    if text is None:
        text = ""
    analysis = analyze_source(text)
    return SourceSyncReport(
        mode=analysis.mode,
        patchable=analysis.patchable,
        patchable_ids=analysis.patchable_ids,
        blockers=analysis.blockers,
        has_markers=analysis.has_markers or (BEGIN_MARKER in text and END_MARKER in text),
        script_path=script_path,
    )


def save_python(
    scene: Scene,
    path: str | Path,
    *,
    mode: SyncMode = "auto",
) -> tuple[Path, SourceSyncReport]:
    """Write or patch a Python authoring script for ``scene``.

    Modes:
    - markers: rewrite/create the marked ``build_scene`` region
    - ast: patch literal authoring calls when safe, else fall back to markers
    - auto: prefer ast when patchable, else markers
    - json: not applicable (caller should use Scene.save)
    """
    target = Path(path)
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    report = source_sync_report(path=target, source=existing)
    resolved: SyncMode
    if mode == "auto":
        resolved = "ast" if report.patchable else "markers"
    elif mode == "json":
        raise ValueError("save_python does not write JSON; use Scene.save")
    else:
        resolved = mode

    if resolved == "ast" and existing:
        patched, analysis = patch_source_ast(existing, scene)
        if analysis.patchable:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(patched, encoding="utf-8")
            return target, SourceSyncReport(
                mode="ast",
                patchable=True,
                patchable_ids=analysis.patchable_ids,
                blockers=analysis.blockers,
                has_markers=analysis.has_markers,
                script_path=str(target),
            )
        # Fall through to markers.

    body = emit_build_scene(scene)
    if existing.strip():
        text = replace_marked_region(existing, body)
    else:
        text = (
            '"""Sceneify authoring script (synced from editor)."""\n\n'
            + wrap_with_markers(body)
            + "\n\nif __name__ == '__main__':\n"
            + "    scene = build_scene()\n"
            + "    scene.run()\n"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target, SourceSyncReport(
        mode="markers",
        patchable=False,
        patchable_ids=report.patchable_ids,
        blockers=report.blockers,
        has_markers=True,
        script_path=str(target),
    )
