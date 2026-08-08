"""Tests for static web export (frontend + backend loop)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sceneify import Scene
from sceneify.export_web import export_web
from sceneify.server import PACKAGE_WEB


def test_export_web_writes_viewer_config_and_packed_assets(tmp_path: Path) -> None:
    if not (PACKAGE_WEB / "index.html").is_file():
        pytest.skip("Bundled viewer missing")

    assets = tmp_path / "project" / "assets"
    assets.mkdir(parents=True)
    glb = assets / "crate.glb"
    glb.write_bytes(b"glTF" + b"\x00" * 8)

    scene = Scene("export-demo")
    scene.add_mesh("crate", glb, format="glb", position=(0, 0, 0))
    out = tmp_path / "dist-web"
    result = export_web(
        scene,
        out,
        api_base="http://127.0.0.1:9000",
        copy_assets=True,
        project_root=tmp_path / "project",
    )
    assert result == out.resolve()
    assert (out / "index.html").is_file()
    assert (out / "sceneify.config.json").is_file()
    assert (out / "scene.json").is_file()
    assert (out / "assets" / "crate.glb").is_file()

    config = json.loads((out / "sceneify.config.json").read_text(encoding="utf-8"))
    assert config["apiBase"] == "http://127.0.0.1:9000"
    assert config["assetMode"] == "static"
    assert "assets/crate.glb" in config["copiedAssets"]

    html = (out / "index.html").read_text(encoding="utf-8")
    assert "window.__SCENEIFY_CONFIG__" in html
    assert "http://127.0.0.1:9000" in html

    document = json.loads((out / "scene.json").read_text(encoding="utf-8"))
    assert document["scene"]["meshes"][0]["source"] == "assets/crate.glb"


def test_export_web_can_skip_asset_packing(tmp_path: Path) -> None:
    if not (PACKAGE_WEB / "index.html").is_file():
        pytest.skip("Bundled viewer missing")

    scene = Scene("no-pack")
    scene.add_mesh("remote", "https://example.com/model.glb", format="glb")
    out = export_web(scene, tmp_path / "out", copy_assets=False, api_base="")
    config = json.loads((out / "sceneify.config.json").read_text(encoding="utf-8"))
    assert config["apiBase"] == ""
    assert config["assetMode"] == "api"
    assert config["copiedAssets"] == []
    document = json.loads((out / "scene.json").read_text(encoding="utf-8"))
    assert document["scene"]["meshes"][0]["source"] == "https://example.com/model.glb"


def test_scene_export_web_helper(tmp_path: Path) -> None:
    if not (PACKAGE_WEB / "index.html").is_file():
        pytest.skip("Bundled viewer missing")
    scene = Scene("helper")
    path = scene.export_web(tmp_path / "bundle", api_base="http://localhost:8765")
    assert (path / "sceneify.config.json").is_file()
