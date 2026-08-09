---
name: sceneify-mcp
description: Build and edit sceneify 3D worlds and browser games through sceneify's Python API and MCP server. Use when creating scenes, interactive worlds, player gameplay, physics, objectives, HUDs, catalog, Poly Haven models/HDRIs, OS3A environment GLBs, validating scene graphs, or running sceneify-mcp.
---

# sceneify MCP

sceneify does not run a language model. The host coding agent calls MCP tools; sceneify applies catalog-grounded actions to a scene.

Use the Python API to create a game's declarative runtime (controls, camera, objectives, HUD,
timer, enemies). Use MCP to discover assets and iteratively edit the running world's graph.

## Setup (once per project)

1. Install MCP support:

```bash
uv add "sceneify[mcp]"
# or: pip install "sceneify[mcp]"
```

2. Install this skill into the project (portable path used by Cursor, Codex, and others):

```bash
sceneify install-skill
```

Host-specific copies:

```bash
sceneify install-skill --target cursor
sceneify install-skill --target claude
sceneify install-skill --target codex
sceneify install-skill --target all
sceneify install-skill --user   # install under ~/.agents/skills
```

3. Configure the MCP stdio server in the host. Example Cursor `.cursor/mcp.json`:

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

Live browser editing (viewer already running):

```json
{
  "mcpServers": {
    "sceneify": {
      "command": "sceneify-mcp",
      "args": [
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

Isolated example sessions (optional):

```bash
sceneify-mcp --session-manager --catalog assets.catalog.json
```

## Modes

| Mode | How to start | Notes |
| --- | --- | --- |
| Standalone | `sceneify-mcp --catalog …` | In-memory scene; `load` / `save` via `sceneify_apply` |
| Live | `--server URL --source script.py` | Viewer is source of truth; mutations sync to Python; `load`/`save` unavailable |
| Sessions | `--session-manager` | Use session tools; apply with `sceneify_apply_session` |

## Build worlds and games

Start from the user's gameplay goal before selecting assets. State the following briefly when
requirements are incomplete: player goal, movement/camera style, success/failure conditions,
world scale, and visual theme. Then build in layers:

1. **Blockout** — ground, playable bounds, major routes, obstacles, spawn and goal.
2. **Collision** — fixed colliders for floors, walls and props; dynamic physics only for moving
   bodies. Pair decorative GLBs with simple invisible primitive colliders when needed.
3. **Presentation** — HDRI or preset lighting, background, fog, camera, materials, then visual assets.
4. **Gameplay** — player controller, camera, collectibles/hazards/checkpoints/goal, HUD and timer.
5. **Iteration** — run the viewer, use live MCP for small changes, validate after mutations.

Do not begin with dozens of remote assets. Validate a small playable greybox before decorating it.

### World fundamentals (Python)

Create a named scene, set its presentation, define the playable environment, and use stable,
meaningful node ids. Coordinates use `[x, y, z]`; Y is up.

```python
import sceneify as sf

scene = sf.Scene("Forest Ruins", background="#15261d")
scene.set_presentation(
    shadows=True,
    environmentPreset="sunset",
    fog={"color": "#15261d", "near": 20, "far": 80},
    camera={"position": [14, 12, 18], "target": [0, 0, 0], "fov": 50},
    title="Forest Ruins",
)
scene.set_environment(
    bounds_min=(-20, 0, -20),
    bounds_max=(20, 12, 20),
    ground_y=0,
    snap=0.5,
)
scene.create_primitive(
    "ground",
    "box",
    size=(40, 0.2, 40),
    position=(0, -0.1, 0),
    material=sf.Material("#38533a"),
    physics=sf.Physics(body="fixed", collider="cuboid"),
    tags=["ground"],
)
```

For a terrain or architectural GLB, fetch it into the catalog, then use MCP `set_world`.
Prefer `provider=os3a` for themed environment packs (floors, platforms, architecture pieces).
Use MCP `place_on_world` for placed catalog assets. With `sceneify[mesh]`, placement raycasts
the world mesh; otherwise it falls back to the environment ground plane.

For HDRI lighting, fetch a Poly Haven HDRI (`type=hdris`) then call `sceneify_set_presentation`
with `asset=<catalogId>` (or `set_presentation` via `sceneify_apply`).

### Physics rules

* Use `Physics(body="fixed", collider="cuboid")` for ground, walls, and static blockers.
* Use `Physics(body="dynamic", collider="capsule")` for a player body.
* Keep collision shapes simple and align them with visible geometry.
* Put a visual GLB under a physics parent when its mesh does not make a reliable collider.
* Do not assign physics to every decorative asset without a gameplay reason.

### Game fundamentals (Python)

MCP can assign gameplay roles with `set_gameplay_role`, but it does **not** expose an action to
configure controller bindings, camera, HUD, timer, outcomes, or enemy waves. Author those in the
Python source, then use live MCP to iterate on nodes and transforms.

```python
import sceneify as sf

player_y = 1.0
scene.create_primitive(
    "player",
    "capsule",
    position=(0, player_y, 8),
    radius=0.3,
    height=0.8,
    physics=sf.Physics(body="dynamic", collider="capsule", mass=1),
    tags=["player"],
)
scene.create_primitive(
    "relic_1",
    "sphere",
    position=(2, 1, 0),
    radius=0.35,
    tags=["pickup"],
)
scene.create_primitive(
    "exit",
    "box",
    position=(0, 1, -12),
    size=(2, 2, 1),
    tags=["goal"],
)

game = sf.Game()
game.action_map(
    moveForward=["KeyW", "ArrowUp"],
    moveBack=["KeyS", "ArrowDown"],
    moveLeft=["KeyA", "ArrowLeft"],
    moveRight=["KeyD", "ArrowRight"],
    jump=["Space"],
)
game.add_controller("player", preset="ecctrl", move_speed=5, jump_speed=7)
game.follow_camera("player", distance=6, height=3)
game.add_collectible("relic_1")
game.add_goal("exit", required_score=1)
game.set_hud(title="Find the relic", controls_hint="Move: WASD · Jump: Space")
game.set_timer(120)
game.outcomes(win_message="The ruins are restored", lose_message="Time ran out")
scene.set_game(game)
```

Use `preset="simple"` for the default third-person controller. Use `preset="ecctrl"` for
camera-relative movement, sprinting, and a follow camera. A player body needs a floor and
appropriate colliders before the controller can be meaningfully tested.

### Gameplay design checklist

* Create exactly one player body and controller; place it on stable ground.
* Give pickups, hazards, checkpoints, and goals clear ids and spatial separation.
* Set the goal's `required_score` to match the number/value of required collectibles.
* Add a checkpoint before a difficult hazard; do not make failure states ambiguous.
* Give the HUD an objective and controls hint; make the timer consistent with the game scope.
* Test the full loop: spawn → movement → pickup/hazard → goal or loss → outcome.

## Resources

Read when you need schema or state:

* `sceneify://catalog` — local catalog document
* `sceneify://scene/current` — current scene JSON
* `sceneify://tool-spec` — full action descriptors

## Tools

### Discovery (prefer these over inventing asset ids)

* `sceneify_list_assets` / `sceneify_search_assets` — local catalog, paginated
* `sceneify_list_remote` / `sceneify_search_remote` — remote CC0 providers, paginated
  * `provider=polyhaven` — `type=models` (glTF) or `type=hdris` (HDR environment maps)
  * `provider=os3a` — `type=environments` or `type=models` for environment/place GLB packs
* `sceneify_info_remote` — metadata + file variants for one `remoteId`
* `sceneify_fetch_remote` — download into `.sceneify_cache` and register in catalog

Pagination fields: `pageOffset`, `limit`, response `total` / `hasMore` / `nextOffset`.
Filtering is done inside sceneify (id/name first, then tags). Default remote `provider` is `polyhaven`.

### Scene inspection

* `sceneify_get_scene`
* `sceneify_validate_scene`

### Presentation

* `sceneify_set_presentation` — merges settings into the existing presentation. It supports
  `asset` (a fetched HDRI catalog id), `environmentMap`, `environmentPreset`,
  `ambientIntensity`, `background`, `fog`, `camera`, `shadows`, `title`, and `presentation`
  for supported additional fields.

Pass `asset` only for a fetched HDRI (`hdr`, `exr`, or `hdri`). A GLB world or architecture asset
must be used with `set_world` or `add_asset`, never as the presentation `asset`.

### Mutations

* `sceneify_apply` — `{ "action": "<name>", ...fields }` or `action` + `fields` object
* With `--session-manager`: `sceneify_create_example`, `sceneify_start_session`, `sceneify_list_sessions`, `sceneify_stop_session`, `sceneify_apply_session`

Every tool response includes `ok`. On failure read `error.code` / `error.message` and retry with a corrected payload.

## Required workflow for remote assets

### Models / places

1. `sceneify_search_remote` (or list) with the intended provider/type → pick a real `remoteId`
2. `sceneify_info_remote` → confirm variants / resolution
3. `sceneify_fetch_remote` with optional local catalog `id`
4. `sceneify_apply` with `add_asset` or `set_world` using that catalog id
5. `sceneify_validate_scene`
6. Standalone only: `sceneify_apply` with `save`

For places/architecture packs use `provider=os3a`, `type=environments` (modular
floors/platforms/structures).

### HDRI lighting

1. `sceneify_search_remote(query="outdoor", provider="polyhaven", type="hdris")`
2. `sceneify_info_remote` for the selected result
3. `sceneify_fetch_remote` with `type=hdris` and a local catalog `id`
4. `sceneify_set_presentation` with `asset=<catalogId>` (merges into existing presentation)

Never invent mesh paths or catalog ids. Credit Poly Haven when using the live API; assets remain CC0.
OS3A / Polygonal Mind packs are CC0.

## Common `sceneify_apply` actions

World authoring: `set_presentation`, `set_world`, `add_asset`, `add_primitive`, `add_object`, `add_annotation`, `update_node`, `patch_node`, `reparent`, `delete_node`, `place_on_world`, `set_gameplay_role`

Document ops: `validate_scene`, `get_scene`, `load`, `save` (`load`/`save` standalone only)

Primitives: `box`, `sphere`, `capsule`, `plane`

Gameplay roles: `none`, `player-spawn`, `pickup`, `hazard`, `checkpoint`, `goal`

Vectors are `[x, y, z]`.

### Examples

```json
{"action": "add_primitive", "id": "ground", "primitive": "plane", "size": [16, 1, 16]}
```

```json
{"action": "add_asset", "asset": "bust", "id": "bust_1", "position": [2, 0, -1]}
```

```json
{"action": "set_presentation", "asset": "sky", "shadows": true, "ambientIntensity": 0.45}
```

```json
{"action": "update_node", "id": "bust_1", "position": [3, 0, -1]}
```

```json
{"action": "save", "path": "world.sceneify.json"}
```

## Agent rules

1. Turn a vague game request into a small playable loop before adding decoration.
2. Discover before place — search/list with provider and type, then fetch, then add or set world.
3. One small MCP action at a time; check `ok` after mutations.
4. Prefer dedicated list/search/info/presentation tools; use `sceneify_apply` for world edits.
5. Configure game runtime features in Python; MCP's `set_gameplay_role` alone does not add a controller or game rules.
6. Keep live `--source` scripts patchable (marked region or simple literals).
7. Run `sceneify_validate_scene` after structural changes and resolve graph/environment violations.
8. Use HDRIs only through `sceneify_set_presentation`; do not place them as meshes.
9. Do not sandbox-assume paths: MCP stdio is for a local trusted client.
10. For full schemas see package docs `docs/agent-tools.md`, `docs/environment.md`, `docs/schema.md`, or `sceneify tool-spec --all`.
