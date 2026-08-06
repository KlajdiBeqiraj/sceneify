# Coding agent tools

sceneify does not run a language model and does not depend on a model provider. A coding agent
owned by the application developer can translate a text request into small scene actions.

The public contract has three parts:

* `schemas/scene.schema.json` defines the saved world document
* `schemas/catalog.schema.json` defines the available GLB asset catalog
* `sceneify.agent_tools` applies deterministic catalog-grounded actions

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
tools.apply({"action": "set_world", "asset": "warehouse_shell"})
tools.apply(
    {
        "action": "add_asset",
        "asset": "forklift",
        "id": "forklift_1",
        "position": [2, 0, -1],
    }
)
tools.apply({"action": "save", "path": "warehouse.sceneify.json"})
```

Supported actions are `set_world`, `add_asset`, `add_object`, `add_annotation`, `update_node`, and
`save`. Asset actions accept only ids present in the catalog, so an agent selects existing assets
instead of inventing mesh files. The descriptor uses a neutral `inputSchema` field and can be
adapted to a coding agent, MCP server, or model API without adding provider packages to sceneify.

The same descriptor is available as JSON from `sceneify tool-spec`. Installed applications can
load the normative document schemas with `sceneify.load_schema("scene")` and
`sceneify.load_schema("catalog")`.
