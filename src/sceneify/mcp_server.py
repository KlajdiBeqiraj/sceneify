"""Optional MCP stdio server exposing sceneify world tools."""

from __future__ import annotations

import inspect
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx

from sceneify.agent_tools import ACTION_SCHEMA, WorldTools, tool_definitions
from sceneify.catalog import AssetCatalog
from sceneify.perception import apply_perception, describe_scene, is_read_action, topdown_map
from sceneify.remote_assets import HDRI_FORMATS
from sceneify.scene import Scene
from sceneify.session_manager import SessionManager

_PERCEPTION_ACTIONS = frozenset(
    {
        "describe_scene",
        "get_node",
        "list_nodes",
        "topdown_map",
        "spatial_query",
        "get_bounds",
    }
)


class LiveWorldTools:
    """Apply agent actions to the scene served by a running sceneify process."""

    def __init__(
        self,
        server_url: str,
        *,
        source_path: str | None = None,
        catalog: AssetCatalog | None = None,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.source_path = source_path
        self.catalog = catalog or AssetCatalog()
        self._local = WorldTools(Scene("mcp-assets"), self.catalog)

    @property
    def scene(self) -> Scene:
        payload = self._request("GET", "/api/scene")
        payload.pop("revision", None)
        return Scene.from_dict(payload)

    def apply(self, command: Mapping[str, Any]) -> dict[str, Any]:
        action = command.get("action")
        if not isinstance(action, str):
            raise ValueError("action must be a string")
        if action in {
            "list_assets",
            "search_assets",
            "list_remote",
            "search_remote",
            "info_remote",
            "fetch_remote",
        }:
            return self._local.apply(command)
        if action == "get_scene":
            scene = self._scene_payload()
            include_scene = command.get("includeScene")
            if include_scene is None:
                include_scene = True
            payload: dict[str, Any] = {"action": action, "result": scene}
            if include_scene:
                payload["scene"] = scene
            else:
                payload["sceneIncluded"] = False
            return payload
        if action == "validate_scene":
            scene = self.scene
            scene.validate_graph()
            result = {
                "action": action,
                "result": {
                    "graph": "ok",
                    "environmentViolations": [
                        item.to_dict() for item in scene.validate_environment(raise_on_reject=False)
                    ],
                },
            }
            if command.get("includeScene"):
                result["scene"] = scene.to_dict()
            else:
                result["sceneIncluded"] = False
            return result
        if action in _PERCEPTION_ACTIONS:
            result = apply_perception(self.scene, command)
            response: dict[str, Any] = {"action": action, "result": result}
            if command.get("includeScene"):
                response["scene"] = self.scene.to_dict()
            else:
                response["sceneIncluded"] = False
            return response
        if action == "capture_view":
            return self._capture_view(command)
        if action in {"load", "save"}:
            raise ValueError(f"{action} is unavailable for a live MCP session")

        revision = self._revision()
        server_command = self._server_command(command)
        ack = self._request(
            "POST",
            "/api/commands",
            json={**server_command, "expectedRevision": revision},
        )
        if self.source_path:
            self._request(
                "POST",
                "/api/scene/save-python",
                json={
                    "path": self.source_path,
                    "mode": "auto",
                    "expectedRevision": ack["revision"],
                },
            )
        return {"action": action, "result": ack.get("result"), "scene": ack["scene"]}

    def _scene_payload(self) -> dict[str, Any]:
        return self._request("GET", "/api/scene")

    def _revision(self) -> int:
        revision = self._scene_payload().get("revision")
        if isinstance(revision, bool) or not isinstance(revision, int):
            raise ValueError("Live scene server returned an invalid revision")
        return revision

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        with httpx.Client(base_url=self.server_url, timeout=30.0) as client:
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"Live scene server returned an invalid response for {path}")
        return payload

    def _server_command(self, command: Mapping[str, Any]) -> dict[str, Any]:
        action = str(command["action"])
        if action == "set_presentation":
            payload = dict(_without(command, "action"))
            asset_id = payload.get("asset")
            if isinstance(asset_id, str) and asset_id:
                try:
                    asset = self.catalog.get(asset_id)
                except KeyError as exc:
                    raise ValueError(
                        f"Unknown catalog asset {asset_id!r}. "
                        "Call fetch_remote (or list_assets) before set_presentation."
                    ) from exc
                fmt = (asset.format or "").lower()
                if fmt not in HDRI_FORMATS:
                    raise ValueError(
                        f"Catalog asset {asset.id!r} format {fmt!r} is not an HDRI "
                        f"(expected one of {sorted(HDRI_FORMATS)})"
                    )
                if not asset.path:
                    raise ValueError(f"Catalog asset {asset.id!r} has no local path")
                payload["environmentMap"] = asset.path
                payload.pop("asset", None)
            return {"action": "set_presentation", **payload}
        if action == "add_primitive":
            return {
                **_without(command, "action"),
                "action": "create_primitive",
            }
        if action == "add_asset":
            asset_id = _required_string(command, "asset")
            try:
                asset = self.catalog.get(asset_id)
            except KeyError as exc:
                raise ValueError(
                    f"Unknown catalog asset {asset_id!r}. "
                    "Call fetch_remote (or list_assets) before add_asset."
                ) from exc
            if not asset.path:
                raise ValueError(f"Catalog asset {asset.id!r} has no local path")
            return {
                **_without(command, "action", "asset"),
                "action": "create_asset",
                "assetId": asset.id,
                "source": asset.path,
            }
        if action == "add_object":
            return {
                **_without(command, "action"),
                "action": "create",
                "kind": "object",
            }
        if action == "add_annotation":
            return {"action": "add_annotation", **_without(command, "action")}
        if action == "set_world":
            asset = self.catalog.get(_required_string(command, "asset"))
            if not asset.path:
                raise ValueError(f"Catalog asset {asset.id!r} has no local path")
            return {
                **_without(command, "action", "asset"),
                "action": "set_world",
                "assetId": asset.id,
                "source": asset.path,
                "format": asset.format,
            }
        if action == "update_node":
            patch = {
                key: command[key]
                for key in ("position", "rotation", "scale", "visible")
                if key in command
            }
            return {"action": "patch", "id": command.get("id"), "patch": patch}
        if action == "patch_node":
            return {"action": "patch", "id": command.get("id"), "patch": command.get("patch")}
        if action == "reparent":
            return {
                "action": "reparent",
                "id": command.get("id"),
                "parentId": command.get("parentId"),
            }
        if action == "delete_node":
            return {"action": "delete", "id": command.get("id")}
        if action == "set_gameplay_role":
            return {
                "action": "set_gameplay_role",
                "id": command.get("id"),
                "role": command.get("role"),
            }
        raise ValueError(f"Action {action!r} is not yet supported by a live MCP session")

    def _capture_view(self, command: Mapping[str, Any]) -> dict[str, Any]:
        body: dict[str, Any] = {
            "preset": command.get("preset") or "presentation",
            "width": int(command.get("width") or 1280),
            "height": int(command.get("height") or 720),
        }
        for key in ("nodeId", "eye", "target", "fov"):
            if key in command:
                body[key] = command[key]
        payload = self._request("POST", "/api/scene/capture", json=body)
        return {"action": "capture_view", "result": payload, "sceneIncluded": False}


def create_world_session(
    *,
    scene_name: str = "mcp-world",
    catalog: AssetCatalog | None = None,
    catalog_path: str | Path | None = None,
    scene_path: str | Path | None = None,
) -> WorldTools:
    """Create the in-memory WorldTools session used by the MCP server."""
    scene = Scene.load(scene_path) if scene_path else Scene(scene_name)
    if catalog is None:
        catalog = AssetCatalog.load_or_create(catalog_path) if catalog_path else AssetCatalog()
    elif catalog_path:
        catalog.bind_path(catalog_path)
    return WorldTools(scene, catalog)


def build_mcp_server(
    tools: WorldTools | LiveWorldTools | None = None,
    *,
    session_manager: SessionManager | None = None,
) -> Any:
    """Build an MCP server instance. Requires the optional ``sceneify[mcp]`` extra."""
    try:
        from mcp.server.mcpserver import MCPServer
    except ImportError as exc:
        raise ImportError(
            'MCP support requires the optional dependency. Install with: uv add "sceneify[mcp]"'
        ) from exc

    session = tools or create_world_session()
    manager = session_manager
    server = MCPServer(
        name="sceneify",
        instructions=(
            "Build sceneify worlds with catalog-grounded actions. "
            "Before editing an existing scene, call sceneify_describe_scene then "
            "sceneify_topdown_map / sceneify_spatial_query for layout awareness. "
            "Prefer world poses from perception tools over raw get_scene. "
            "Discover assets with list/search tools (paginated). "
            "Use info_remote before fetch_remote, then add_asset. "
            "Credit Poly Haven when using the live API."
        ),
    )

    @server.resource("sceneify://catalog")
    def catalog_resource() -> str:
        return json.dumps(session.catalog.to_document(), indent=2)

    @server.resource("sceneify://scene/current")
    def scene_resource() -> str:
        return json.dumps(session.scene.to_dict(), indent=2)

    @server.resource("sceneify://scene/overview")
    def scene_overview_resource() -> str:
        return json.dumps(describe_scene(session.scene, detail="summary"), indent=2)

    @server.resource("sceneify://scene/topdown")
    def scene_topdown_resource() -> str:
        return json.dumps(topdown_map(session.scene), indent=2)

    @server.resource("sceneify://tool-spec")
    def tool_spec_resource() -> str:
        return json.dumps(tool_definitions(), indent=2)

    @server.tool()
    def sceneify_list_assets(
        query: str | None = None,
        tag: str | None = None,
        namesOnly: bool = True,
        pageOffset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List local catalog assets with pagination. Optional query filters by id/name."""
        return _safe_apply(
            session,
            {
                "action": "list_assets",
                "query": query,
                "tag": tag,
                "namesOnly": namesOnly,
                "pageOffset": pageOffset,
                "limit": limit,
            },
        )

    @server.tool()
    def sceneify_search_assets(
        query: str,
        tag: str | None = None,
        namesOnly: bool = True,
        pageOffset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Search the local catalog by name/id with pagination."""
        return _safe_apply(
            session,
            {
                "action": "search_assets",
                "query": query,
                "tag": tag,
                "namesOnly": namesOnly,
                "pageOffset": pageOffset,
                "limit": limit,
            },
        )

    @server.tool()
    def sceneify_list_remote(
        query: str | None = None,
        provider: str = "polyhaven",
        type: str = "models",
        pageOffset: int = 0,
        limit: int = 25,
    ) -> dict[str, Any]:
        """List remote Poly Haven assets with pagination (filtered by sceneify)."""
        command: dict[str, Any] = {
            "action": "list_remote",
            "provider": provider,
            "type": type,
            "pageOffset": pageOffset,
            "limit": limit,
        }
        if query:
            command["query"] = query
        return _safe_apply(session, command)

    @server.tool()
    def sceneify_search_remote(
        query: str,
        provider: str = "polyhaven",
        type: str = "models",
        pageOffset: int = 0,
        limit: int = 12,
    ) -> dict[str, Any]:
        """Search remote assets by text; sceneify filters on id/name first."""
        return _safe_apply(
            session,
            {
                "action": "search_remote",
                "query": query,
                "provider": provider,
                "type": type,
                "pageOffset": pageOffset,
                "limit": limit,
            },
        )

    @server.tool()
    def sceneify_info_remote(
        remoteId: str,
        provider: str = "polyhaven",
        includeFiles: bool = True,
    ) -> dict[str, Any]:
        """Get detailed metadata and file variants for one remote asset id."""
        return _safe_apply(
            session,
            {
                "action": "info_remote",
                "remoteId": remoteId,
                "provider": provider,
                "includeFiles": includeFiles,
            },
        )

    @server.tool()
    def sceneify_fetch_remote(
        remoteId: str,
        provider: str = "polyhaven",
        id: str | None = None,
        resolution: str = "1k",
        type: str = "models",
        force: bool = False,
        cacheDir: str | None = None,
    ) -> dict[str, Any]:
        """Download one remote asset into cache and register it in the catalog."""
        command: dict[str, Any] = {
            "action": "fetch_remote",
            "remoteId": remoteId,
            "provider": provider,
            "resolution": resolution,
            "type": type,
            "force": force,
        }
        if id:
            command["id"] = id
        if cacheDir:
            command["cacheDir"] = cacheDir
        return _safe_apply(session, command)

    @server.tool()
    def sceneify_get_scene(includeScene: bool = True) -> dict[str, Any]:
        """Return the full scene document (large). Prefer describe_scene for perception."""
        return _safe_apply(session, {"action": "get_scene", "includeScene": includeScene})

    @server.tool()
    def sceneify_validate_scene() -> dict[str, Any]:
        """Validate the scene graph and environment rules."""
        return _safe_apply(session, {"action": "validate_scene"})

    @server.tool()
    def sceneify_describe_scene(
        detail: str = "summary",
        tags: list[str] | None = None,
        roots: list[str] | None = None,
        maxNodes: int = 200,
        includeAnnotations: bool = True,
    ) -> dict[str, Any]:
        """Compact scene overview with hierarchy tree and world poses."""
        command: dict[str, Any] = {
            "action": "describe_scene",
            "detail": detail,
            "maxNodes": maxNodes,
            "includeAnnotations": includeAnnotations,
        }
        if tags is not None:
            command["tags"] = tags
        if roots is not None:
            command["roots"] = roots
        return _safe_apply(session, command)

    @server.tool()
    def sceneify_get_node(id: str, includeBounds: bool = True) -> dict[str, Any]:
        """Inspect one node: local+world transform, children, bounds, annotations."""
        return _safe_apply(
            session,
            {"action": "get_node", "id": id, "includeBounds": includeBounds},
        )

    @server.tool()
    def sceneify_list_nodes(
        tag: str | None = None,
        kind: str | None = None,
        query: str | None = None,
        parentId: str | None = None,
        pageOffset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Paginated scene nodes with world poses."""
        command: dict[str, Any] = {
            "action": "list_nodes",
            "pageOffset": pageOffset,
            "limit": limit,
        }
        if tag is not None:
            command["tag"] = tag
        if kind is not None:
            command["kind"] = kind
        if query is not None:
            command["query"] = query
        if parentId is not None:
            command["parentId"] = parentId
        return _safe_apply(session, command)

    @server.tool()
    def sceneify_topdown_map(
        cellSize: float = 1.0,
        width: int | None = None,
        height: int | None = None,
        focus: list[float] | None = None,
        maxCells: int = 80,
    ) -> dict[str, Any]:
        """ASCII top-down occupancy map on XZ (top of ascii = north / -Z)."""
        command: dict[str, Any] = {
            "action": "topdown_map",
            "cellSize": cellSize,
            "maxCells": maxCells,
        }
        if width is not None:
            command["width"] = width
        if height is not None:
            command["height"] = height
        if focus is not None:
            command["focus"] = focus
        return _safe_apply(session, command)

    @server.tool()
    def sceneify_spatial_query(
        mode: str,
        id: str | None = None,
        fromId: str | None = None,
        toId: str | None = None,
        point: list[float] | None = None,
        k: int = 5,
        radius: float | None = None,
        tag: str | None = None,
        kind: str | None = None,
        x: float | None = None,
        z: float | None = None,
    ) -> dict[str, Any]:
        """Spatial relations: nearest, distance, relative, in_radius, height_at."""
        command: dict[str, Any] = {"action": "spatial_query", "mode": mode, "k": k}
        if id is not None:
            command["id"] = id
        if fromId is not None:
            command["fromId"] = fromId
        if toId is not None:
            command["toId"] = toId
        if point is not None:
            command["point"] = point
        if radius is not None:
            command["radius"] = radius
        if tag is not None:
            command["tag"] = tag
        if kind is not None:
            command["kind"] = kind
        if x is not None:
            command["x"] = x
        if z is not None:
            command["z"] = z
        return _safe_apply(session, command)

    @server.tool()
    def sceneify_get_bounds(id: str | None = None) -> dict[str, Any]:
        """World AABB for one node, or the whole scene when id is omitted."""
        command: dict[str, Any] = {"action": "get_bounds"}
        if id is not None:
            command["id"] = id
        return _safe_apply(session, command)

    @server.tool()
    def sceneify_capture_view(
        preset: str = "presentation",
        nodeId: str | None = None,
        width: int = 1280,
        height: int = 720,
        eye: list[float] | None = None,
        target: list[float] | None = None,
        fov: float | None = None,
    ) -> Any:
        """Capture a PNG screenshot from a live viewer (requires --server or a session)."""
        if not isinstance(session, LiveWorldTools):
            return {
                "ok": False,
                "action": "capture_view",
                "error": {
                    "code": "CaptureUnavailable",
                    "message": (
                        "capture_view requires a live viewer "
                        "(sceneify-mcp --server URL or a started session)"
                    ),
                },
            }
        command: dict[str, Any] = {
            "action": "capture_view",
            "preset": preset,
            "width": width,
            "height": height,
        }
        if nodeId is not None:
            command["nodeId"] = nodeId
        if eye is not None:
            command["eye"] = eye
        if target is not None:
            command["target"] = target
        if fov is not None:
            command["fov"] = fov
        result = _safe_apply(session, command)
        if not result.get("ok"):
            return result
        capture = result.get("result")
        if not isinstance(capture, dict):
            return result
        image_b64 = capture.get("image")
        if not isinstance(image_b64, str) or not image_b64:
            return result
        try:
            from mcp.types import ImageContent, TextContent

            meta = {
                "ok": True,
                "action": "capture_view",
                "preset": capture.get("preset") or preset,
                "camera": capture.get("camera"),
                "width": capture.get("width"),
                "height": capture.get("height"),
                "mimeType": capture.get("mimeType") or "image/png",
            }
            return [
                TextContent(type="text", text=json.dumps(meta)),
                ImageContent(
                    type="image",
                    data=image_b64,
                    mimeType=str(capture.get("mimeType") or "image/png"),
                ),
            ]
        except Exception:
            return result

    @server.tool()
    @_with_apply_signature()
    def sceneify_apply(
        action: str,
        fields: dict[str, Any] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """Apply one validated sceneify world action."""
        command = _merge_apply_payload(action, fields, extra)
        return _safe_apply(session, command)

    @server.tool()
    def sceneify_scaffold(
        family: str,
        title: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Create a playable present, character, or board shell under examples/mcp.

        family=present — orbit/HDRI room plus embed snippet next steps.
        family=character — controller plus optional collect/reach objectives.
        family=board — clickable grid, pieces, turns, HUD; rules stay in Python.
        """
        if manager is None:
            raise ValueError("Scaffold requires sceneify-mcp --session-manager")
        normalized = family.strip().lower()
        path = manager.scaffold(normalized, name=name, title=title)
        relative = str(path.relative_to(manager.project_root))
        next_steps = _scaffold_next_steps(normalized, relative)
        result: dict[str, Any] = {
            "path": relative,
            "family": normalized,
            "nextSteps": next_steps,
        }
        if normalized == "present":
            from sceneify.export_web import embed_snippets

            result["embed"] = embed_snippets(
                api_base="http://127.0.0.1:8765",
                mode="look",
                src="./embed.html",
            )
        return result

    @server.tool()
    def sceneify_create_example(
        name: str,
        title: str | None = None,
        kind: str = "world",
    ) -> dict[str, Any]:
        """Create a source-sync-ready Python example under examples/mcp.

        kind=world (default) starts the editor with .run().
        kind=game starts a play loop with .play() and a stub on_input.
        """
        if manager is None:
            raise ValueError("Example sessions require sceneify-mcp --session-manager")
        path = manager.create_example(name, title=title, kind=kind)
        return {"path": str(path.relative_to(manager.project_root)), "kind": kind}

    @server.tool()
    def sceneify_start_session(script: str, sessionId: str | None = None) -> dict[str, object]:
        """Start an isolated example session and return its browser URL."""
        if manager is None:
            raise ValueError("Example sessions require sceneify-mcp --session-manager")
        return manager.start(script, session_id=sessionId).to_dict()

    @server.tool()
    def sceneify_list_sessions() -> list[dict[str, object]]:
        """List conversational example sessions and their browser URLs."""
        if manager is None:
            raise ValueError("Example sessions require sceneify-mcp --session-manager")
        return manager.list()

    @server.tool()
    def sceneify_stop_session(sessionId: str) -> dict[str, object]:
        """Stop one isolated example session."""
        if manager is None:
            raise ValueError("Example sessions require sceneify-mcp --session-manager")
        return manager.stop(sessionId)

    @server.tool()
    @_with_apply_signature(session=True)
    def sceneify_apply_session(
        sessionId: str,
        action: str,
        fields: dict[str, Any] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """Apply an action to the explicitly selected live example session."""
        if manager is None:
            raise ValueError("Example sessions require sceneify-mcp --session-manager")
        command = _merge_apply_payload(action, fields, extra)
        target = manager.get(sessionId)
        source = str(target.script.relative_to(manager.project_root))
        live = LiveWorldTools(target.url, source_path=source, catalog=session.catalog)
        return _safe_apply(live, command)

    return server


def main(argv: list[str] | None = None) -> None:
    """Run the sceneify MCP server over stdio."""
    import argparse

    parser = argparse.ArgumentParser(prog="sceneify-mcp", description="sceneify MCP server")
    parser.add_argument("--catalog", help="Optional local asset catalog path")
    parser.add_argument("--scene", help="Optional sceneify scene path to load")
    parser.add_argument("--name", default="mcp-world", help="Scene name when creating a new scene")
    parser.add_argument(
        "--server",
        help="Base URL of a running sceneify viewer to edit instead of creating an isolated scene",
    )
    parser.add_argument(
        "--source",
        help="Python authoring script to synchronize after every live MCP mutation",
    )
    parser.add_argument(
        "--session-manager",
        action="store_true",
        help="Enable isolated examples under examples/mcp and session-aware MCP tools",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root used by --session-manager (default: current directory)",
    )
    args = parser.parse_args(argv)

    catalog = AssetCatalog.load_or_create(args.catalog) if args.catalog else AssetCatalog()
    if args.server and args.session_manager:
        parser.error("--server and --session-manager cannot be combined")
    if args.server:
        tools: WorldTools | LiveWorldTools = LiveWorldTools(
            args.server,
            source_path=args.source,
            catalog=catalog,
        )
    else:
        if args.source:
            parser.error("--source requires --server")
        tools = create_world_session(
            scene_name=args.name,
            catalog=catalog,
            catalog_path=args.catalog,
            scene_path=args.scene,
        )
    manager = SessionManager(args.project_root) if args.session_manager else None
    server = build_mcp_server(tools, session_manager=manager)
    server.run(transport="stdio")


def _with_apply_signature(*, session: bool = False):
    """Rewrite FastMCP inputSchema so VAR_KEYWORD ``extra`` is not required."""

    def decorator(fn):
        fn.__signature__ = _apply_signature(session=session)
        return fn

    return decorator


def _apply_signature(*, session: bool = False) -> inspect.Signature:
    params: list[inspect.Parameter] = []
    if session:
        params.append(
            inspect.Parameter("sessionId", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str)
        )
    params.append(
        inspect.Parameter("action", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str)
    )
    params.append(
        inspect.Parameter(
            "fields",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=None,
            annotation=dict[str, Any] | None,
        )
    )
    for name in ACTION_SCHEMA["properties"]:
        if name == "action":
            continue
        params.append(
            inspect.Parameter(
                name,
                inspect.Parameter.KEYWORD_ONLY,
                default=None,
                annotation=Any,
            )
        )
    return inspect.Signature(params, return_annotation=dict[str, Any])


def _merge_apply_payload(
    action: str,
    fields: dict[str, Any] | None,
    extra: Mapping[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    nested = extra.get("fields")
    if isinstance(nested, Mapping):
        payload.update(nested)
    if isinstance(fields, Mapping):
        payload.update(fields)
    for key, value in extra.items():
        if key == "fields" or value is None:
            continue
        payload[key] = value
    return {"action": action, **payload}


def _safe_apply(tools: WorldTools | LiveWorldTools, command: dict[str, Any]) -> dict[str, Any]:
    cleaned = {key: value for key, value in command.items() if value is not None}
    try:
        return {"ok": True, **tools.apply(cleaned)}
    except Exception as exc:
        failure: dict[str, Any] = {
            "ok": False,
            "action": command.get("action"),
            "error": {
                "code": exc.__class__.__name__,
                "message": str(exc),
            },
        }
        action = command.get("action")
        include_scene = command.get("includeScene")
        if include_scene is None:
            include_scene = isinstance(action, str) and not is_read_action(action)
        if include_scene:
            failure["scene"] = tools.scene.to_dict()
        else:
            failure["sceneIncluded"] = False
        return failure


def _without(command: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    return {key: value for key, value in command.items() if key not in keys}


def _scaffold_next_steps(family: str, path: str) -> list[str]:
    start = f"sceneify_start_session(script={path!r})"
    if family == "present":
        return [
            start,
            "Decorate with catalog / Poly Haven HDRI via set_presentation.",
            "Call scene.export_web(...) then paste EMBED.txt (<sceneify-viewer> or iframe) on the site.",
        ]
    if family == "character":
        return [
            start,
            "Place ground, player, pickups or an exit. Use play.objective('collect'|'reach'|'survive').",
            "Do not attach overlap collect to a board.",
        ]
    return [
        start,
        "Keep rules in the short @board.on_pick handler. Do not add a named chess/go engine.",
        "Use board.place / move / next_turn / end('win'|'lose'|'draw').",
    ]


def _required_string(command: Mapping[str, Any], key: str) -> str:
    value = command.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a nonempty string")
    return value


if __name__ == "__main__":
    main()
