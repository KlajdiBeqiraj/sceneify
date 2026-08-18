<p align="center">
  <img src="assets/logo.svg" alt="sceneify" width="160" />
</p>

# sceneify

[![PyPI](https://img.shields.io/pypi/v/sceneify.svg)](https://pypi.org/project/sceneify/)
[![Python](https://img.shields.io/pypi/pyversions/sceneify.svg)](https://pypi.org/project/sceneify/)
[![License: MIT](https://img.shields.io/pypi/l/sceneify.svg)](https://pypi.org/project/sceneify/)

Build interactive browser-based 3D worlds from Python.

`sceneify` is a PyPI library with a Streamlit-like authoring API. Python defines the scene and
game behavior, while the bundled web viewer provides view, edit, and play modes. An optional
MCP server lets Cursor, Claude Code, Codex, GitHub Copilot, and other coding agents discover
assets and edit the world through catalog-grounded tools.

## Install

With uv:

```bash
uv add sceneify
```

With pip:

```bash
pip install sceneify
```

The published wheel includes the viewer. Node.js is required only when developing the viewer
itself.

## Create a world from Python or the editor

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
scene.run()
```

`scene.run()` opens the world editor. It can create primitives, import GLB files, instantiate
catalog assets, edit materials and physics, organize the hierarchy, undo commands, and save a
versioned scene.

The saved level becomes the input to a game script:

```python
import sceneify as sf

scene = sf.Scene.load("world.sceneify.json")


@scene.on_event
def game_event(current: sf.Scene, event: sf.SemanticEvent) -> None:
    print(event.name, event.node_id)


scene.play()
```

## Make a Python game

Python declares the world, controls, camera, sensors, HUD, timer, and outcomes. The browser runs
latency-sensitive movement and physics, while WebSocket carries semantic events and scene edits.

```python
import sceneify as sf

scene = sf.Scene("collect")
scene.create_primitive(
    "player",
    "capsule",
    position=(0, 1, 0),
    physics=sf.Physics(body="dynamic", collider="capsule"),
)

game = sf.Game()
game.action_map(
    moveForward=["KeyW", "ArrowUp"],
    moveBack=["KeyS", "ArrowDown"],
    moveLeft=["KeyA", "ArrowLeft"],
    moveRight=["KeyD", "ArrowRight"],
    jump=["Space"],
)
game.add_controller(
    "player"
)  # preset="simple" by default; use preset="ecctrl" for camera-relative controls
game.follow_camera("player")
game.set_hud(title="Collect and Escape")
game.set_timer(90)
scene.set_game(game)
scene.play()
```

Run the complete third-person vertical slice with a skinned KayKit character,
animation blending, GLB dungeon props, physics, collectibles, and HUD:

```bash
uv run python examples/game/collect_escape.py
```

Open the same world in authoring mode:

```bash
uv run python examples/game/collect_escape.py --edit
```

Run the Roman-inspired environment showcase with local HDR lighting, CC0 sculptures,
curated ruins, and mouse-driven points of interest:

```bash
uv run python examples/showcase/roman_environment.py
```

Open the same environment in the authoring editor:

```bash
uv run python examples/showcase/roman_environment.py --edit
```

The Roman showcase runs an automatic camera tour along a predefined path: wide
establishing shots, travel through the plaza, and close framing of each exhibit
with lowered lighting and a stable info panel. Markers remain for hover context in
edit mode. Asset sources and licenses are listed in
[`THIRD_PARTY_ASSETS.md`](THIRD_PARTY_ASSETS.md). Demo binaries remain in the Git
repository but are excluded from the PyPI wheel and source distribution.

Anchor POIs to scene objects instead of duplicating absolute coordinates:

```python
scene.add_annotation(
    "statue_info",
    target_id="marble_bust",
    offset=(0, 2, 0),
    label="Marble Bust 01",
)
```

See [docs/protocol.md](docs/protocol.md) for synchronization and semantic events.

## Build worlds with a coding agent (MCP)

sceneify does not run a language model. Any MCP-compatible coding agent can call `sceneify-mcp`
over stdio: Cursor, Claude Code, Codex, GitHub Copilot / VS Code, Windsurf, and similar hosts.
The agent discovers local catalog and remote CC0 assets (Poly Haven models/HDRIs, OS3A
environment GLBs), inspects the scene, and applies catalog-grounded mutations. Game runtime
features (controls, camera, HUD, timer, outcomes) stay in Python.

### Install MCP support

```bash
uv add "sceneify[mcp]"
# or: pip install "sceneify[mcp]"
sceneify install-skill
```

`sceneify install-skill` copies the bundled Agent Skill into `.agents/skills/sceneify-mcp`,
the portable path used by Cursor, Codex, Claude Code, and other Agent Skills hosts.

Host-specific copies:

```bash
sceneify install-skill --target cursor   # .cursor/skills
sceneify install-skill --target claude   # .claude/skills
sceneify install-skill --target codex    # .codex/skills
sceneify install-skill --target all --force
sceneify install-skill --user --force                 # ~/.agents/skills
sceneify install-skill --target cursor --user --force # ~/.cursor/skills
```

### Point the host at `sceneify-mcp`

Use `uv run` so the host finds the project environment. Restart the MCP server after changing
the config.

**Cursor** (`.cursor/mcp.json`) and **Claude Code** (`.mcp.json` at the project root):

```json
{
  "mcpServers": {
    "sceneify": {
      "command": "uv",
      "args": ["run", "sceneify-mcp", "--catalog", "assets.catalog.json"]
    }
  }
}
```

Live browser editing, with the viewer already running:

```json
{
  "mcpServers": {
    "sceneify": {
      "command": "uv",
      "args": [
        "run",
        "sceneify-mcp",
        "--server",
        "http://127.0.0.1:8765",
        "--source",
        "examples/workflows/sync_roundtrip.py",
        "--catalog",
        "assets.catalog.json"
      ]
    }
  }
}
```

**VS Code / GitHub Copilot** (`.vscode/mcp.json`):

```json
{
  "servers": {
    "sceneify": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "sceneify-mcp", "--catalog", "assets.catalog.json"]
    }
  }
}
```

**Codex** (`~/.codex/config.toml` or project `.codex/config.toml`):

```toml
[mcp_servers.sceneify]
command = "uv"
args = ["run", "sceneify-mcp", "--catalog", "assets.catalog.json"]
```

Windsurf and other MCP hosts use the same stdio command. If `sceneify-mcp` is already on
`PATH`, you can set `"command": "sceneify-mcp"` and pass the flags in `"args"`.

### Server modes

| Mode | How to start | Notes |
| --- | --- | --- |
| Standalone | `sceneify-mcp --catalog …` | In-memory scene; `load` / `save` via `sceneify_apply` |
| Live | `--server URL --source script.py` | Viewer is source of truth; mutations sync back to Python |
| Sessions | `--session-manager --catalog assets.catalog.json` | Isolated examples; fetch and place share one catalog |

Live example:

```bash
uv run python examples/workflows/sync_roundtrip.py
sceneify-mcp --server http://127.0.0.1:8765 --source examples/workflows/sync_roundtrip.py
```

The agent uses dedicated tools for discovery (`sceneify_search_assets`,
`sceneify_search_remote`, `sceneify_fetch_remote`), perception (`sceneify_describe_scene`,
`sceneify_topdown_map`, `sceneify_spatial_query`, `sceneify_get_node`), and mutations
(`sceneify_apply` / `sceneify_apply_session`). HDRI lighting is `set_presentation` with a
catalog id — do not send a required `extra` field. Full schemas are in
[docs/agent-tools.md](docs/agent-tools.md) and `sceneify tool-spec --all`.

The same actions are available without MCP from Python (`sf.WorldTools`) and the CLI:

```bash
sceneify tool-spec
sceneify search-remote barrel
sceneify search-remote outdoor --type hdris
sceneify search-remote floor --provider os3a
sceneify fetch-remote Barrel_01 --id barrel
sceneify apply plan.json --save world.sceneify.json
```

Using the live Poly Haven API requires crediting Poly Haven; the assets themselves remain CC0.
OS3A / Polygonal Mind environment packs are CC0. See [docs/catalog.md](docs/catalog.md),
[docs/schema.md](docs/schema.md), and [docs/export.md](docs/export.md).

## Optional extras

```bash
uv add "sceneify[mcp]"
uv add "sceneify[mesh]"
```

* `mcp` adds the MCP stdio server used by coding agents
* `mesh` adds local geometry processing with trimesh and NumPy

## Examples and checks

```bash
uv run pytest
```

Run every example from the repository root. Each group has one narrow purpose:

| Group | Example | What to observe |
| --- | --- | --- |
| Basics | `uv run python examples/basics/basic_scene.py` | GLB assets, hierarchy, annotations, and trajectories |
| Basics | `uv run python examples/basics/environment_rules.py` | Bounds, zones, snapping, and placement rules |
| Realtime | `uv run python examples/realtime/realtime_minigame.py` | Browser input handled by Python callbacks |
| Realtime | `uv run python examples/realtime/tick_delta_demo.py` | Python tick updates sent as compact pose deltas |
| Realtime | `uv run python examples/realtime/stress_many_assets.py` | GLB instancing and a browser performance stress scene |
| Game | `uv run python examples/game/prefab_demo.py` | One crate template, three overridden physics instances |
| Game | `uv run python examples/game/episode_demo.py --record` | Capture a short run, then replay the JSON episode |
| Game | `uv run python examples/game/collect_escape.py` | Complete third-person game: relics, enemies, hazards, and goal |
| Workflows | `uv run python examples/workflows/world_edit_save.py` | Create a world, edit it, and save a scene JSON |
| Workflows | `uv run python examples/workflows/sync_roundtrip.py` | Save JSON and write scene changes back to Python markers |
| Workflows | `uv run python examples/workflows/export_web_demo.py --serve` | Export a static viewer connected to the live Python backend |
| Showcase | `uv run python examples/showcase/roman_environment.py` | Automatic camera tour and interactive exhibit annotations |

Development uses uv, Python 3.13, and the committed lockfile. See
[docs/development.md](docs/development.md).

## License

MIT. Copyright (c) 2026 Klajdi Beqiraj.
