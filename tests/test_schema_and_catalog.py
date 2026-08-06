"""Tests for versioned scene documents and asset catalogs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from sceneify import Asset, AssetCatalog, Scene
from sceneify.io import SCENE_FORMAT, SCENE_VERSION, load_scene_dict


def test_scene_document_requires_supported_identity(tmp_path: Path) -> None:
    scene = Scene("versioned")
    path = scene.save(tmp_path / "scene.json")
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["format"] == SCENE_FORMAT
    assert document["version"] == SCENE_VERSION

    document["version"] = 3
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        load_scene_dict(path)


def test_raw_scene_payload_remains_supported(tmp_path: Path) -> None:
    path = tmp_path / "raw.json"
    path.write_text(json.dumps(Scene("raw").to_dict()), encoding="utf-8")
    assert Scene.load(path).name == "raw"


def test_catalog_roundtrip_and_duplicate_validation(tmp_path: Path) -> None:
    catalog = AssetCatalog(
        assets=[
            Asset(id="robot", path="assets/robot.glb", tags=["character"]),
            Asset(id="world", path="assets/world.glb", metadata={"kind": "level"}),
        ]
    )
    path = catalog.save(tmp_path / "catalog.json")
    loaded = AssetCatalog.load(path)
    assert loaded.get("robot").tags == ["character"]
    assert loaded.to_document()["format"] == "sceneify-asset-catalog"
    assert loaded.to_document()["version"] == 2
    assert loaded.get("robot").format == "glb"

    with pytest.raises(ValidationError, match="Duplicate asset ids"):
        AssetCatalog(
            assets=[
                Asset(id="same", path="one.glb"),
                Asset(id="same", path="two.glb"),
            ]
        )


def test_catalog_reads_v1_and_serializes_typed_v2(tmp_path: Path) -> None:
    path = tmp_path / "assets.catalog.json"
    path.write_text(
        json.dumps(
            {
                "format": "sceneify-asset-catalog",
                "version": 1,
                "assets": [
                    {
                        "id": "legacy",
                        "path": "assets/legacy.glb",
                        "tags": ["character"],
                        "metadata": {"author": "Sceneify"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    loaded = AssetCatalog.load(path)
    assert loaded.get("legacy").format == "glb"

    typed = Asset(
        id="remote",
        source="https://example.com/model.glb",
        license="CC0",
        checksum="sha256:abc",
        thumbnail="https://example.com/model.png",
        byteSize=42,
        animations=["idle"],
    )
    document = AssetCatalog(assets=[typed]).to_document()
    assert document["version"] == 2
    assert document["assets"][0]["byteSize"] == 42
    assert document["assets"][0]["format"] == "glb"


def test_public_json_schemas_are_versioned() -> None:
    root = Path(__file__).parents[1] / "schemas"
    scene_schema = json.loads((root / "scene.schema.json").read_text(encoding="utf-8"))
    catalog_schema = json.loads((root / "catalog.schema.json").read_text(encoding="utf-8"))
    assert scene_schema["properties"]["version"]["const"] == SCENE_VERSION
    assert scene_schema["properties"]["format"]["const"] == SCENE_FORMAT
    assert catalog_schema["properties"]["version"]["const"] == 2
