"""Download public remote assets into a local cache and catalog entries."""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from sceneify.catalog import Asset, AssetCatalog

DEFAULT_CACHE = Path.cwd() / ".sceneify_cache"
USER_AGENT = "sceneify/0.4.0 (+https://github.com/KlajdiBeqiraj/sceneify)"
POLYHAVEN_API = "https://api.polyhaven.com"
OS3A_DATA_ROOT = "https://raw.githubusercontent.com/ToxSam/open-source-3d-assets/main/data"
SUPPORTED_PROVIDERS = ("polyhaven", "os3a")
_ASSETS_CACHE: dict[str, tuple[float, Any]] = {}
_ASSETS_CACHE_TTL_SECONDS = 300.0
MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024
HDRI_FORMATS = frozenset({"hdr", "exr", "hdri"})


def list_remote_assets(
    *,
    provider: str = "polyhaven",
    asset_type: str = "models",
    query: str | None = None,
    offset: int = 0,
    limit: int = 25,
) -> dict[str, Any]:
    """Return a paginated remote asset page filtered by sceneify (name/id first)."""
    provider_id = _normalize_provider(provider)
    if provider_id == "polyhaven":
        return _list_polyhaven(asset_type=asset_type, query=query, offset=offset, limit=limit)
    return _list_os3a(asset_type=asset_type, query=query, offset=offset, limit=limit)


def search_remote_assets(
    query: str,
    *,
    provider: str = "polyhaven",
    asset_type: str = "models",
    offset: int = 0,
    limit: int = 12,
) -> dict[str, Any]:
    """Search remote assets by text. Filtering happens inside sceneify."""
    if not query.strip():
        raise ValueError("query must be a nonempty string")
    return list_remote_assets(
        provider=provider,
        asset_type=asset_type,
        query=query,
        offset=offset,
        limit=limit,
    )


def get_remote_asset_info(
    remote_id: str,
    *,
    provider: str = "polyhaven",
    include_files: bool = True,
) -> dict[str, Any]:
    """Return detailed metadata (and optional file variants) for one remote asset."""
    provider_id = _normalize_provider(provider)
    asset_id = remote_id.strip()
    if not asset_id:
        raise ValueError("remote asset id must be a nonempty string")
    if provider_id == "polyhaven":
        return _info_polyhaven(asset_id, include_files=include_files)
    return _info_os3a(asset_id, include_files=include_files)


def fetch_remote_asset(
    remote_id: str,
    *,
    provider: str = "polyhaven",
    catalog: AssetCatalog | None = None,
    catalog_id: str | None = None,
    cache_dir: str | Path | None = None,
    resolution: str = "1k",
    asset_type: str = "models",
    force: bool = False,
) -> Asset:
    """Download one remote asset into the local cache and upsert the catalog."""
    provider_id = _normalize_provider(provider)
    root = Path(cache_dir) if cache_dir else DEFAULT_CACHE
    if provider_id == "polyhaven":
        asset = _fetch_polyhaven(
            remote_id,
            cache_dir=root,
            resolution=resolution,
            catalog_id=catalog_id,
            force=force,
            asset_type=asset_type,
        )
    else:
        asset = _fetch_os3a(
            remote_id,
            cache_dir=root,
            catalog_id=catalog_id,
            force=force,
            asset_type=asset_type,
        )
    if catalog is not None:
        catalog.upsert(asset)
    return asset


def _normalize_provider(provider: str) -> str:
    value = provider.strip().lower()
    if value not in SUPPORTED_PROVIDERS:
        known = ", ".join(SUPPORTED_PROVIDERS)
        raise ValueError(f"Unsupported remote asset provider: {provider!r}. Known: {known}")
    return value


def _list_polyhaven(
    *,
    asset_type: str,
    query: str | None,
    offset: int,
    limit: int,
) -> dict[str, Any]:
    if offset < 0:
        raise ValueError("offset must be >= 0")
    if limit < 1:
        raise ValueError("limit must be >= 1")

    type_key = _polyhaven_type_key(asset_type)
    payload = _cached_polyhaven_assets(type_key)
    scored = _filter_polyhaven_assets(payload, query=query, type_key=type_key)
    total = len(scored)
    page = scored[offset : offset + limit]
    next_offset = offset + len(page)
    return {
        "provider": "polyhaven",
        "type": type_key,
        "query": query,
        "assets": page,
        "total": total,
        "offset": offset,
        "limit": limit,
        "count": len(page),
        "hasMore": next_offset < total,
        "nextOffset": next_offset if next_offset < total else None,
        "attribution": "Asset listing powered by Poly Haven (polyhaven.com).",
    }


def _info_polyhaven(asset_id: str, *, include_files: bool) -> dict[str, Any]:
    info = _http_json(f"{POLYHAVEN_API}/info/{asset_id}")
    if not isinstance(info, dict):
        raise ValueError(f"Unexpected Poly Haven info payload for {asset_id!r}")

    result: dict[str, Any] = {
        "provider": "polyhaven",
        "id": asset_id,
        "name": str(info.get("name") or asset_id),
        "description": info.get("description"),
        "tags": [str(item) for item in info.get("tags") or []],
        "categories": [str(item) for item in info.get("categories") or []],
        "authors": info.get("authors") or {},
        "license": "CC0-1.0",
        "source": f"https://polyhaven.com/a/{asset_id}",
        "thumbnail": info.get("thumbnail_url"),
        "polycount": info.get("polycount"),
        "dimensions": info.get("dimensions"),
        "maxResolution": info.get("max_resolution"),
        "downloadCount": info.get("download_count"),
        "attribution": "Assets from Poly Haven (polyhaven.com), CC0.",
    }
    if include_files:
        files = _http_json(f"{POLYHAVEN_API}/files/{asset_id}")
        if not isinstance(files, dict):
            raise ValueError(f"Unexpected Poly Haven files payload for {asset_id!r}")
        result["files"] = _summarize_polyhaven_files(files)
    return result


def _filter_polyhaven_assets(
    payload: dict[str, Any],
    *,
    query: str | None,
    type_key: str,
) -> list[dict[str, Any]]:
    needle = (query or "").strip().lower()
    tokens = [part for part in re.split(r"\s+", needle) if part] if needle else []
    scored: list[tuple[int, dict[str, Any]]] = []

    for asset_id, meta in payload.items():
        if not isinstance(meta, dict):
            continue
        name = str(meta.get("name") or asset_id)
        tags = [str(item) for item in meta.get("tags") or []]
        categories = [str(item) for item in meta.get("categories") or []]
        id_l = asset_id.lower()
        name_l = name.lower()

        score = 0
        if needle:
            # Prefer name/id matches; tags/categories are secondary.
            name_haystack = f"{id_l} {name_l}"
            if needle in name_haystack or all(token in name_haystack for token in tokens):
                score += 80
            else:
                tag_haystack = " ".join(tags + categories).lower()
                if needle in tag_haystack or all(token in tag_haystack for token in tokens):
                    score += 20
                else:
                    continue
            if needle in (id_l, name_l):
                score += 100
            if id_l.startswith(needle) or name_l.startswith(needle):
                score += 40
            score += sum(16 for token in tokens if token in id_l or token in name_l)
            score += sum(4 for tag in tags if any(token in tag.lower() for token in tokens))

        score += int(meta.get("download_count") or 0) // 10000
        scored.append(
            (
                score,
                {
                    "provider": "polyhaven",
                    "id": asset_id,
                    "name": name,
                    "type": type_key,
                    "tags": tags,
                    "categories": categories,
                    "thumbnail": meta.get("thumbnail_url"),
                    "license": "CC0-1.0",
                    "source": f"https://polyhaven.com/a/{asset_id}",
                    "downloadCount": meta.get("download_count"),
                },
            )
        )

    scored.sort(key=lambda item: (-item[0], item[1]["name"].lower(), item[1]["id"]))
    return [item for _, item in scored]


def _summarize_polyhaven_files(files: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"formats": sorted(files.keys()), "gltf": {}, "hdri": {}}
    gltf = files.get("gltf")
    if isinstance(gltf, dict):
        for resolution, entry in gltf.items():
            if not isinstance(entry, dict):
                continue
            main = entry.get("gltf")
            if not isinstance(main, dict):
                continue
            includes = main.get("include") or {}
            include_size = 0
            if isinstance(includes, dict):
                include_size = sum(
                    int(info.get("size") or 0)
                    for info in includes.values()
                    if isinstance(info, dict)
                )
            summary["gltf"][resolution] = {
                "url": main.get("url"),
                "size": main.get("size"),
                "md5": main.get("md5"),
                "includeCount": len(includes) if isinstance(includes, dict) else 0,
                "includeBytes": include_size,
                "totalBytesApprox": int(main.get("size") or 0) + include_size,
            }
    hdri = files.get("hdri")
    if isinstance(hdri, dict):
        for resolution, entry in hdri.items():
            if not isinstance(entry, dict):
                continue
            hdr = entry.get("hdr") if isinstance(entry.get("hdr"), dict) else None
            exr = entry.get("exr") if isinstance(entry.get("exr"), dict) else None
            preferred = hdr or exr
            if preferred is None:
                continue
            summary["hdri"][resolution] = {
                "format": "hdr" if hdr is not None else "exr",
                "url": preferred.get("url"),
                "size": preferred.get("size"),
                "md5": preferred.get("md5"),
                "hasHdr": hdr is not None,
                "hasExr": exr is not None,
            }
    return summary


def _cached_polyhaven_assets(type_key: str) -> dict[str, Any]:
    cache_key = f"polyhaven:{type_key}"
    now = time.monotonic()
    cached = _ASSETS_CACHE.get(cache_key)
    if cached and now - cached[0] < _ASSETS_CACHE_TTL_SECONDS:
        payload = cached[1]
        if isinstance(payload, dict):
            return payload
    payload = _http_json(f"{POLYHAVEN_API}/assets", params={"type": type_key})
    if not isinstance(payload, dict):
        raise ValueError("Unexpected Poly Haven assets payload")
    _ASSETS_CACHE[cache_key] = (now, payload)
    return payload


def _fetch_polyhaven(
    remote_id: str,
    *,
    cache_dir: Path,
    resolution: str,
    catalog_id: str | None,
    force: bool,
    asset_type: str,
) -> Asset:
    type_key = _polyhaven_type_key(asset_type)
    if type_key == "models":
        return _fetch_polyhaven_model(
            remote_id,
            cache_dir=cache_dir,
            resolution=resolution,
            catalog_id=catalog_id,
            force=force,
        )
    if type_key == "hdris":
        return _fetch_polyhaven_hdri(
            remote_id,
            cache_dir=cache_dir,
            resolution=resolution,
            catalog_id=catalog_id,
            force=force,
        )
    raise ValueError(f"Poly Haven fetch supports models and hdris today, not {asset_type!r}")


def _fetch_polyhaven_model(
    remote_id: str,
    *,
    cache_dir: Path,
    resolution: str,
    catalog_id: str | None,
    force: bool,
) -> Asset:
    asset_id = remote_id.strip()
    _safe_component(asset_id, label="remote asset id")

    files = _http_json(f"{POLYHAVEN_API}/files/{asset_id}")
    if not isinstance(files, dict) or "gltf" not in files:
        raise ValueError(f"Poly Haven asset {asset_id!r} has no glTF files")

    res = resolution.strip().lower()
    gltf_root = files["gltf"]
    if not isinstance(gltf_root, dict) or res not in gltf_root:
        available = ", ".join(sorted(gltf_root)) if isinstance(gltf_root, dict) else ""
        raise ValueError(f"Resolution {res!r} unavailable for {asset_id!r}. Available: {available}")

    entry = gltf_root[res]
    if not isinstance(entry, dict) or "gltf" not in entry:
        raise ValueError(f"Malformed Poly Haven glTF entry for {asset_id!r} at {res}")
    main = entry["gltf"]
    if not isinstance(main, dict) or not isinstance(main.get("url"), str):
        raise ValueError(f"Missing glTF url for {asset_id!r}")

    _safe_component(res, label="resolution")
    target_dir = (cache_dir / "polyhaven" / asset_id / res).resolve()
    main_name = Path(urlparse(main["url"]).path).name or f"{asset_id}_{res}.gltf"
    main_path = target_dir / main_name
    marker = target_dir / ".sceneify-complete.json"

    if force or not marker.is_file() or not main_path.is_file():
        target_dir.mkdir(parents=True, exist_ok=True)
        _download_file(main["url"], main_path, expected=main)
        includes = main.get("include") or {}
        if not isinstance(includes, dict):
            raise ValueError(f"Malformed include map for {asset_id!r}")
        for relative, info in includes.items():
            if not isinstance(info, dict) or not isinstance(info.get("url"), str):
                raise ValueError(f"Malformed include entry {relative!r} for {asset_id!r}")
            destination = _contained_path(target_dir, relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            _download_file(info["url"], destination, expected=info)
        marker.write_text(
            json.dumps(
                {
                    "provider": "polyhaven",
                    "id": asset_id,
                    "resolution": res,
                    "main": main_name,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    checksum = _sha256_file(main_path)
    local_id = catalog_id or _slugify(asset_id)
    return Asset(
        id=local_id,
        path=str(main_path),
        format="gltf",
        license="CC0-1.0",
        source=f"https://polyhaven.com/a/{asset_id}",
        checksum=f"sha256:{checksum}",
        byte_size=main_path.stat().st_size,
        tags=["polyhaven", "remote", res],
        metadata={
            "provider": "polyhaven",
            "remoteId": asset_id,
            "resolution": res,
            "attribution": "Assets from Poly Haven (polyhaven.com), CC0.",
        },
    )


def _fetch_polyhaven_hdri(
    remote_id: str,
    *,
    cache_dir: Path,
    resolution: str,
    catalog_id: str | None,
    force: bool,
) -> Asset:
    asset_id = remote_id.strip()
    _safe_component(asset_id, label="remote asset id")

    files = _http_json(f"{POLYHAVEN_API}/files/{asset_id}")
    if not isinstance(files, dict) or "hdri" not in files:
        raise ValueError(f"Poly Haven asset {asset_id!r} has no HDRI files")

    res = resolution.strip().lower()
    hdri_root = files["hdri"]
    if not isinstance(hdri_root, dict) or res not in hdri_root:
        available = ", ".join(sorted(hdri_root)) if isinstance(hdri_root, dict) else ""
        raise ValueError(f"Resolution {res!r} unavailable for {asset_id!r}. Available: {available}")

    entry = hdri_root[res]
    if not isinstance(entry, dict):
        raise ValueError(f"Malformed Poly Haven HDRI entry for {asset_id!r} at {res}")
    hdr = entry.get("hdr") if isinstance(entry.get("hdr"), dict) else None
    exr = entry.get("exr") if isinstance(entry.get("exr"), dict) else None
    preferred = hdr or exr
    if preferred is None or not isinstance(preferred.get("url"), str):
        raise ValueError(f"Missing HDRI download url for {asset_id!r} at {res}")
    fmt = "hdr" if hdr is not None else "exr"

    _safe_component(res, label="resolution")
    target_dir = (cache_dir / "polyhaven" / asset_id / res).resolve()
    main_name = Path(urlparse(preferred["url"]).path).name or f"{asset_id}_{res}.{fmt}"
    main_path = target_dir / main_name
    marker = target_dir / ".sceneify-complete.json"

    if force or not marker.is_file() or not main_path.is_file():
        target_dir.mkdir(parents=True, exist_ok=True)
        _download_file(preferred["url"], main_path, expected=preferred)
        marker.write_text(
            json.dumps(
                {
                    "provider": "polyhaven",
                    "id": asset_id,
                    "type": "hdris",
                    "resolution": res,
                    "main": main_name,
                    "format": fmt,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    checksum = _sha256_file(main_path)
    local_id = catalog_id or _slugify(asset_id)
    return Asset(
        id=local_id,
        path=str(main_path),
        format=fmt,
        license="CC0-1.0",
        source=f"https://polyhaven.com/a/{asset_id}",
        checksum=f"sha256:{checksum}",
        byte_size=main_path.stat().st_size,
        tags=["polyhaven", "remote", "hdri", res],
        metadata={
            "provider": "polyhaven",
            "remoteId": asset_id,
            "resolution": res,
            "assetType": "hdris",
            "attribution": "Assets from Poly Haven (polyhaven.com), CC0.",
        },
    )


def _polyhaven_type_key(asset_type: str) -> str:
    value = asset_type.strip().lower()
    aliases = {
        "model": "models",
        "models": "models",
        "hdri": "hdris",
        "hdris": "hdris",
        "texture": "textures",
        "textures": "textures",
        "all": "all",
    }
    if value not in aliases:
        raise ValueError(f"Unsupported Poly Haven asset type: {asset_type!r}")
    return aliases[value]


def _os3a_type_key(asset_type: str) -> str:
    value = asset_type.strip().lower()
    aliases = {
        "model": "environments",
        "models": "environments",
        "environment": "environments",
        "environments": "environments",
        "all": "environments",
    }
    if value not in aliases:
        raise ValueError(f"Unsupported OS3A asset type: {asset_type!r}")
    return aliases[value]


def _list_os3a(
    *,
    asset_type: str,
    query: str | None,
    offset: int,
    limit: int,
) -> dict[str, Any]:
    if offset < 0:
        raise ValueError("offset must be >= 0")
    if limit < 1:
        raise ValueError("limit must be >= 1")
    type_key = _os3a_type_key(asset_type)
    scored = _filter_os3a_assets(_cached_os3a_catalog(), query=query)
    total = len(scored)
    page = scored[offset : offset + limit]
    next_offset = offset + len(page)
    return {
        "provider": "os3a",
        "type": type_key,
        "query": query,
        "assets": page,
        "total": total,
        "offset": offset,
        "limit": limit,
        "count": len(page),
        "hasMore": next_offset < total,
        "nextOffset": next_offset if next_offset < total else None,
        "attribution": (
            "Environment packs from Open Source 3D Assets / Polygonal Mind collections (CC0)."
        ),
    }


def _info_os3a(asset_id: str, *, include_files: bool) -> dict[str, Any]:
    catalog = _cached_os3a_catalog()
    entry = catalog.get(asset_id)
    if entry is None:
        raise ValueError(f"Unknown OS3A asset id: {asset_id!r}")
    result = {
        "provider": "os3a",
        "id": entry["id"],
        "name": entry["name"],
        "description": entry.get("description"),
        "tags": entry.get("tags") or [],
        "categories": entry.get("categories") or [],
        "projectId": entry.get("projectId"),
        "projectName": entry.get("projectName"),
        "authors": {"Polygonal Mind": "All"},
        "license": entry.get("license") or "CC0",
        "source": entry.get("source"),
        "thumbnail": entry.get("thumbnail"),
        "byteSize": entry.get("byteSize"),
        "attribution": entry.get("attribution"),
    }
    if include_files:
        result["files"] = {
            "glb": {
                "url": entry.get("downloadUrl"),
                "size": entry.get("byteSize"),
                "format": "glb",
            }
        }
    return result


def _filter_os3a_assets(
    catalog: dict[str, dict[str, Any]],
    *,
    query: str | None,
) -> list[dict[str, Any]]:
    needle = (query or "").strip().lower()
    tokens = [part for part in re.split(r"\s+", needle) if part] if needle else []
    scored: list[tuple[int, dict[str, Any]]] = []

    for asset_id, meta in catalog.items():
        name = str(meta.get("name") or asset_id)
        tags = [str(item) for item in meta.get("tags") or []]
        categories = [str(item) for item in meta.get("categories") or []]
        project = str(meta.get("projectName") or meta.get("projectId") or "")
        id_l = asset_id.lower()
        name_l = name.lower()
        project_l = project.lower()

        score = 0
        if needle:
            name_haystack = f"{id_l} {name_l} {project_l}"
            if needle in name_haystack or all(token in name_haystack for token in tokens):
                score += 80
            else:
                tag_haystack = " ".join(tags + categories).lower()
                if needle in tag_haystack or all(token in tag_haystack for token in tokens):
                    score += 20
                else:
                    continue
            if needle in (id_l, name_l):
                score += 100
            if id_l.startswith(needle) or name_l.startswith(needle):
                score += 40
            score += sum(16 for token in tokens if token in id_l or token in name_l)
            score += sum(8 for token in tokens if token in project_l)
            score += sum(4 for tag in tags if any(token in tag.lower() for token in tokens))

        score += int(meta.get("byteSize") or 0) // 200_000
        scored.append(
            (
                score,
                {
                    "provider": "os3a",
                    "id": asset_id,
                    "name": name,
                    "type": "environments",
                    "tags": tags,
                    "categories": categories,
                    "projectId": meta.get("projectId"),
                    "projectName": meta.get("projectName"),
                    "thumbnail": meta.get("thumbnail"),
                    "license": meta.get("license") or "CC0",
                    "source": meta.get("source"),
                    "byteSize": meta.get("byteSize"),
                },
            )
        )

    scored.sort(key=lambda item: (-item[0], item[1]["name"].lower(), item[1]["id"]))
    return [item for _, item in scored]


def _cached_os3a_catalog() -> dict[str, dict[str, Any]]:
    cache_key = "os3a:catalog"
    now = time.monotonic()
    cached = _ASSETS_CACHE.get(cache_key)
    if cached and now - cached[0] < _ASSETS_CACHE_TTL_SECONDS:
        payload = cached[1]
        if isinstance(payload, dict):
            return payload

    projects = _http_json(f"{OS3A_DATA_ROOT}/projects.json")
    if not isinstance(projects, list):
        raise ValueError("Unexpected OS3A projects payload")

    catalog: dict[str, dict[str, Any]] = {}
    for project in projects:
        if not isinstance(project, dict):
            continue
        if project.get("is_public") is False:
            continue
        project_id = str(project.get("id") or "").strip()
        project_name = str(project.get("name") or project_id)
        license_name = str(project.get("license") or "CC0")
        data_file = str(project.get("asset_data_file") or "").strip()
        if not project_id or not data_file:
            continue
        assets_url = f"{OS3A_DATA_ROOT}/{data_file.lstrip('/')}"
        assets = _http_json(assets_url)
        if not isinstance(assets, list):
            continue
        for item in assets:
            if not isinstance(item, dict):
                continue
            if item.get("is_public") is False or item.get("is_draft") is True:
                continue
            asset_id = str(item.get("id") or "").strip()
            download_url = item.get("model_file_url")
            if not asset_id or not isinstance(download_url, str) or not download_url:
                continue
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            attributes = metadata.get("attributes") if isinstance(metadata, dict) else None
            tags: list[str] = []
            categories: list[str] = []
            if isinstance(attributes, list):
                for attr in attributes:
                    if not isinstance(attr, dict):
                        continue
                    value = attr.get("value")
                    if not isinstance(value, str) or not value:
                        continue
                    tags.append(value)
                    trait = attr.get("trait_type")
                    if isinstance(trait, str) and trait.lower() in {
                        "category",
                        "theme",
                        "setting",
                        "type",
                    }:
                        categories.append(value)
            tags.extend([project_id, project_name, "os3a", "environment"])
            byte_size = metadata.get("file_size") if isinstance(metadata, dict) else None
            catalog[asset_id] = {
                "id": asset_id,
                "name": str(item.get("name") or asset_id),
                "description": item.get("description"),
                "tags": sorted(set(tags)),
                "categories": sorted(set(categories)),
                "projectId": project_id,
                "projectName": project_name,
                "license": license_name,
                "source": download_url,
                "downloadUrl": download_url,
                "thumbnail": item.get("thumbnail_url"),
                "byteSize": int(byte_size) if isinstance(byte_size, int) else None,
                "attribution": (
                    "Environment packs from Open Source 3D Assets / "
                    f"{project_name} (Polygonal Mind), {license_name}."
                ),
            }

    _ASSETS_CACHE[cache_key] = (now, catalog)
    return catalog


def _fetch_os3a(
    remote_id: str,
    *,
    cache_dir: Path,
    catalog_id: str | None,
    force: bool,
    asset_type: str,
) -> Asset:
    _os3a_type_key(asset_type)
    asset_id = remote_id.strip()
    _safe_component(asset_id, label="remote asset id")
    entry = _cached_os3a_catalog().get(asset_id)
    if entry is None:
        raise ValueError(f"Unknown OS3A asset id: {asset_id!r}")
    download_url = entry.get("downloadUrl")
    if not isinstance(download_url, str) or not download_url:
        raise ValueError(f"OS3A asset {asset_id!r} has no download URL")

    project_id = str(entry.get("projectId") or "os3a")
    _safe_component(project_id, label="project id")
    target_dir = (cache_dir / "os3a" / project_id / asset_id).resolve()
    main_name = Path(urlparse(download_url).path).name or f"{asset_id}.glb"
    main_path = target_dir / main_name
    marker = target_dir / ".sceneify-complete.json"

    if force or not marker.is_file() or not main_path.is_file():
        target_dir.mkdir(parents=True, exist_ok=True)
        # OS3A registry sizes are informational; do not enforce byte identity.
        _download_file(download_url, main_path, expected={})
        marker.write_text(
            json.dumps(
                {
                    "provider": "os3a",
                    "id": asset_id,
                    "projectId": project_id,
                    "main": main_name,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    checksum = _sha256_file(main_path)
    local_id = catalog_id or _slugify(asset_id)
    return Asset(
        id=local_id,
        path=str(main_path),
        format="glb",
        license=str(entry.get("license") or "CC0"),
        source=download_url,
        checksum=f"sha256:{checksum}",
        byte_size=main_path.stat().st_size,
        thumbnail=entry.get("thumbnail") if isinstance(entry.get("thumbnail"), str) else None,
        tags=["os3a", "remote", "environment", project_id],
        metadata={
            "provider": "os3a",
            "remoteId": asset_id,
            "projectId": project_id,
            "projectName": entry.get("projectName"),
            "attribution": entry.get("attribution"),
        },
    )


def _http_json(url: str, *, params: dict[str, str] | None = None) -> Any:
    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=60.0,
        follow_redirects=True,
    ) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def _download_file(url: str, destination: Path, *, expected: dict[str, Any]) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Remote asset URLs must use HTTPS")
    expected_size = expected.get("size")
    if isinstance(expected_size, int) and expected_size > MAX_DOWNLOAD_BYTES:
        raise ValueError(f"Remote asset exceeds the {MAX_DOWNLOAD_BYTES} byte download limit")
    temporary = destination.with_name(f".{destination.name}.part")
    with httpx.stream(
        "GET",
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=120.0,
        follow_redirects=True,
    ) as response:
        response.raise_for_status()
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > MAX_DOWNLOAD_BYTES:
            raise ValueError(f"Remote asset exceeds the {MAX_DOWNLOAD_BYTES} byte download limit")
        downloaded = 0
        with temporary.open("wb") as handle:
            for chunk in response.iter_bytes():
                downloaded += len(chunk)
                if downloaded > MAX_DOWNLOAD_BYTES:
                    temporary.unlink(missing_ok=True)
                    raise ValueError(
                        f"Remote asset exceeds the {MAX_DOWNLOAD_BYTES} byte download limit"
                    )
                handle.write(chunk)
    if isinstance(expected_size, int) and downloaded != expected_size:
        temporary.unlink(missing_ok=True)
        raise ValueError(f"Remote asset size mismatch: expected {expected_size}, got {downloaded}")
    expected_md5 = expected.get("md5")
    if isinstance(expected_md5, str) and _md5_file(temporary) != expected_md5.lower():
        temporary.unlink(missing_ok=True)
        raise ValueError("Remote asset checksum mismatch")
    temporary.replace(destination)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_component(value: str, *, label: str) -> None:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"{label} must be a single path component")


def _contained_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Remote asset include escapes its cache directory: {relative!r}") from exc
    return candidate


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip()).strip("-").lower()
    return slug or "asset"
