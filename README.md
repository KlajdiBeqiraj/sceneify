# sceneify

Compose interactive 3D worlds from Python.

`sceneify` is a PyPI-oriented toolkit with a Streamlit-like API: load several
GLB assets, use a GLB as the world environment, place objects on it, annotate,
draw trajectories, edit transforms in the browser, then save/load the scene.

## Status

Alpha (v0.3). Core authoring loop works:

- geometric environment rules
- world mesh environment
- viewer edit mode + inspector
- `scene.save` / `Scene.load` JSON format

Tooling is **uv-first** (lockfile, dependency groups, CI). See
[docs/development.md](docs/development.md) and [docs/roadmap.md](docs/roadmap.md).

## Quick start

```bash
uv python install
uv sync --all-extras

cd web && npm ci && npm run build && cd ..
uv run python examples/world_edit_save.py
```

Press Enter to stop the server. In the viewer: toggle **Edit on**, move objects,
save from the sidebar.

```python
import sceneify as sf
from sceneify.demo_assets import download_public_asset

world = download_public_asset("damaged_helmet")
prop = download_public_asset("avocado")

scene = sf.Scene("demo")
env = scene.set_environment(bounds_min=(-4, 0, -4), bounds_max=(4, 4, 4), snap=0.1)
env.set_world_glb(str(world))
scene.place_on_world("prop", prop, x=1.2, z=0.3, scale=(10, 10, 10))
scene.save("world.sceneify.json")
scene.run()
```

Reload later:

```python
scene = sf.Scene.load("world.sceneify.json")
scene.run()
```

## Examples

```bash
uv run python examples/basic_scene.py
uv run python examples/environment_rules.py
uv run python examples/world_edit_save.py
uv run pytest
```

## Public demo assets

See [docs/demo-assets.md](docs/demo-assets.md).

```bash
uv run sceneify list-demos
uv run sceneify fetch-demo damaged_helmet
```

## Layout

- `src/sceneify/` Python package
- `web/` React + R3F viewer
- `examples/` samples
- `tests/` unit tests
- `docs/` guides and roadmap
- `uv.lock` reproducible Python deps

## License

MIT. Copyright (c) 2026 Klajdi Beqiraj.
