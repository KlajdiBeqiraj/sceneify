"""Tests for remote asset search/fetch helpers."""

from __future__ import annotations

import hashlib
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

    files = {
        "gltf": {
            "1k": {
                "gltf": {
                    "url": "https://dl.example.test/marble_1k.gltf",
                    "size": 10,
                    "md5": hashlib.md5(b"gltf-bytes").hexdigest(),
                    "include": {
                        "marble.bin": {
                            "url": "https://dl.example.test/marble.bin",
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
        return _FakeClient({"https://api.polyhaven.com/files/marble_bust_01": files})

    def fake_stream(method: str, url: str, **kwargs: Any) -> _FakeResponse:
        del method, kwargs
        content = b"gltf-bytes" if str(url).endswith(".gltf") else b"bin!"
        return _FakeResponse(content=content)

    monkeypatch.setattr(remote.httpx, "Client", fake_client)
    monkeypatch.setattr(remote.httpx, "stream", fake_stream)

    catalog = AssetCatalog()
    asset = fetch_remote_asset(
        "marble_bust_01",
        catalog=catalog,
        catalog_id="marble-bust",
        cache_dir=tmp_path,
        resolution="1k",
    )
    assert asset.id == "marble-bust"
    assert asset.format == "gltf"
    assert Path(asset.path or "").is_file()
    assert (tmp_path / "polyhaven" / "marble_bust_01" / "1k" / "marble.bin").is_file()
    assert catalog.get("marble-bust").source.endswith("marble_bust_01")


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
