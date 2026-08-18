"""Tests for packing multi-file glTF into a viewer-loadable GLB."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from sceneify.gltf_pack import pack_gltf_to_glb
from sceneify.scene import Scene
from sceneify.server import create_app


def _tiny_gltf(tmp_path: Path) -> Path:
    gltf = tmp_path / "model.gltf"
    blob = tmp_path / "model.bin"
    blob.write_bytes(b"bin!")
    gltf.write_text(
        json.dumps(
            {
                "asset": {"version": "2.0"},
                "buffers": [{"uri": "model.bin", "byteLength": 4}],
                "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 4}],
                "images": [{"uri": "model.bin"}],
            }
        ),
        encoding="utf-8",
    )
    return gltf


def test_pack_gltf_to_glb_inlines_relative_includes(tmp_path: Path) -> None:
    packed = pack_gltf_to_glb(_tiny_gltf(tmp_path))
    data = packed.read_bytes()
    assert packed.suffix == ".glb"
    assert data[:4] == b"glTF"
    assert b"model.bin" not in data
    assert b"bin!" in data


def test_packed_glb_is_served_by_asset_endpoint(tmp_path: Path) -> None:
    packed = pack_gltf_to_glb(_tiny_gltf(tmp_path))
    scene = Scene("packed")
    app = create_app(scene, realtime=False, project_root=tmp_path)
    with TestClient(app) as client:
        response = client.get("/api/asset", params={"path": packed.name})
        assert response.status_code == 200
        assert response.content[:4] == b"glTF"
