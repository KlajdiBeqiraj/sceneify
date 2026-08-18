"""Tests for remote asset search/fetch helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from sceneify.catalog import AssetCatalog
from sceneify.remote_assets import (
    fetch_remote_asset,
    get_remote_asset_info,
    list_remote_assets,
    search_remote_assets,
)


class _FakeResponse:
    def __init__(self, payload: Any = None, *, content: bytes | None = None) -> None:
        self._payload = payload
        self._content = content or b""
        self.status_code = 200
        self.headers: dict[str, str] = {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload

    def iter_bytes(self) -> Any:
        yield self._content

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class _FakeClient:
    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def get(self, url: str, params: dict[str, str] | None = None) -> _FakeResponse:
        del params
        if url not in self.routes:
            raise AssertionError(f"Unexpected GET {url}")
        return _FakeResponse(self.routes[url])


def _assets_payload() -> dict[str, Any]:
    return {
        "marble_bust_01": {
            "name": "Marble Bust 01",
            "tags": ["sculpture", "roman"],
            "categories": ["props"],
            "download_count": 12000,
            "thumbnail_url": "https://example.test/bust.png",
        },
        "Barrel_01": {
            "name": "Barrel 01",
            "tags": ["prop"],
            "categories": ["props"],
            "download_count": 5000,
        },
        "Barrel_02": {
            "name": "Barrel 02",
            "tags": ["prop"],
            "categories": ["props"],
            "download_count": 4000,
        },
    }


def test_search_remote_assets_polyhaven(monkeypatch: pytest.MonkeyPatch) -> None:
    import sceneify.remote_assets as remote

    remote._ASSETS_CACHE.clear()

    def fake_client(*args: Any, **kwargs: Any) -> _FakeClient:
        del args, kwargs
        return _FakeClient({"https://api.polyhaven.com/assets": _assets_payload()})

    monkeypatch.setattr(remote.httpx, "Client", fake_client)
    page = search_remote_assets("marble", provider="polyhaven", limit=5)
    assert page["total"] == 1
    assert page["count"] == 1
    assert page["assets"][0]["id"] == "marble_bust_01"
    assert page["assets"][0]["license"] == "CC0-1.0"
    assert page["hasMore"] is False


def test_list_remote_assets_paginated(monkeypatch: pytest.MonkeyPatch) -> None:
    import sceneify.remote_assets as remote

    remote._ASSETS_CACHE.clear()

    def fake_client(*args: Any, **kwargs: Any) -> _FakeClient:
        del args, kwargs
        return _FakeClient({"https://api.polyhaven.com/assets": _assets_payload()})

    monkeypatch.setattr(remote.httpx, "Client", fake_client)
    first = list_remote_assets(query="barrel", offset=0, limit=1)
    assert first["total"] == 2
    assert first["count"] == 1
    assert first["hasMore"] is True
    assert first["nextOffset"] == 1
    second = list_remote_assets(query="barrel", offset=1, limit=1)
    assert second["count"] == 1
    assert second["hasMore"] is False


def test_get_remote_asset_info(monkeypatch: pytest.MonkeyPatch) -> None:
    import sceneify.remote_assets as remote

    def fake_client(*args: Any, **kwargs: Any) -> _FakeClient:
        del args, kwargs
        return _FakeClient(
            {
                "https://api.polyhaven.com/info/marble_bust_01": {
                    "name": "Marble Bust 01",
                    "description": "A bust",
                    "tags": ["sculpture"],
                    "categories": ["props"],
                    "authors": {"Artist": "All"},
                    "polycount": 1000,
                    "dimensions": [1, 2, 3],
                    "download_count": 9,
                    "thumbnail_url": "https://example.test/t.png",
                },
                "https://api.polyhaven.com/files/marble_bust_01": {
                    "gltf": {
                        "1k": {
                            "gltf": {
                                "url": "https://dl.example.test/m.gltf",
                                "size": 10,
                                "md5": "abc",
                                "include": {
                                    "m.bin": {"url": "https://dl.example.test/m.bin", "size": 4}
                                },
                            }
                        }
                    }
                },
            }
        )

    monkeypatch.setattr(remote.httpx, "Client", fake_client)
    info = get_remote_asset_info("marble_bust_01")
    assert info["name"] == "Marble Bust 01"
    assert info["polycount"] == 1000
    assert info["files"]["gltf"]["1k"]["totalBytesApprox"] == 14


def test_fetch_remote_asset_polyhaven(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sceneify.remote_assets as remote

    gltf_bytes = json.dumps(
        {
            "asset": {"version": "2.0"},
            "buffers": [{"uri": "marble.bin", "byteLength": 4}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 4}],
        }
    ).encode("utf-8")
    bin_bytes = b"bin!"
    files = {
        "gltf": {
            "1k": {
                "gltf": {
                    "url": "https://dl.example.test/marble_1k.gltf",
                    "size": len(gltf_bytes),
                    "md5": hashlib.md5(gltf_bytes).hexdigest(),
                    "include": {
                        "marble.bin": {
                            "url": "https://dl.example.test/marble.bin",
                            "size": len(bin_bytes),
                            "md5": hashlib.md5(bin_bytes).hexdigest(),
                        }
                    },
                }
            }
        }
    }

    def fake_client(*args: Any, **kwargs: Any) -> _FakeClient:
        del args, kwargs
        return _FakeClient({"https://api.polyhaven.com/files/marble_bust_01": files})

    def fake_stream(method: str, url: str, **kwargs: Any) -> _FakeResponse:
        del method, kwargs
        content = gltf_bytes if str(url).endswith(".gltf") else bin_bytes
        return _FakeResponse(content=content)

    monkeypatch.setattr(remote.httpx, "Client", fake_client)
    monkeypatch.setattr(remote.httpx, "stream", fake_stream)

    catalog_path = tmp_path / "assets.catalog.json"
    catalog = AssetCatalog().bind_path(catalog_path)
    asset = fetch_remote_asset(
        "marble_bust_01",
        catalog=catalog,
        catalog_id="marble-bust",
        cache_dir=tmp_path,
        resolution="1k",
    )
    assert asset.id == "marble-bust"
    assert asset.format == "glb"
    packed = Path(asset.path or "")
    assert packed.suffix == ".glb"
    assert packed.is_file()
    assert packed.read_bytes()[:4] == b"glTF"
    assert (tmp_path / "polyhaven" / "marble_bust_01" / "1k" / "marble.bin").is_file()
    assert catalog.get("marble-bust").source.endswith("marble_bust_01")
    persisted = AssetCatalog.load(catalog_path)
    assert persisted.get("marble-bust").format == "glb"


def test_fetch_remote_rejects_include_outside_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sceneify.remote_assets as remote

    files = {
        "gltf": {
            "1k": {
                "gltf": {
                    "url": "https://dl.example.test/model.gltf",
                    "size": 10,
                    "md5": hashlib.md5(b"gltf-bytes").hexdigest(),
                    "include": {
                        "../outside.bin": {
                            "url": "https://dl.example.test/outside.bin",
                            "size": 4,
                            "md5": hashlib.md5(b"bin!").hexdigest(),
                        }
                    },
                }
            }
        }
    }

    def fake_client(*args: Any, **kwargs: Any) -> _FakeClient:
        del args, kwargs
        return _FakeClient({"https://api.polyhaven.com/files/safe_model": files})

    def fake_stream(method: str, url: str, **kwargs: Any) -> _FakeResponse:
        del method, kwargs
        return _FakeResponse(content=b"gltf-bytes" if url.endswith(".gltf") else b"bin!")

    monkeypatch.setattr(remote.httpx, "Client", fake_client)
    monkeypatch.setattr(remote.httpx, "stream", fake_stream)

    with pytest.raises(ValueError, match="escapes its cache directory"):
        fetch_remote_asset("safe_model", cache_dir=tmp_path)
    assert not (tmp_path / "polyhaven" / "safe_model" / "outside.bin").exists()


def test_fetch_remote_asset_polyhaven_hdri(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sceneify.remote_assets as remote

    remote._ASSETS_CACHE.clear()
    content = b"hdr-bytes!!"
    files = {
        "hdri": {
            "1k": {
                "hdr": {
                    "url": "https://dl.example.test/kloppenheim_06_1k.hdr",
                    "size": len(content),
                    "md5": hashlib.md5(content).hexdigest(),
                },
                "exr": {
                    "url": "https://dl.example.test/kloppenheim_06_1k.exr",
                    "size": 8,
                    "md5": hashlib.md5(b"exr-data").hexdigest(),
                },
            }
        }
    }

    def fake_client(*args: Any, **kwargs: Any) -> _FakeClient:
        del args, kwargs
        return _FakeClient({"https://api.polyhaven.com/files/kloppenheim_06": files})

    def fake_stream(method: str, url: str, **kwargs: Any) -> _FakeResponse:
        del method, kwargs
        assert str(url).endswith(".hdr")
        return _FakeResponse(content=content)

    monkeypatch.setattr(remote.httpx, "Client", fake_client)
    monkeypatch.setattr(remote.httpx, "stream", fake_stream)

    catalog = AssetCatalog()
    asset = fetch_remote_asset(
        "kloppenheim_06",
        catalog=catalog,
        catalog_id="sky",
        cache_dir=tmp_path,
        resolution="1k",
        asset_type="hdris",
    )
    assert asset.id == "sky"
    assert asset.format == "hdr"
    assert Path(asset.path or "").is_file()
    assert "hdri" in asset.tags
    assert catalog.get("sky").metadata["assetType"] == "hdris"


def test_summarize_polyhaven_files_includes_hdri(monkeypatch: pytest.MonkeyPatch) -> None:
    import sceneify.remote_assets as remote

    def fake_client(*args: Any, **kwargs: Any) -> _FakeClient:
        del args, kwargs
        return _FakeClient(
            {
                "https://api.polyhaven.com/info/kloppenheim_06": {
                    "name": "Kloppenheim 06",
                    "tags": ["outdoor"],
                    "categories": ["skies"],
                    "authors": {"Greg": "All"},
                    "download_count": 1,
                },
                "https://api.polyhaven.com/files/kloppenheim_06": {
                    "hdri": {
                        "1k": {
                            "hdr": {
                                "url": "https://dl.example.test/k.hdr",
                                "size": 12,
                                "md5": "abc",
                            }
                        }
                    }
                },
            }
        )

    monkeypatch.setattr(remote.httpx, "Client", fake_client)
    info = get_remote_asset_info("kloppenheim_06")
    assert info["files"]["hdri"]["1k"]["format"] == "hdr"
    assert info["files"]["hdri"]["1k"]["hasHdr"] is True


def test_search_and_fetch_os3a(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sceneify.remote_assets as remote

    remote._ASSETS_CACHE.clear()
    projects_url = f"{remote.OS3A_DATA_ROOT}/projects.json"
    assets_url = f"{remote.OS3A_DATA_ROOT}/assets/pm-momuspark.json"
    glb_url = "https://raw.githubusercontent.com/example/repo/main/Floor_01.glb"
    glb_bytes = b"glb-bytes!"

    projects = [
        {
            "id": "pm-momuspark",
            "name": "MomusPark",
            "license": "CC0",
            "is_public": True,
            "asset_data_file": "assets/pm-momuspark.json",
        }
    ]
    assets = [
        {
            "id": "momuspark-floor",
            "name": "Floor_Tiles_Medium",
            "description": "Park floor",
            "model_file_url": glb_url,
            "is_public": True,
            "is_draft": False,
            "thumbnail_url": "https://example.test/floor.png",
            "metadata": {
                "file_size": len(glb_bytes),
                "attributes": [
                    {"trait_type": "Theme", "value": "Nature Park"},
                    {"trait_type": "Category", "value": "Environment"},
                    {"trait_type": "Type", "value": "Floor"},
                ],
            },
        },
        {
            "id": "momuspark-bench",
            "name": "Bench_01",
            "model_file_url": "https://raw.githubusercontent.com/example/repo/main/Bench.glb",
            "is_public": True,
            "is_draft": False,
            "metadata": {
                "file_size": 100,
                "attributes": [{"trait_type": "Type", "value": "Bench"}],
            },
        },
    ]

    def fake_client(*args: Any, **kwargs: Any) -> _FakeClient:
        del args, kwargs
        return _FakeClient({projects_url: projects, assets_url: assets})

    def fake_stream(method: str, url: str, **kwargs: Any) -> _FakeResponse:
        del method, kwargs
        assert url == glb_url
        return _FakeResponse(content=glb_bytes)

    monkeypatch.setattr(remote.httpx, "Client", fake_client)
    monkeypatch.setattr(remote.httpx, "stream", fake_stream)

    page = search_remote_assets("floor", provider="os3a", asset_type="environments", limit=5)
    assert page["provider"] == "os3a"
    assert page["total"] == 1
    assert page["assets"][0]["id"] == "momuspark-floor"

    info = get_remote_asset_info("momuspark-floor", provider="os3a")
    assert info["projectId"] == "pm-momuspark"
    assert info["files"]["glb"]["url"] == glb_url

    catalog = AssetCatalog()
    asset = fetch_remote_asset(
        "momuspark-floor",
        provider="os3a",
        catalog=catalog,
        catalog_id="park-floor",
        cache_dir=tmp_path,
        asset_type="environments",
    )
    assert asset.format == "glb"
    assert Path(asset.path or "").is_file()
    assert (tmp_path / "os3a" / "pm-momuspark" / "momuspark-floor").is_dir()
    assert catalog.get("park-floor").metadata["provider"] == "os3a"
