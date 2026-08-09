"""Optional MCP stdio server exposing sceneify world tools."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx

from sceneify.agent_tools import WorldTools, tool_definitions
from sceneify.catalog import AssetCatalog
from sceneify.scene import Scene
from sceneify.session_manager import SessionManager


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
            return {"action": action, "result": scene, "scene": scene}
        if action == "validate_scene":
            scene = self.scene
            scene.validate_graph()
            return {
                "action": action,
                "result": {
                    "graph": "ok",
                    "environmentViolations": [
                        item.to_dict() for item in scene.validate_environment(raise_on_reject=False)
                    ],
                },
                "scene": scene.to_dict(),
            }
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
        if action == "add_primitive":
            return {
                **_without(command, "action"),
                "action": "create_primitive",
            }
        if action == "add_asset":
            asset = self.catalog.get(_required_string(command, "asset"))
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


def create_world_session(
    *,
    scene_name: str = "mcp-world",
    catalog_path: str | Path | None = None,
    scene_path: str | Path | None = None,
) -> WorldTools:
    """Create the in-memory WorldTools session used by the MCP server."""
    scene = Scene.load(scene_path) if scene_path else Scene(scene_name)
    catalog = AssetCatalog.load(catalog_path) if catalog_path else AssetCatalog()
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
            "Discover assets with list/search tools (paginated). "
            "Filter happens inside sceneify on id/name first. "
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
    def sceneify_get_scene() -> dict[str, Any]:
        """Return the current scene document."""
        return _safe_apply(session, {"action": "get_scene"})

    @server.tool()
    def sceneify_validate_scene() -> dict[str, Any]:
        """Validate the scene graph and environment rules."""
        return _safe_apply(session, {"action": "validate_scene"})

    @server.tool()
    def sceneify_apply(action: str, **fields: Any) -> dict[str, Any]:
        """Apply one validated sceneify world action."""
        command = {"action": action, **fields}
        return _safe_apply(session, command)

    @server.tool()
    def sceneify_create_example(name: str, title: str | None = None) -> dict[str, Any]:
        """Create a source-sync-ready Python example under examples/mcp."""
        if manager is None:
            raise ValueError("Example sessions require sceneify-mcp --session-manager")
        path = manager.create_example(name, title=title)
        return {"path": str(path.relative_to(manager.project_root))}

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
    def sceneify_apply_session(sessionId: str, action: str, **fields: Any) -> dict[str, Any]:
        """Apply an action to the explicitly selected live example session."""
        if manager is None:
            raise ValueError("Example sessions require sceneify-mcp --session-manager")
        target = manager.get(sessionId)
        source = str(target.script.relative_to(manager.project_root))
        live = LiveWorldTools(target.url, source_path=source)
        return _safe_apply(live, {"action": action, **fields})

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

    catalog = AssetCatalog.load(args.catalog) if args.catalog else AssetCatalog()
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
            catalog_path=args.catalog,
            scene_path=args.scene,
        )
    manager = SessionManager(args.project_root) if args.session_manager else None
    server = build_mcp_server(tools, session_manager=manager)
    server.run(transport="stdio")


def _safe_apply(tools: WorldTools | LiveWorldTools, command: dict[str, Any]) -> dict[str, Any]:
    cleaned = {key: value for key, value in command.items() if value is not None}
    try:
        return {"ok": True, **tools.apply(cleaned)}
    except Exception as exc:
        return {
            "ok": False,
            "action": command.get("action"),
            "error": {
                "code": exc.__class__.__name__,
                "message": str(exc),
            },
            "scene": tools.scene.to_dict(),
        }


def _without(command: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    return {key: value for key, value in command.items() if key not in keys}


def _required_string(command: Mapping[str, Any], key: str) -> str:
    value = command.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a nonempty string")
    return value


if __name__ == "__main__":
    main()
