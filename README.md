<p align="center">
  <img src="assets/logo.svg" alt="sceneify" width="160" />
</p>

# sceneify

Build interactive browser-based 3D worlds from Python.

`sceneify` is a PyPI library with a Streamlit-like authoring API. Python defines the scene and
game behavior, while the bundled web viewer provides view, edit, and play modes.

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

## Use with Gymnasium and Stable Baselines3

The optional RL extra installs Gymnasium only:

```bash
uv add "sceneify[rl]"
```

`sceneify.rl.ReachTargetEnv` trains headless and can stream a human render to the browser. Stable
Baselines3 is not a sceneify dependency. Add it to the application that needs it:

```bash
uv add stable-baselines3 "sceneify[rl]"
```

## Build worlds with a coding agent

sceneify does not run a language model and does not install a model provider. It exposes a
versioned scene schema, an asset catalog, and deterministic actions. A developer's coding agent
can translate text into those actions using local catalog assets or remote CC0 downloads
(Poly Haven models/HDRIs, OS3A environment GLBs).

```python
import sceneify as sf

scene = sf.Scene("warehouse")
catalog = sf.AssetCatalog()
tools = sf.WorldTools(scene, catalog)

tools.apply({"action": "search_remote", "query": "barrel", "provider": "polyhaven"})
tools.apply({"action": "fetch_remote", "remoteId": "Barrel_01", "id": "barrel"})
tools.apply(
    {
        "action": "add_asset",
        "asset": "barrel",
        "id": "barrel_1",
        "position": [2, 0, -1],
    }
)
tools.apply(
    {
        "action": "fetch_remote",
        "remoteId": "kloppenheim_06",
        "type": "hdris",
        "id": "sky",
    }
)
tools.apply({"action": "set_presentation", "asset": "sky", "shadows": True})
tools.apply({"action": "save", "path": "warehouse.sceneify.json"})
```

Useful CLI entry points:

```bash
sceneify tool-spec
sceneify search-remote barrel
sceneify search-remote outdoor --type hdris
sceneify search-remote floor --provider os3a
sceneify fetch-remote Barrel_01 --id barrel
sceneify fetch-remote kloppenheim_06 --type hdris --id sky
sceneify apply plan.json --save world.sceneify.json
```

Optional MCP stdio server for Cursor/Claude-compatible hosts:

```bash
uv add "sceneify[mcp]"
sceneify install-skill
uv run python examples/workflows/sync_roundtrip.py
sceneify-mcp --server http://127.0.0.1:8765 --source examples/workflows/sync_roundtrip.py
```

`sceneify install-skill` copies the bundled Agent Skill into `.agents/skills/sceneify-mcp`
(portable across Cursor, Codex, Claude Code, and similar hosts). Use
`sceneify install-skill --target all` for host-specific copies, or `--user` for a home-directory
install. Point the host MCP config at `sceneify-mcp` (see [docs/agent-tools.md](docs/agent-tools.md)).

See [docs/agent-tools.md](docs/agent-tools.md), [docs/catalog.md](docs/catalog.md), and
[docs/schema.md](docs/schema.md), and [docs/export.md](docs/export.md). Using the live Poly Haven
API requires crediting Poly Haven; the assets themselves remain CC0. OS3A / Polygonal Mind
environment packs are CC0.

The `sceneify[llm]` extra is a dependency-free compatibility marker. Agent tools ship in the core
package and remain independent from model SDKs. The `sceneify[mcp]` extra only adds the MCP SDK.

## Optional extras

```bash
uv add "sceneify[mesh]"
uv add "sceneify[rl]"
uv add "sceneify[llm]"
uv add "sceneify[mcp]"
```

* `mesh` adds local geometry processing with trimesh and NumPy
* `rl` adds the Gymnasium environment interface
* `llm` keeps a provider-neutral install target without installing model runtimes
* `mcp` adds the optional MCP stdio server for coding agents

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
