# Demo assets (public GLB and PLY)

`sceneify` does not ship large binary samples. Download public assets into a
local cache, then pass the file paths to `Scene.add_glb` / `Scene.add_mesh`.

## Built-in fetch helper

```bash
pip install -e .
sceneify list-demos
sceneify fetch-demo damaged_helmet
sceneify fetch-demo avocado
```

Files land in `.sceneify_cache/` (gitignored).

From Python:

```python
from sceneify.demo_assets import download_public_asset, list_public_assets

print(list_public_assets())
path = download_public_asset("damaged_helmet")
```

## Recommended public sources

### GLB / glTF

- [Khronos glTF Sample Models](https://github.com/KhronosGroup/glTF-Sample-Models)
  - DamagedHelmet (GLB)
  - Avocado (GLB)
  - Many other scenes for multi-asset demos

Example raw URL pattern (DamagedHelmet):

```text
https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Models/master/2.0/DamagedHelmet/glTF-Binary/DamagedHelmet.glb
```

Check the upstream repository license before redistribution.

### PLY

- [Stanford 3D Scanning Repository](https://graphics.stanford.edu/data/3Dscanrep/)
  - Classic scans (often archives; extract a PLY locally)
- three.js example PLY (`dolphins.ply`) via `sceneify fetch-demo dolphins_ply`

PLY display in the web viewer is planned; the Python scene graph already accepts
`format="ply"` so you can wire assets early.

## Multi-asset scene tip

Fetch two GLBs, place them with different `position` / `scale`, group with
`add_object(..., children=[...])`, then add annotations and a trajectory for a
minimal “world” demo without private data.
