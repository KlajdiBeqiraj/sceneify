"""Provider independent actions for coding agents that author scenes."""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sceneify.catalog import AssetCatalog
from sceneify.game import GameManifest
from sceneify.perception import apply_perception, is_read_action
from sceneify.remote_assets import (
    HDRI_FORMATS,
    fetch_remote_asset,
    get_remote_asset_info,
    list_remote_assets,
    search_remote_assets,
)
from sceneify.scene import Scene

_PRESENTATION_KEYS = frozenset(
    {
        "environmentMap",
        "environmentPreset",
        "ambientIntensity",
        "background",
        "fog",
        "camera",
        "shadows",
        "title",
        "subtitle",
        "grid",
        "helpers",
        "exposure",
        "keyLightIntensity",
        "cameraTour",
    }
)

ACTION_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "sceneify world action",
    "type": "object",
    "required": ["action"],
    "properties": {
        "action": {
            "enum": [
                "list_assets",
                "search_assets",
                "list_remote",
                "search_remote",
                "info_remote",
                "fetch_remote",
                "set_presentation",
                "set_world",
                "add_asset",
                "add_primitive",
                "add_object",
                "add_annotation",
                "update_node",
                "patch_node",
                "reparent",
                "delete_node",
                "place_on_world",
                "set_gameplay_role",
                "validate_scene",
                "get_scene",
                "describe_scene",
                "get_node",
                "list_nodes",
                "topdown_map",
                "spatial_query",
                "get_bounds",
                "capture_view",
                "load",
                "save",
            ]
        },
        "asset": {"type": "string", "minLength": 1},
        "id": {"type": "string", "minLength": 1},
        "path": {"type": "string", "minLength": 1},
        "label": {"type": "string"},
        "description": {"type": "string"},
        "query": {"type": "string"},
        "tag": {"type": "string"},
        "provider": {"type": "string", "minLength": 1},
        "remoteId": {"type": "string", "minLength": 1},
        "resolution": {"type": "string", "minLength": 1},
        "type": {"type": "string", "minLength": 1},
        "pageOffset": {"type": "integer", "minimum": 0},
        "limit": {"type": "integer", "minimum": 1},
        "namesOnly": {"type": "boolean"},
        "includeFiles": {"type": "boolean"},
        "force": {"type": "boolean"},
        "primitive": {"enum": ["box", "sphere", "capsule", "plane"]},
        "role": {"enum": ["none", "player-spawn", "pickup", "hazard", "checkpoint", "goal"]},
        "parentId": {"type": ["string", "null"]},
        "targetId": {"type": "string", "minLength": 1},
        "children": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
        "position": {"$ref": "#/$defs/vec3"},
        "offset": {"$ref": "#/$defs/vec3"},
        "rotation": {"$ref": "#/$defs/vec3"},
        "scale": {"$ref": "#/$defs/vec3"},
        "size": {"$ref": "#/$defs/vec3"},
        "radius": {"type": "number"},
        "height": {"type": "number"},
        "x": {"type": "number"},
        "z": {"type": "number"},
        "offsetY": {"type": "number"},
        "visible": {"type": "boolean"},
        "material": {"type": "object"},
        "physics": {"type": "object"},
        "patch": {"type": "object"},
        "presentation": {"type": "object"},
        "environmentMap": {"type": "string"},
        "environmentPreset": {"type": "string"},
        "ambientIntensity": {"type": "number"},
        "background": {"type": "string"},
        "fog": {"type": "object"},
        "camera": {"type": "object"},
        "shadows": {"type": "boolean"},
        "title": {"type": "string"},
        "cacheDir": {"type": "string", "minLength": 1},
        "includeScene": {
            "type": "boolean",
            "description": (
                "Include full scene dump in the response. Defaults to false for read/perception "
                "actions and true for mutations."
            ),
        },
        "detail": {"enum": ["summary", "full"]},
        "maxNodes": {"type": "integer", "minimum": 1},
        "includeAnnotations": {"type": "boolean"},
        "includeBounds": {"type": "boolean"},
        "kind": {"enum": ["mesh", "object", "primitive", "annotation"]},
        "roots": {"type": "array", "items": {"type": "string"}},
        "cellSize": {"type": "number"},
        "width": {"type": "integer", "minimum": 1},
        "focus": {"$ref": "#/$defs/vec3"},
        "maxCells": {"type": "integer", "minimum": 1},
        "mode": {
            "enum": ["nearest", "distance", "relative", "in_radius", "height_at"],
        },
        "fromId": {"type": "string", "minLength": 1},
        "toId": {"type": "string", "minLength": 1},
        "point": {"$ref": "#/$defs/vec3"},
        "k": {"type": "integer", "minimum": 1},
    },
    "$defs": {
        "vec3": {
            "type": "array",
            "prefixItems": [{"type": "number"}, {"type": "number"}, {"type": "number"}],
            "items": False,
        }
    },
}


def tool_definition() -> dict[str, Any]:
    """Return a neutral tool descriptor suitable for a coding agent adapter."""
    return {
        "name": "sceneify_apply",
        "description": (
            "Apply one validated action to a sceneify world. "
            "Prefer dedicated list/search/info tools for asset discovery. "
            "Use fetch_remote before add_asset/set_world for remote CC0 meshes, "
            "and fetch_remote type=hdris then set_presentation for HDRI lighting. "
            "Providers: polyhaven (models/hdris), os3a (environment GLBs)."
        ),
        "inputSchema": ACTION_SCHEMA,
    }


def tool_definitions() -> list[dict[str, Any]]:
    """Return the focused tool set used by MCP and multi-tool adapters."""
    page_props = {
        "pageOffset": {"type": "integer", "minimum": 0, "default": 0},
        "limit": {"type": "integer", "minimum": 1, "default": 25},
    }
    apply_tool = tool_definition()
    return [
        {
            "name": "sceneify_list_assets",
            "description": (
                "List local catalog assets with pagination. "
                "Optional query filters by asset id/name."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "tag": {"type": "string"},
                    "namesOnly": {"type": "boolean", "default": True},
                    **page_props,
                },
            },
        },
        {
            "name": "sceneify_search_assets",
            "description": (
                "Search the local catalog by name/id (sceneify-side filter) with pagination."
            ),
            "inputSchema": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "minLength": 1},
                    "tag": {"type": "string"},
                    "namesOnly": {"type": "boolean", "default": True},
                    **page_props,
                },
            },
        },
        {
            "name": "sceneify_list_remote",
            "description": (
                "List remote CC0 assets with pagination. "
                "provider=polyhaven (models/hdris) or provider=os3a (environment GLBs). "
                "sceneify fetches the catalog and pages/filters locally. "
                "Credit Poly Haven when using its live API."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "provider": {"type": "string", "default": "polyhaven"},
                    "type": {
                        "type": "string",
                        "default": "models",
                        "description": "polyhaven: models|hdris; os3a: environments|models",
                    },
                    **page_props,
                },
            },
        },
        {
            "name": "sceneify_search_remote",
            "description": (
                "Search remote assets by text. sceneify filters primarily on id/name, "
                "then tags. Use type=hdris for Poly Haven environments, "
                "provider=os3a for place/architecture GLBs."
            ),
            "inputSchema": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "minLength": 1},
                    "provider": {"type": "string", "default": "polyhaven"},
                    "type": {"type": "string", "default": "models"},
                    **page_props,
                },
            },
        },
        {
            "name": "sceneify_info_remote",
            "description": (
                "Get detailed metadata and available file variants for one remote asset id."
            ),
            "inputSchema": {
                "type": "object",
                "required": ["remoteId"],
                "properties": {
                    "remoteId": {"type": "string", "minLength": 1},
                    "provider": {"type": "string", "default": "polyhaven"},
                    "includeFiles": {"type": "boolean", "default": True},
                },
            },
        },
        {
            "name": "sceneify_fetch_remote",
            "description": (
                "Download one remote asset into .sceneify_cache and register it in the catalog. "
                "For HDRIs use type=hdris then set_presentation with asset=catalogId."
            ),
            "inputSchema": {
                "type": "object",
                "required": ["remoteId"],
                "properties": {
                    "remoteId": {"type": "string", "minLength": 1},
                    "provider": {"type": "string", "default": "polyhaven"},
                    "id": {"type": "string", "minLength": 1},
                    "resolution": {"type": "string", "default": "1k"},
                    "type": {"type": "string", "default": "models"},
                    "force": {"type": "boolean"},
                    "cacheDir": {"type": "string"},
                },
            },
        },
        {
            "name": "sceneify_set_presentation",
            "description": (
                "Merge presentation settings (lighting, camera, fog, HDRI). "
                "Pass environmentMap path or asset=catalogId for a fetched HDRI."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "asset": {
                        "type": "string",
                        "description": "Catalog id of a fetched HDRI (hdr/exr).",
                    },
                    "environmentMap": {"type": "string"},
                    "environmentPreset": {"type": "string"},
                    "ambientIntensity": {"type": "number"},
                    "background": {"type": "string"},
                    "fog": {"type": "object"},
                    "camera": {"type": "object"},
                    "shadows": {"type": "boolean"},
                    "title": {"type": "string"},
                    "presentation": {"type": "object"},
                },
            },
        },
        {
            "name": "sceneify_get_scene",
            "description": (
                "Return the full scene document (large). Prefer describe_scene / list_nodes "
                "for agent perception."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"includeScene": {"type": "boolean", "default": True}},
            },
        },
        {
            "name": "sceneify_validate_scene",
            "description": "Validate the scene graph and environment rules.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "sceneify_describe_scene",
            "description": (
                "Compact scene overview with hierarchy tree and world poses. "
                "Use detail=summary before editing; detail=full for leaf nodes + bounds."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "detail": {"enum": ["summary", "full"], "default": "summary"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "roots": {"type": "array", "items": {"type": "string"}},
                    "maxNodes": {"type": "integer", "minimum": 1, "default": 200},
                    "includeAnnotations": {"type": "boolean", "default": True},
                },
            },
        },
        {
            "name": "sceneify_get_node",
            "description": (
                "Inspect one node: local+world transform, children, bounds, anchored annotations."
            ),
            "inputSchema": {
                "type": "object",
                "required": ["id"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "includeBounds": {"type": "boolean", "default": True},
                },
            },
        },
        {
            "name": "sceneify_list_nodes",
            "description": "Paginated scene nodes with world poses; filter by tag/kind/query.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string"},
                    "kind": {"enum": ["mesh", "object", "primitive", "annotation"]},
                    "query": {"type": "string"},
                    "parentId": {"type": ["string", "null"]},
                    "pageOffset": {"type": "integer", "minimum": 0, "default": 0},
                    "limit": {"type": "integer", "minimum": 1, "default": 50},
                },
            },
        },
        {
            "name": "sceneify_topdown_map",
            "description": (
                "ASCII top-down occupancy map on XZ (Y-up). "
                "Top of ascii is north (-Z). Use for layout awareness."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "cellSize": {"type": "number", "default": 1.0},
                    "width": {"type": "integer", "minimum": 1},
                    "height": {"type": "integer", "minimum": 1},
                    "focus": {
                        "type": "array",
                        "prefixItems": [
                            {"type": "number"},
                            {"type": "number"},
                            {"type": "number"},
                        ],
                        "items": False,
                    },
                    "maxCells": {"type": "integer", "minimum": 1, "default": 80},
                },
            },
        },
        {
            "name": "sceneify_spatial_query",
            "description": (
                "Spatial relations in world space: nearest, distance, relative bearing, "
                "in_radius, height_at. Axes: +X east, -Z north, Y up."
            ),
            "inputSchema": {
                "type": "object",
                "required": ["mode"],
                "properties": {
                    "mode": {
                        "enum": ["nearest", "distance", "relative", "in_radius", "height_at"],
                    },
                    "id": {"type": "string"},
                    "fromId": {"type": "string"},
                    "toId": {"type": "string"},
                    "point": {
                        "type": "array",
                        "prefixItems": [
                            {"type": "number"},
                            {"type": "number"},
                            {"type": "number"},
                        ],
                        "items": False,
                    },
                    "k": {"type": "integer", "minimum": 1, "default": 5},
                    "radius": {"type": "number"},
                    "tag": {"type": "string"},
                    "kind": {"enum": ["mesh", "object", "primitive", "annotation"]},
                    "x": {"type": "number"},
                    "z": {"type": "number"},
                },
            },
        },
        {
            "name": "sceneify_get_bounds",
            "description": (
                "World AABB for one node id, or the whole scene when id is omitted. "
                "Primitives use size/radius; meshes use GLB accessor bounds when available."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"id": {"type": "string", "minLength": 1}},
            },
        },
        {
            "name": "sceneify_capture_view",
            "description": (
                "Capture a PNG screenshot from a live browser viewer. "
                "Requires sceneify-mcp --server or a started session. "
                "Presets: presentation, topdown, focus (with nodeId)."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "preset": {
                        "enum": ["presentation", "topdown", "focus"],
                        "default": "presentation",
                    },
                    "nodeId": {"type": "string"},
                    "width": {"type": "integer", "minimum": 1, "default": 1280},
                    "height": {"type": "integer", "minimum": 1, "default": 720},
                    "eye": {"$ref": "#/$defs/vec3"},
                    "target": {"$ref": "#/$defs/vec3"},
                    "fov": {"type": "number"},
                },
            },
        },
        apply_tool,
    ]


class WorldTools:
    """Apply small deterministic actions over a scene and an asset catalog."""

    def __init__(self, scene: Scene, catalog: AssetCatalog) -> None:
        self.scene = scene
        self.catalog = catalog

    def apply(self, command: Mapping[str, Any]) -> dict[str, Any]:
        """Apply one action and return its result plus optional scene dump."""
        action = _required_string(command, "action")
        handlers = {
            "list_assets": self._list_assets,
            "search_assets": self._search_assets,
            "list_remote": self._list_remote,
            "search_remote": self._search_remote,
            "info_remote": self._info_remote,
            "fetch_remote": self._fetch_remote,
            "set_presentation": self._set_presentation,
            "set_world": self._set_world,
            "add_asset": self._add_asset,
            "add_primitive": self._add_primitive,
            "add_object": self._add_object,
            "add_annotation": self._add_annotation,
            "update_node": self._update_node,
            "patch_node": self._patch_node,
            "reparent": self._reparent,
            "delete_node": self._delete_node,
            "place_on_world": self._place_on_world,
            "set_gameplay_role": self._set_gameplay_role,
            "validate_scene": self._validate_scene,
            "get_scene": self._get_scene,
            "describe_scene": self._perception,
            "get_node": self._perception,
            "list_nodes": self._perception,
            "topdown_map": self._perception,
            "spatial_query": self._perception,
            "get_bounds": self._perception,
            "capture_view": self._capture_view,
            "load": self._load,
            "save": self._save,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ValueError(f"Unsupported world action: {action!r}")
        result = handler(command)
        include_scene = command.get("includeScene")
        if include_scene is None:
            # Read/perception tools omit the full dump by default; mutations keep it
            # for backward compatibility unless explicitly disabled.
            include_scene = action == "get_scene" or not is_read_action(action)
        payload: dict[str, Any] = {"action": action, "result": result}
        if include_scene:
            payload["scene"] = self.scene.to_dict()
        else:
            payload["sceneIncluded"] = False
        return payload

    def apply_many(
        self,
        commands: Sequence[Mapping[str, Any]],
        *,
        stop_on_error: bool = True,
    ) -> list[dict[str, Any]]:
        """Apply multiple actions in order."""
        results: list[dict[str, Any]] = []
        for command in commands:
            try:
                results.append({"ok": True, **self.apply(command)})
            except Exception as exc:
                failure: dict[str, Any] = {
                    "ok": False,
                    "action": command.get("action"),
                    "error": {
                        "code": exc.__class__.__name__,
                        "message": str(exc),
                        "hint": _hint_for(str(command.get("action") or ""), exc),
                    },
                }
                if command.get("includeScene", True):
                    failure["scene"] = self.scene.to_dict()
                results.append(failure)
                if stop_on_error:
                    break
        return results

    def _list_assets(self, command: Mapping[str, Any]) -> dict[str, Any]:
        names_only = command.get("namesOnly")
        return self.catalog.list_page(
            query=_optional_string(command, "query"),
            tag=_optional_string(command, "tag"),
            offset=_page_offset(command),
            limit=_optional_int(command, "limit") or 50,
            names_only=True if names_only is None else bool(names_only),
        )

    def _search_assets(self, command: Mapping[str, Any]) -> dict[str, Any]:
        query = _required_string(command, "query")
        names_only = command.get("namesOnly")
        return self.catalog.list_page(
            query=query,
            tag=_optional_string(command, "tag"),
            offset=_page_offset(command),
            limit=_optional_int(command, "limit") or 50,
            names_only=True if names_only is None else bool(names_only),
        )

    def _list_remote(self, command: Mapping[str, Any]) -> dict[str, Any]:
        return list_remote_assets(
            provider=_optional_string(command, "provider") or "polyhaven",
            asset_type=_optional_string(command, "type") or "models",
            query=_optional_string(command, "query"),
            offset=_page_offset(command),
            limit=_optional_int(command, "limit") or 25,
        )

    def _search_remote(self, command: Mapping[str, Any]) -> dict[str, Any]:
        return search_remote_assets(
            _required_string(command, "query"),
            provider=_optional_string(command, "provider") or "polyhaven",
            asset_type=_optional_string(command, "type") or "models",
            offset=_page_offset(command),
            limit=_optional_int(command, "limit") or 12,
        )

    def _info_remote(self, command: Mapping[str, Any]) -> dict[str, Any]:
        remote_id = _optional_string(command, "remoteId") or _optional_string(command, "asset")
        if not remote_id:
            raise ValueError("info_remote requires remoteId")
        include_files = command.get("includeFiles")
        return get_remote_asset_info(
            remote_id,
            provider=_optional_string(command, "provider") or "polyhaven",
            include_files=True if include_files is None else bool(include_files),
        )

    def _fetch_remote(self, command: Mapping[str, Any]) -> dict[str, Any]:
        remote_id = _optional_string(command, "remoteId") or _optional_string(command, "asset")
        if not remote_id:
            raise ValueError("fetch_remote requires remoteId")
        asset = fetch_remote_asset(
            remote_id,
            provider=_optional_string(command, "provider") or "polyhaven",
            catalog=self.catalog,
            catalog_id=_optional_string(command, "id"),
            cache_dir=_optional_string(command, "cacheDir"),
            resolution=_optional_string(command, "resolution") or "1k",
            asset_type=_optional_string(command, "type") or "models",
            force=bool(command.get("force", False)),
        )
        return {"asset": asset.to_document()}

    def _set_presentation(self, command: Mapping[str, Any]) -> dict[str, Any]:
        updates = _presentation_updates(command)
        asset_id = _optional_string(command, "asset")
        if asset_id:
            asset = self.catalog.get(asset_id)
            fmt = (asset.format or "").lower()
            if fmt not in HDRI_FORMATS:
                raise ValueError(
                    f"Catalog asset {asset.id!r} format {fmt!r} is not an HDRI "
                    f"(expected one of {sorted(HDRI_FORMATS)})"
                )
            if not asset.path:
                raise ValueError(f"Catalog asset {asset.id!r} has no local path")
            updates["environmentMap"] = asset.path
        if not updates:
            raise ValueError(
                "set_presentation requires presentation fields and/or an HDRI catalog asset"
            )
        merged = {**copy.deepcopy(self.scene._presentation), **updates}
        self.scene.set_presentation(**merged)
        return copy.deepcopy(self.scene._presentation)

    def _set_world(self, command: Mapping[str, Any]) -> dict[str, Any]:
        asset = self.catalog.get(_required_string(command, "asset"))
        if not asset.path:
            raise ValueError(f"Catalog asset {asset.id!r} has no local path")
        environment = self.scene.environment or self.scene.set_environment()
        world = environment.set_world_mesh(
            asset.path,
            format=asset.format,
            position=command.get("position"),
            rotation=command.get("rotation"),
            scale=command.get("scale"),
            visible=bool(command.get("visible", True)),
            catalog_asset=asset.id,
        )
        return world.to_dict()

    def _add_asset(self, command: Mapping[str, Any]) -> dict[str, Any]:
        asset = self.catalog.get(_required_string(command, "asset"))
        if not asset.path:
            raise ValueError(f"Catalog asset {asset.id!r} has no local path")
        node_id = str(command.get("id") or asset.id)
        mesh = self.scene.add_mesh(
            node_id,
            asset.path,
            format=asset.format,
            position=command.get("position"),
            rotation=command.get("rotation"),
            scale=command.get("scale"),
            visible=bool(command.get("visible", True)),
            parent_id=command.get("parentId"),
            tags=command.get("tags"),
            material=command.get("material"),
            physics=command.get("physics"),
            catalog_asset=asset.id,
        )
        return mesh.to_dict()

    def _add_primitive(self, command: Mapping[str, Any]) -> dict[str, Any]:
        node = self.scene.create_primitive(
            _required_string(command, "id"),
            _required_string(command, "primitive"),  # type: ignore[arg-type]
            parent_id=command.get("parentId"),
            tags=command.get("tags"),
            position=command.get("position"),
            rotation=command.get("rotation"),
            scale=command.get("scale"),
            size=command.get("size"),
            radius=float(command["radius"]) if "radius" in command else 0.5,
            height=float(command["height"]) if "height" in command else 1.0,
            visible=bool(command.get("visible", True)),
            material=command.get("material"),
            physics=command.get("physics"),
        )
        return node.to_dict()

    def _add_object(self, command: Mapping[str, Any]) -> dict[str, Any]:
        children = command.get("children")
        if children is not None and (
            not isinstance(children, list) or not all(isinstance(item, str) for item in children)
        ):
            raise ValueError("children must be a list of node ids")
        node = self.scene.add_object(
            _required_string(command, "id"),
            label=_optional_string(command, "label"),
            children=children,
            position=command.get("position"),
            rotation=command.get("rotation"),
            scale=command.get("scale"),
            visible=bool(command.get("visible", True)),
            parent_id=command.get("parentId"),
            tags=command.get("tags"),
        )
        return node.to_dict()

    def _add_annotation(self, command: Mapping[str, Any]) -> dict[str, Any]:
        target_id = _optional_string(command, "targetId")
        node = self.scene.add_annotation(
            _required_string(command, "id"),
            None if target_id else command.get("position", (0.0, 0.0, 0.0)),
            target_id=target_id,
            offset=command.get("offset"),
            label=_optional_string(command, "label"),
            description=_optional_string(command, "description"),
            visible=bool(command.get("visible", True)),
        )
        return node.to_dict()

    def _update_node(self, command: Mapping[str, Any]) -> dict[str, Any]:
        return self.scene.update_node(
            _required_string(command, "id"),
            position=command.get("position"),
            rotation=command.get("rotation"),
            scale=command.get("scale"),
            visible=command.get("visible"),
        )

    def _patch_node(self, command: Mapping[str, Any]) -> dict[str, Any]:
        patch = command.get("patch")
        if not isinstance(patch, dict):
            raise ValueError("patch_node requires an object patch")
        return self.scene.patch_node(_required_string(command, "id"), patch)

    def _reparent(self, command: Mapping[str, Any]) -> dict[str, Any]:
        parent_id = command.get("parentId")
        if parent_id is not None and not isinstance(parent_id, str):
            raise ValueError("parentId must be a string or null")
        return self.scene.reparent(_required_string(command, "id"), parent_id)

    def _delete_node(self, command: Mapping[str, Any]) -> dict[str, Any]:
        deleted = self.scene.delete_recursive(_required_string(command, "id"))
        return {"deleted": deleted}

    def _place_on_world(self, command: Mapping[str, Any]) -> dict[str, Any]:
        asset = self.catalog.get(_required_string(command, "asset"))
        if not asset.path:
            raise ValueError(f"Catalog asset {asset.id!r} has no local path")
        if "x" not in command or "z" not in command:
            raise ValueError("place_on_world requires x and z")
        if self.scene.environment is None:
            self.scene.set_environment()
        node_id = str(command.get("id") or asset.id)
        mesh = self.scene.place_on_world(
            node_id,
            asset.path,
            x=float(command["x"]),
            z=float(command["z"]),
            offset_y=float(command.get("offsetY", 0.0)),
            format=asset.format,
            rotation=command.get("rotation"),
            scale=command.get("scale"),
            visible=bool(command.get("visible", True)),
            catalog_asset=asset.id,
        )
        return mesh.to_dict()

    def _set_gameplay_role(self, command: Mapping[str, Any]) -> dict[str, Any]:
        node_id = _required_string(command, "id")
        role = _required_string(command, "role")
        manifest = GameManifest.from_dict(self.scene._game_manifest)
        manifest.set_gameplay_role(node_id, role)  # type: ignore[arg-type]
        self.scene.set_game(manifest)
        return {"id": node_id, "role": role, "game": manifest.to_dict()}

    def _validate_scene(self, command: Mapping[str, Any]) -> dict[str, Any]:
        del command
        self.scene.validate_graph()
        violations = self.scene.validate_environment(raise_on_reject=False)
        return {
            "graph": "ok",
            "environmentViolations": [item.to_dict() for item in violations],
        }

    def _get_scene(self, command: Mapping[str, Any]) -> dict[str, Any]:
        del command
        return self.scene.to_dict()

    def _perception(self, command: Mapping[str, Any]) -> dict[str, Any]:
        return apply_perception(self.scene, command)

    def _capture_view(self, command: Mapping[str, Any]) -> dict[str, Any]:
        del command
        raise ValueError(
            "capture_view requires a live viewer (sceneify-mcp --server URL or a started session)"
        )

    def _load(self, command: Mapping[str, Any]) -> dict[str, Any]:
        path = Path(_required_string(command, "path"))
        self.scene = Scene.load(path)
        return {"path": str(path), "name": self.scene.name}

    def _save(self, command: Mapping[str, Any]) -> dict[str, str]:
        path = Path(_required_string(command, "path"))
        return {"path": str(self.scene.save(path))}


def _required_string(command: Mapping[str, Any], key: str) -> str:
    value = command.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a nonempty string")
    return value


def _optional_string(command: Mapping[str, Any], key: str) -> str | None:
    value = command.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _optional_int(command: Mapping[str, Any], key: str) -> int | None:
    value = command.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _page_offset(command: Mapping[str, Any]) -> int:
    if "pageOffset" in command:
        value = _optional_int(command, "pageOffset")
        return 0 if value is None else value
    # Accept plain offset only when it is an integer page cursor.
    value = command.get("offset")
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("pageOffset must be an integer")
    if value < 0:
        raise ValueError("pageOffset must be >= 0")
    return value


def _presentation_updates(command: Mapping[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    nested = command.get("presentation")
    if nested is not None:
        if not isinstance(nested, Mapping):
            raise ValueError("presentation must be an object")
        for key, value in nested.items():
            if key in _PRESENTATION_KEYS:
                updates[key] = copy.deepcopy(value)
    for key in _PRESENTATION_KEYS:
        if key in command:
            updates[key] = copy.deepcopy(command[key])
    return updates


def _hint_for(action: str, exc: Exception) -> str:
    message = str(exc)
    if action in {"add_asset", "set_world", "place_on_world", "set_presentation"} and isinstance(
        exc, KeyError
    ):
        return "Call list_assets or fetch_remote before referencing a catalog id."
    if action == "fetch_remote" and "Resolution" in message:
        return "Try resolution '1k' or inspect search_remote results."
    if action == "set_presentation" and "HDRI" in message:
        return "Fetch a Poly Haven HDRI with type=hdris before set_presentation."
    if action == "place_on_world":
        return "Ensure an environment/world mesh exists, or call set_world first."
    if "Unsupported world action" in message:
        return "Use sceneify tool-spec to inspect supported actions."
    return "Inspect the error message and retry with a corrected action payload."
