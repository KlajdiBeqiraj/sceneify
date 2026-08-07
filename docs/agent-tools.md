# Coding agent tools

sceneify does not run a language model and does not depend on a model provider. A coding agent
owned by the application developer can translate a text request into small scene actions.

The public contract has four parts:

* `schemas/scene.schema.json` defines the saved world document
* `schemas/catalog.schema.json` defines the available asset catalog
* `sceneify.agent_tools` applies deterministic catalog-grounded actions
* `sceneify.remote_assets` can search/download Poly Haven CC0 models into the local catalog

```python
from sceneify import Scene
from sceneify.agent_tools import WorldTools, tool_definition
from sceneify.catalog import AssetCatalog

scene = Scene("warehouse")
catalog = AssetCatalog.load("assets.catalog.json")
tools = WorldTools(scene, catalog)

# Give this neutral descriptor to the developer's coding agent adapter.
descriptor = tool_definition()

# Apply the structured calls returned by that adapter.
tools.apply({"action": "list_remote", "pageOffset": 0, "limit": 25})
tools.apply({"action": "search_remote", "query": "bust", "pageOffset": 0, "limit": 10})
tools.apply({"action": "info_remote", "remoteId": "marble_bust_01"})
tools.apply({"action": "fetch_remote", "remoteId": "marble_bust_01", "id": "bust"})
tools.apply(
    {
        "action": "add_asset",
        "asset": "bust",
        "id": "bust_1",
        "position": [2, 0, -1],
    }
)
tools.apply({"action": "save", "path": "warehouse.sceneify.json"})
```

Discovery tools are paginated (`pageOffset`, `limit`, `total`, `hasMore`, `nextOffset`).
sceneify performs filtering itself: local/remote search prefer **id/name**, then tags.

Supported actions include:

* local catalog: `list_assets`, `search_assets`
* remote Poly Haven: `list_remote`, `search_remote`, `info_remote`, `fetch_remote`
* world authoring: `set_world`, `add_asset`, `add_primitive`, `add_object`, `add_annotation`,
  `update_node`, `patch_node`, `reparent`, `delete_node`, `place_on_world`, `set_gameplay_role`
* document ops: `validate_scene`, `get_scene`, `load`, `save`

Asset placement accepts only ids present in the catalog, so an agent selects existing or fetched
assets instead of inventing mesh files.

## CLI

```bash
sceneify tool-spec
sceneify tool-spec --all
sceneify list-remote --limit 25 --offset 0
sceneify search-remote bust --limit 10
sceneify info-remote marble_bust_01
sceneify fetch-remote marble_bust_01 --id bust --catalog assets.catalog.json
sceneify apply plan.json --catalog assets.catalog.json --save world.sceneify.json
```

## Optional MCP server

Install the optional extra and run the stdio server:

```bash
uv add "sceneify[mcp]"
sceneify-mcp --catalog assets.catalog.json
```

The server exposes catalog/scene resources plus tools for list/search/fetch/apply. Using the live
Poly Haven API requires crediting Poly Haven to end users (API terms); the assets themselves remain
CC0.

The descriptor uses a neutral `inputSchema` field and can be adapted to a coding agent, MCP server,
or model API without adding provider packages to sceneify core.

The same descriptor is available as JSON from `sceneify tool-spec`. Installed applications can
load the normative document schemas with `sceneify.load_schema("scene")` and
`sceneify.load_schema("catalog")`.
