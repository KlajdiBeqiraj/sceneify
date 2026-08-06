"""Versioned asset catalog models and serialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

CATALOG_FORMAT = "sceneify-asset-catalog"
CATALOG_VERSION = 2
SUPPORTED_CATALOG_VERSIONS = {1, CATALOG_VERSION}


class Asset(BaseModel):
    """One asset addressable by a stable identifier."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(min_length=1)
    path: str | None = Field(default=None, min_length=1)
    format: str | None = Field(default=None, min_length=1)
    license: str | None = Field(default=None, min_length=1)
    source: str | None = Field(default=None, min_length=1)
    checksum: str | None = Field(default=None, min_length=1)
    thumbnail: str | None = Field(default=None, min_length=1)
    byte_size: int | None = Field(default=None, alias="byteSize", ge=0)
    animations: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_location_and_format(self) -> Asset:
        if self.path is None and self.source is None:
            raise ValueError("Asset requires path or source")
        if self.format is None:
            location = self.path or self.source or ""
            suffix = Path(urlparse(location).path).suffix.lower().lstrip(".")
            self.format = suffix or "unknown"
        else:
            self.format = self.format.lower().lstrip(".")
        return self

    def to_document(self) -> dict[str, Any]:
        """Return the JSON representation used by catalog v2."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class AssetCatalog(BaseModel):
    """A validated collection of assets with unique identifiers."""

    model_config = ConfigDict(extra="forbid")

    assets: list[Asset] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> AssetCatalog:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for asset in self.assets:
            if asset.id in seen:
                duplicates.add(asset.id)
            seen.add(asset.id)
        if duplicates:
            names = ", ".join(sorted(duplicates))
            raise ValueError(f"Duplicate asset ids: {names}")
        return self

    def get(self, asset_id: str) -> Asset:
        """Return an asset by id or raise KeyError."""
        for asset in self.assets:
            if asset.id == asset_id:
                return asset
        raise KeyError(asset_id)

    def to_document(self) -> dict[str, Any]:
        """Return the versioned catalog document."""
        return {
            "format": CATALOG_FORMAT,
            "version": CATALOG_VERSION,
            "assets": [asset.to_document() for asset in self.assets],
        }

    def save(self, path: str | Path) -> Path:
        """Write JSON, or YAML when the optional YAML package is available."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        document = self.to_document()
        if target.suffix.lower() in {".yaml", ".yml"}:
            yaml = _import_yaml()
            text = yaml.safe_dump(document, sort_keys=False)
        else:
            text = json.dumps(document, indent=2) + "\n"
        target.write_text(text, encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: str | Path) -> AssetCatalog:
        """Load and validate a versioned JSON or YAML catalog."""
        source = Path(path)
        if source.suffix.lower() in {".yaml", ".yml"}:
            raw = _import_yaml().safe_load(source.read_text(encoding="utf-8"))
        else:
            raw = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Asset catalog must contain an object")
        if raw.get("format") != CATALOG_FORMAT:
            raise ValueError(f"Unsupported catalog format: {raw.get('format')!r}")
        version = raw.get("version")
        if isinstance(version, bool) or version not in SUPPORTED_CATALOG_VERSIONS:
            raise ValueError(f"Unsupported catalog version: {version!r}")
        return cls.model_validate({"assets": raw.get("assets")})


def _import_yaml() -> Any:
    try:
        import yaml
    except ImportError as exc:
        raise ImportError(
            "YAML catalogs require PyYAML. Install it to read or write YAML catalogs."
        ) from exc
    return yaml
