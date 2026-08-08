"""Tests for Scene <-> Python source sync."""

from __future__ import annotations

from pathlib import Path

from sceneify import Material, Physics, Scene
from sceneify.source_sync import (
    BEGIN_MARKER,
    END_MARKER,
    analyze_source,
    emit_build_scene,
    save_python,
    source_sync_report,
)


def _simple_scene() -> Scene:
    scene = Scene("Sync Test", background="#111111")
    scene.create_primitive(
        "box_a",
        "box",
        size=(1.0, 1.0, 1.0),
        position=(1.0, 0.5, 0.0),
        material=Material("#ff0000"),
        physics=Physics(body="fixed"),
    )
    scene.create_primitive(
        "ball",
        "sphere",
        radius=0.4,
        position=(-1.0, 0.4, 0.0),
        material=Material("#00ff00", roughness=0.2),
    )
    return scene


def test_emit_build_scene_is_one_call_per_node() -> None:
    body = emit_build_scene(_simple_scene())
    assert "def build_scene()" in body
    assert body.count("create_primitive(") == 2
    assert "box_a" in body and "ball" in body


def test_save_python_markers_roundtrip(tmp_path: Path) -> None:
    scene = _simple_scene()
    script = tmp_path / "world.py"
    path, report = save_python(scene, script, mode="markers")
    text = path.read_text(encoding="utf-8")
    assert report.mode == "markers"
    assert BEGIN_MARKER in text and END_MARKER in text
    assert "create_primitive(" in text

    # Simulate an editor move, then rewrite markers.
    scene._primitives["box_a"].position = (2.5, 0.5, 1.0)
    path, report = save_python(scene, script, mode="markers")
    updated = path.read_text(encoding="utf-8")
    assert "2.5" in updated
    assert updated.count(BEGIN_MARKER) == 1


def test_analyze_source_detects_loops() -> None:
    source = """
from sceneify import Scene
def build_scene():
    scene = Scene("x")
    for i in range(3):
        scene.create_primitive(f"p_{i}", "box")
    return scene
"""
    analysis = analyze_source(source)
    assert analysis.patchable is False
    assert any("for_stmt" in item for item in analysis.blockers)


def test_ast_patch_updates_transforms(tmp_path: Path) -> None:
    script = tmp_path / "simple.py"
    script.write_text(
        """
from sceneify import Scene

def build():
    scene = Scene("x")
    scene.create_primitive("box_a", "box", position=(0.0, 0.0, 0.0))
    scene.create_primitive("ball", "sphere", position=(1.0, 0.0, 0.0))
    return scene
""",
        encoding="utf-8",
    )
    scene = _simple_scene()
    scene._primitives["box_a"].position = (3.0, 0.5, 0.0)
    path, report = save_python(scene, script, mode="ast")
    text = path.read_text(encoding="utf-8")
    assert report.mode in {"ast", "markers"}
    assert "box_a" in text
    if report.mode == "ast":
        assert "3.0" in text


def test_source_sync_report_empty(tmp_path: Path) -> None:
    report = source_sync_report(path=tmp_path / "missing.py")
    assert report.mode in {"json", "markers"}
    assert report.patchable is False


def test_save_python_endpoint(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from sceneify.server import create_app

    scene = _simple_scene()
    app = create_app(scene, realtime=False, project_root=tmp_path)
    client = TestClient(app)
    response = client.post(
        "/api/scene/save-python",
        json={"path": "authored.py", "mode": "markers", "revision": 0},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["sync"]["mode"] == "markers"
    assert (tmp_path / "authored.py").is_file()
    status = client.get("/api/scene/source-sync", params={"path": "authored.py"})
    assert status.status_code == 200
    assert status.json()["has_markers"] is True
