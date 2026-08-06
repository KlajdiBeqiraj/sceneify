"""Helpers to download public demo GLB/PLY assets into a local cache."""

from __future__ import annotations

from pathlib import Path

import httpx

DEFAULT_CACHE = Path.cwd() / ".sceneify_cache"

# Public Khronos sample assets (glTF Sample Models).
PUBLIC_ASSETS: dict[str, dict[str, str]] = {
    "damaged_helmet": {
        "url": (
            "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Models/"
            "master/2.0/DamagedHelmet/glTF-Binary/DamagedHelmet.glb"
        ),
        "filename": "DamagedHelmet.glb",
        "format": "glb",
        "license_note": "Khronos glTF Sample Models (see upstream repo license).",
    },
    "avocado": {
        "url": (
            "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Models/"
            "master/2.0/Avocado/glTF-Binary/Avocado.glb"
        ),
        "filename": "Avocado.glb",
        "format": "glb",
        "license_note": "Khronos glTF Sample Models (see upstream repo license).",
    },
    # Public PLY from the three.js examples (ASCII dolphins).
    "dolphins_ply": {
        "url": "https://threejs.org/examples/models/ply/ascii/dolphins.ply",
        "filename": "dolphins.ply",
        "format": "ply",
        "license_note": "three.js example model; see three.js license for redistribution.",
    },
}


def list_public_assets() -> list[str]:
    return sorted(PUBLIC_ASSETS)


def download_public_asset(
    name: str,
    *,
    cache_dir: str | Path | None = None,
    force: bool = False,
) -> Path:
    """Download a named public demo asset into the local cache and return its path."""
    if name not in PUBLIC_ASSETS:
        known = ", ".join(list_public_assets())
        raise KeyError(f"Unknown asset {name!r}. Known: {known}")

    meta = PUBLIC_ASSETS[name]
    root = Path(cache_dir) if cache_dir else DEFAULT_CACHE
    root.mkdir(parents=True, exist_ok=True)
    target = root / meta["filename"]

    if target.exists() and not force:
        return target

    with httpx.stream("GET", meta["url"], follow_redirects=True, timeout=60.0) as response:
        response.raise_for_status()
        with target.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)

    return target
