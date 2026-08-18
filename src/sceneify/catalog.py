"""Versioned asset catalog models and serialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

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
    _persist_path: Path | None = PrivateAttr(default=None)

    @property
    def persist_path(self) -> Path | None:
        """Filesystem path used by :meth:`persist` after catalog-grounded fetches."""
        return self._persist_path

    def bind_path(self, path: str | Path | None) -> AssetCatalog:
        """Remember where this catalog should be written after upserts."""
        self._persist_path = None if path is None else Path(path)
        return self

    def persist(self) -> Path | None:
        """Write JSON when a persist path is bound; otherwise no-op."""
        if self._persist_path is None:
            return None
        return self.save(self._persist_path)

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

    def upsert(self, asset: Asset) -> Asset:
        """Insert or replace an asset by id and keep uniqueness invariants."""
        for index, existing in enumerate(self.assets):
            if existing.id == asset.id:
                self.assets[index] = asset
                return asset
        self.assets.append(asset)
        return asset

    def search(
        self,
        *,
        query: str | None = None,
        tag: str | None = None,
        offset: int = 0,
        limit: int | None = None,
        names_only: bool = True,
    ) -> list[Asset]:
        """Return assets filtered by free-text query and/or tag.

        When ``names_only`` is true (default), the query matches asset id and
        basename/path stem. Otherwise tags and metadata are included too.
        """
        if offset < 0:
            raise ValueError("offset must be >= 0")
        if limit is not None and limit < 1:
            raise ValueError("limit must be >= 1")
        needle = (query or "").strip().lower()
        tag_needle = (tag or "").strip().lower()
        matches: list[Asset] = []
        for asset in self.assets:
            if tag_needle and tag_needle not in {item.lower() for item in asset.tags}:
                continue
            if needle:
                name_bits = [
                    asset.id,
                    Path(asset.path).stem if asset.path else "",
                    Path(asset.path).name if asset.path else "",
                ]
                if names_only:
                    haystack = " ".join(name_bits).lower()
                else:
                    haystack = " ".join(
                        [
                            *name_bits,
                            asset.path or "",
                            asset.source or "",
                            " ".join(asset.tags),
                            " ".join(str(value) for value in asset.metadata.values()),
                        ]
                    ).lower()
                if needle not in haystack:
                    continue
            matches.append(asset)
        if limit is None:
            return matches[offset:]
        return matches[offset : offset + limit]

    def list_page(
        self,
        *,
        query: str | None = None,
        tag: str | None = None,
        offset: int = 0,
        limit: int = 50,
        names_only: bool = True,
    ) -> dict[str, Any]:
        """Return a paginated catalog page with total/hasMore metadata."""
        if offset < 0:
            raise ValueError("offset must be >= 0")
        if limit < 1:
            raise ValueError("limit must be >= 1")
        filtered = self.search(query=query, tag=tag, offset=0, limit=None, names_only=names_only)
        total = len(filtered)
        page = filtered[offset : offset + limit]
        next_offset = offset + len(page)
        return {
            "assets": [asset.to_document() for asset in page],
            "total": total,
            "offset": offset,
            "limit": limit,
            "count": len(page),
            "hasMore": next_offset < total,
            "nextOffset": next_offset if next_offset < total else None,
            "query": query,
            "tag": tag,
        }

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
        catalog = cls.model_validate({"assets": raw.get("assets")})
        catalog.bind_path(source)
        return catalog

    @classmethod
    def load_or_create(cls, path: str | Path) -> AssetCatalog:
        """Load an existing catalog file, or start empty and bind ``path`` for persist."""
        source = Path(path)
        if source.is_file():
            return cls.load(source)
        return cls().bind_path(source)


def _import_yaml() -> Any:
    try:
        import yaml
    except ImportError as exc:
        raise ImportError(
            "YAML catalogs require PyYAML. Install it to read or write YAML catalogs."
        ) from exc
    return yaml
