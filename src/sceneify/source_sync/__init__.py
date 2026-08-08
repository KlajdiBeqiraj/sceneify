"""Round-trip helpers: Scene <-> Python source (JSON / markers / AST)."""

from sceneify.source_sync.ast_patch import analyze_source, patch_source_ast
from sceneify.source_sync.emit import emit_build_scene
from sceneify.source_sync.markers import (
    BEGIN_MARKER,
    END_MARKER,
    replace_marked_region,
    wrap_with_markers,
)
from sceneify.source_sync.sync import SourceSyncReport, save_python, source_sync_report

__all__ = [
    "BEGIN_MARKER",
    "END_MARKER",
    "SourceSyncReport",
    "analyze_source",
    "emit_build_scene",
    "patch_source_ast",
    "replace_marked_region",
    "save_python",
    "source_sync_report",
    "wrap_with_markers",
]
