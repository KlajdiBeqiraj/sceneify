<p align="center">
  <img src="https://raw.githubusercontent.com/KlajdiBeqiraj/sceneify/main/assets/logo.png" alt="sceneify" width="160" />
</p>

# sceneify

[![PyPI](https://img.shields.io/pypi/v/sceneify.svg)](https://pypi.org/project/sceneify/)
[![Python](https://img.shields.io/pypi/pyversions/sceneify.svg)](https://pypi.org/project/sceneify/)
[![License: MIT](https://img.shields.io/pypi/l/sceneify.svg)](https://pypi.org/project/sceneify/)
[![GitHub](https://img.shields.io/badge/github-KlajdiBeqiraj%2Fsceneify-181717?logo=github)](https://github.com/KlajdiBeqiraj/sceneify)

Build interactive browser-based 3D worlds and games from Python.

`sceneify` is a Streamlit-like authoring API: Python defines the scene and game
behavior, while a bundled web viewer provides view, edit, and play modes. The
published wheel includes the viewer, so Node.js is not required to install or
run a world. An optional MCP server lets Cursor, Claude Code, Codex, GitHub
Copilot, and other coding agents edit those worlds through catalog-grounded tools.

## Features

- Author 3D scenes from Python (primitives, GLB/GLTF/PLY assets, materials, physics)
- Live world editor in the browser, with save/load of versioned `.sceneify.json` scenes
- Gameplay helpers: controllers, follow camera, HUD, timer, collectibles, hazards
- Semantic events over WebSocket so Python stays in the loop
- Agent tools and an optional MCP server for coding agents
- Remote CC0 assets (Poly Haven models/HDRIs, OS3A environments)

## Install

```bash
pip install sceneify
```

With uv:

```bash
uv add sceneify
```

Requires Python 3.12+.

Optional extras:

```bash
pip install "sceneify[mcp]"    # MCP stdio server for coding agents
pip install "sceneify[mesh]"   # local geometry with trimesh and NumPy
```

## Quickstart

```python
import sceneify as sf

scene = sf.Scene("my-level")
scene.create_primitive(
    "ground",
    "plane",
    size=(16, 1, 16),
    material=sf.Material("#344054"),
    physics=sf.Physics(body="fixed", collider="cuboid"),
)
scene.save("world.sceneify.json")
scene.run()  # opens the world editor
```

Load a saved level and handle game events:

```python
import sceneify as sf

scene = sf.Scene.load("world.sceneify.json")


@scene.on_event
def game_event(current: sf.Scene, event: sf.SemanticEvent) -> None:
    print(event.name, event.node_id)


scene.play()
```

## Coding agents (MCP)

Install the extra, copy the Agent Skill, and point the host at the stdio server:

```bash
pip install "sceneify[mcp]"
sceneify install-skill
```

Cursor (`.cursor/mcp.json`) and Claude Code (`.mcp.json`):

```json
{
  "mcpServers": {
    "sceneify": {
      "command": "sceneify-mcp",
      "args": ["--catalog", "assets.catalog.json"]
    }
  }
}
```

VS Code / GitHub Copilot uses `.vscode/mcp.json` with a `servers` object. Codex uses
`[mcp_servers.sceneify]` in its TOML config. `sceneify install-skill --target all`
also writes host-specific skill copies (`.cursor`, `.claude`, `.codex`).
Reinstall with `--force` if a host copy is stale (`--user --target cursor` for `~/.cursor/skills`).

See the [GitHub README](https://github.com/KlajdiBeqiraj/sceneify#build-worlds-with-a-coding-agent-mcp)
and [agent tools](https://github.com/KlajdiBeqiraj/sceneify/blob/main/docs/agent-tools.md).

CLI without MCP:

```bash
sceneify tool-spec
sceneify search-remote barrel
sceneify fetch-remote Barrel_01 --id barrel
```

## Links

- [Source](https://github.com/KlajdiBeqiraj/sceneify)
- [Issues](https://github.com/KlajdiBeqiraj/sceneify/issues)
- [Releases](https://github.com/KlajdiBeqiraj/sceneify/releases)
- [Agent tools](https://github.com/KlajdiBeqiraj/sceneify/blob/main/docs/agent-tools.md)
- [Protocol](https://github.com/KlajdiBeqiraj/sceneify/blob/main/docs/protocol.md)
- [Development](https://github.com/KlajdiBeqiraj/sceneify/blob/main/docs/development.md)

## License

MIT. Copyright (c) 2026 Klajdi Beqiraj.
