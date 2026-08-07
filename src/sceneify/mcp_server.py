"""Optional MCP stdio server exposing sceneify world tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sceneify.agent_tools import WorldTools, tool_definitions
from sceneify.catalog import AssetCatalog
from sceneify.scene import Scene


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


def build_mcp_server(tools: WorldTools | None = None) -> Any:
    """Build an MCP server instance. Requires the optional ``sceneify[mcp]`` extra."""
    try:
        from mcp.server.mcpserver import MCPServer
    except ImportError as exc:
        raise ImportError(
            'MCP support requires the optional dependency. Install with: uv add "sceneify[mcp]"'
        ) from exc

    session = tools or create_world_session()
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

    return server


def main(argv: list[str] | None = None) -> None:
    """Run the sceneify MCP server over stdio."""
    import argparse

    parser = argparse.ArgumentParser(prog="sceneify-mcp", description="sceneify MCP server")
    parser.add_argument("--catalog", help="Optional local asset catalog path")
    parser.add_argument("--scene", help="Optional sceneify scene path to load")
    parser.add_argument("--name", default="mcp-world", help="Scene name when creating a new scene")
    args = parser.parse_args(argv)

    tools = create_world_session(
        scene_name=args.name,
        catalog_path=args.catalog,
        scene_path=args.scene,
    )
    server = build_mcp_server(tools)
    server.run(transport="stdio")


def _safe_apply(tools: WorldTools, command: dict[str, Any]) -> dict[str, Any]:
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


if __name__ == "__main__":
    main()
