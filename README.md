# sceneify

Compose interactive 3D scenes from Python.

`sceneify` is a small PyPI-oriented toolkit for building multi-asset 3D worlds
with a Streamlit-like API: load several GLB (and other mesh) files, group them
into objects, place annotations, draw trajectories, then open a browser viewer.

## Status

Alpha scaffold. The Python scene graph and local server work; the React /
React Three Fiber viewer builds under `web/`. PLY rendering and richer object
tools will grow next.

## Install (editable)

```bash
cd work/sceneify
python -m venv .venv
source .venv/bin/activate
pip install -e .

cd web
npm install
npm run build
cd ..
```

## Quick start

```python
import sceneify as sf
from sceneify.demo_assets import download_public_asset

helmet = download_public_asset("damaged_helmet")
avocado = download_public_asset("avocado")

scene = sf.Scene("demo")
scene.add_glb("helmet", helmet)
scene.add_glb("avocado", avocado, position=(1.5, 0, 0), scale=(8, 8, 8))
scene.add_object("props", label="Props", children=["helmet", "avocado"])
scene.add_annotation("a1", position=(0, 1.1, 0), label="Helmet")
scene.add_trajectory(
    "path",
    points=[(-1, 0.2, 1), (0, 0.8, 1.2), (1.5, 0.2, 1)],
)
scene.run()
```

Or run the bundled example:

```bash
python examples/basic_scene.py
```

## Public demo assets

See [docs/demo-assets.md](docs/demo-assets.md) for public GLB/PLY sources and
the `sceneify fetch-demo` CLI.

```bash
sceneify list-demos
sceneify fetch-demo damaged_helmet
```

## Layout

- `src/sceneify/` Python package (scene graph, server, demo downloads)
- `web/` React + R3F viewer
- `examples/` runnable samples
- `docs/` guides

## License

MIT. Copyright (c) 2026 Klajdi Beqiraj.
