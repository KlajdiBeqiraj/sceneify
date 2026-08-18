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
sceneify install-skill --target all --force
sceneify install-skill --user --force                 # ~/.agents/skills
sceneify install-skill --target cursor --user --force # ~/.cursor/skills (stale until this)
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
| Sessions | `--session-manager` | Use session tools; apply with `sceneify_apply_session`. Fetch and place share one process catalog. |

## Play vs editor

* `scene.play()` — input, ticks, and `on_input` / `on_tick` / `on_event`. Use this for games.
* `scene.run()` — editor only. No WASD/click play loop.
* `create_example(kind="game")` scaffolds markers + `.play()`. `kind="world"` (default) uses `.run()`.

### When to use `Game()` vs host Python

`sf.Game()` is a **collect-the-relic 3rd-person** DSL: controller, collectible, hazard, checkpoint, goal, timer, HUD, enemy wave. MCP can assign roles with `set_gameplay_role` but cannot author controller/HUD/timer.

For **anything else** (board games, turn-based, chess, custom rules): keep logic in the example Python file with `@scene.on_input` / `@scene.on_tick` / `@scene.on_event`. MCP cannot write that runtime. Pattern: `examples/realtime/realtime_minigame.py`. Do not reverse-engineer the viewer or invent a ChessEngine in core.

Play-mode click on a mesh/primitive/object emits semantic event `node_picked` (handle with `@scene.on_event`). Annotation POI clicks stay `poi_selected`.

`node_picked` is for `scene.play()` **without** `Game()`. With `Game()` active, primitives live in the overlap/pickup loop, not click-to-select. Do not mix overlap and pick in the same `Game()` run. There is no generic match HUD or GameWorld click layer — that split is the product boundary, not a missing feature.

### HUD vs annotations

Every annotation with `visible=True` draws a **yellow POI sphere**. That is not a match HUD. Sceneify does **not** ship a DOM overlay independent of `Game()`. Do not attach `Game()` only for a scoreboard.

* Collect-the-relic status: `Game.set_hud` (requires `scene.set_game(game)`).
* Other games: host Python (`on_input` / `on_tick` / labels). Pattern: `examples/realtime/realtime_minigame.py`.
* Hide a node: `update_node` / `patch_node` with `visible=False` (supported live).
* Label without the sphere: `add_annotation(..., marker=False)` (or `meta.marker=false`).
* Never teleport labels to `y=-40` to hide the sphere.

## Remote assets (catalog-grounded)

Session-manager and stdio share **one catalog** for the MCP process. After `fetch_remote`, call `apply_session` `add_asset` / `set_presentation` with the **catalog id**. Do not hardcode `.sceneify_cache/...` paths.

* Poly Haven `type=hdris` — single-file `.hdr`; `set_presentation(asset=<catalogId>)`.
* Poly Haven `type=models` — downloaded as glTF + bin + textures, then **packed to `.glb`** in the catalog so `/api/asset` can load it. Prefer OS3A / KayKit GLB for gameplay meshes when you have a choice.
* OS3A `type=environments|models` — already GLB.

Never invent mesh paths. Credit Poly Haven when using the live API.

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

For HDRI lighting, fetch a Poly Haven HDRI (`type=hdris`) then `set_presentation` with
`asset=<catalogId>` via `sceneify_apply` or `sceneify_apply_session`.

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
* `sceneify://scene/overview` — compact describe_scene summary (prefer this)
* `sceneify://scene/topdown` — ASCII XZ occupancy map
* `sceneify://scene/current` — full scene JSON (large; debug only)
* `sceneify://tool-spec` — full action descriptors

## Scene perception

The agent does **not** see the browser. Use structured perception tools before editing an
existing world. Coordinates are Y-up; `+X` is east, `-Z` is north; rotations are Euler degrees.

Required inspect loop before mutating a non-empty scene:

1. `sceneify_describe_scene` (`detail=summary`) — inventory, tree, root world poses
2. `sceneify_topdown_map` — layout on XZ (top of ASCII = north)
3. `sceneify_get_node` / `sceneify_spatial_query` on the targets you will move
4. Mutate with one small action; re-check with describe or get_node (not full `get_scene`)
5. Live only: `sceneify_capture_view` to verify appearance (not for exact meters)

```text
describe_scene(detail=summary)
→ topdown_map(cellSize=1)
→ spatial_query(mode=nearest|relative, ...)
→ get_node(id=...)
→ update_node / add_*
→ describe_scene or capture_view
```

Use **world** poses from perception tools for alignment. Local transforms in raw JSON are
parent-relative and misleading under hierarchies.

## Tools

### Discovery (prefer these over inventing asset ids)

* `sceneify_list_assets` / `sceneify_search_assets` — local catalog, paginated
* `sceneify_list_remote` / `sceneify_search_remote` — remote CC0 providers, paginated
  * `provider=polyhaven` — `type=models` (packed to GLB) or `type=hdris` (HDR environment maps)
  * `provider=os3a` — `type=environments` or `type=models` for environment/place GLB packs
* `sceneify_info_remote` — metadata + file variants for one `remoteId`
* `sceneify_fetch_remote` — download into `.sceneify_cache`, pack Poly Haven models to GLB, register in the **shared** catalog

Pagination fields: `pageOffset`, `limit`, response `total` / `hasMore` / `nextOffset`.
Filtering is done inside sceneify (id/name first, then tags). Default remote `provider` is `polyhaven`.

### Scene inspection / perception

* `sceneify_describe_scene` — compact overview + tree + world poses (`detail=summary|full`)
* `sceneify_list_nodes` — paginated nodes with world poses (`tag` / `kind` / `query`)
* `sceneify_get_node` — one node: local+world, children, bounds, anchored annotations
* `sceneify_topdown_map` — ASCII occupancy map on XZ
* `sceneify_spatial_query` — `nearest` | `distance` | `relative` | `in_radius` | `height_at`
* `sceneify_get_bounds` — world AABB for a node or the whole scene
* `sceneify_capture_view` — PNG from live viewer (`preset=presentation|topdown|focus`)
* `sceneify_validate_scene` — graph + environment rules
* `sceneify_get_scene` — full document (large; prefer describe/list)

Perception responses omit the full scene dump (`sceneIncluded: false`). Pass
`includeScene: true` on mutations only when you need the raw document.

### Presentation

HDRI lighting: `sceneify_apply` / `sceneify_apply_session` with `action=set_presentation` and
`asset=<catalogId>` of a fetched HDRI. Also accepts `environmentMap`, `environmentPreset`,
`ambientIntensity`, `background`, `fog`, `camera`, `shadows`, `title`, and nested `presentation`.

Pass `asset` only for a fetched HDRI (`hdr`, `exr`, or `hdri`). A GLB world or architecture asset
must be used with `set_world` or `add_asset`, never as the presentation `asset`.

### Mutations

* `sceneify_apply` — `{ "action": "<name>", ...fields }` or `action` + `fields` object. Do **not** send `extra`.
* With `--session-manager`: `sceneify_create_example` (`kind=world|game`), `sceneify_start_session`, `sceneify_list_sessions`, `sceneify_stop_session`, `sceneify_apply_session` (same payload; shared catalog with `fetch_remote`)

Every tool response includes `ok`. On failure read `error.code` / `error.message` and retry with a corrected payload.

## Required workflow for remote assets

### Models / places

1. `sceneify_search_remote` (or list) with the intended provider/type → pick a real `remoteId`
2. `sceneify_info_remote` → confirm variants / resolution
3. `sceneify_fetch_remote` with optional local catalog `id` (models are stored as packed GLB)
4. `sceneify_apply` / `sceneify_apply_session` with `add_asset` or `set_world` using that catalog id — never a cache filesystem path
5. `sceneify_validate_scene`
6. Standalone only: `sceneify_apply` with `save`

For places/architecture packs use `provider=os3a`, `type=environments` (modular
floors/platforms/structures).

### HDRI lighting

1. `sceneify_search_remote(query="outdoor", provider="polyhaven", type="hdris")`
2. `sceneify_info_remote` for the selected result
3. `sceneify_fetch_remote` with `type=hdris` and a local catalog `id`
4. `sceneify_apply` / `sceneify_apply_session` with `action=set_presentation` and `asset=<catalogId>`

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
2. Before editing an existing scene: `describe_scene` → `topdown_map` → `get_node` / `spatial_query`.
3. Use world poses and spatial_query for placement; do not guess from raw local transforms.
4. Discover before place — search/list with provider and type, then fetch, then add or set world.
5. One small MCP action at a time; check `ok` after mutations.
6. Prefer dedicated perception/list/search/info tools; use `sceneify_apply` for world edits.
7. Configure game runtime in Python (`Game()` or `on_input`/`on_tick`). MCP cannot author custom game engines.
8. Keep live `--source` scripts patchable (marked region or simple literals).
9. Run `sceneify_validate_scene` after structural changes and resolve graph/environment violations.
10. Use HDRIs only through `set_presentation` with a catalog id; do not place them as meshes or hardcode `.sceneify_cache` paths.
11. `capture_view` is visual confirmation only; use structured tools for meters and yaw.
12. Do not use annotations as match HUD; do not hide POI spheres by moving them underground.
13. Do not attach `Game()` only for HUD, and do not expect click-to-pick on `Game()` primitives.
14. Do not sandbox-assume paths: MCP stdio is for a local trusted client.
15. For full schemas see package docs `docs/agent-tools.md`, `docs/environment.md`, `docs/schema.md`, or `sceneify tool-spec --all`.
