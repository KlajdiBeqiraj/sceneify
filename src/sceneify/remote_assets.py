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
SUPPORTED_PROVIDERS = ("polyhaven",)
_ASSETS_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_ASSETS_CACHE_TTL_SECONDS = 300.0
MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024


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
    if provider_id != "polyhaven":
        raise ValueError(f"Unsupported remote asset provider: {provider!r}")
    return _list_polyhaven(asset_type=asset_type, query=query, offset=offset, limit=limit)


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
    if provider_id != "polyhaven":
        raise ValueError(f"Unsupported remote asset provider: {provider!r}")
    asset_id = remote_id.strip()
    if not asset_id:
        raise ValueError("remote asset id must be a nonempty string")

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
    if provider_id != "polyhaven":
        raise ValueError(f"Unsupported remote asset provider: {provider!r}")

    root = Path(cache_dir) if cache_dir else DEFAULT_CACHE
    asset = _fetch_polyhaven_model(
        remote_id,
        cache_dir=root,
        resolution=resolution,
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
    summary: dict[str, Any] = {"formats": sorted(files.keys()), "gltf": {}}
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
    return summary


def _cached_polyhaven_assets(type_key: str) -> dict[str, Any]:
    now = time.monotonic()
    cached = _ASSETS_CACHE.get(type_key)
    if cached and now - cached[0] < _ASSETS_CACHE_TTL_SECONDS:
        return cached[1]
    payload = _http_json(f"{POLYHAVEN_API}/assets", params={"type": type_key})
    if not isinstance(payload, dict):
        raise ValueError("Unexpected Poly Haven assets payload")
    _ASSETS_CACHE[type_key] = (now, payload)
    return payload


def _fetch_polyhaven_model(
    remote_id: str,
    *,
    cache_dir: Path,
    resolution: str,
    catalog_id: str | None,
    force: bool,
    asset_type: str,
) -> Asset:
    asset_id = remote_id.strip()
    _safe_component(asset_id, label="remote asset id")
    type_key = _polyhaven_type_key(asset_type)
    if type_key != "models":
        raise ValueError("Only Poly Haven models are supported for fetch_remote_asset today")

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
