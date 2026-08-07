"""Tests for the optional MCP adapter."""

from __future__ import annotations

import pytest

from sceneify.agent_tools import WorldTools
from sceneify.catalog import AssetCatalog
from sceneify.scene import Scene


def test_build_mcp_server_registers_tools() -> None:
    pytest.importorskip("mcp")
    from sceneify.mcp_server import build_mcp_server

    tools = WorldTools(Scene("mcp"), AssetCatalog())
    server = build_mcp_server(tools)
    names = {tool.name for tool in server._tool_manager.list_tools()}
    assert "sceneify_list_assets" in names
    assert "sceneify_search_assets" in names
    assert "sceneify_list_remote" in names
    assert "sceneify_search_remote" in names
    assert "sceneify_info_remote" in names
    assert "sceneify_fetch_remote" in names
    assert "sceneify_apply" in names
