# Roadmap: from scene tool to simple 3D worlds / games

`sceneify` aims to make Python the authoring layer for interactive 3D worlds.

## Now (v0.3)

1. Geometric environment rules (bounds, ground, snap, zones)
2. World GLB as environment mesh + `place_on_world`
3. Edit mode in the viewer (select, translate, inspector panel)
4. Save / load `*.sceneify.json`
5. uv-first tooling (`uv.lock`, dependency groups, CI, ruff)

## Next

- Rotate/scale gizmos in edit mode (not only translate)
- Snap-to-surface while dragging in the viewer
- Optional `trimesh` collision for accurate `height_at` on complex GLBs
- Hot reload / websocket live sync for game loops
- Simple triggers, timers, and input bindings from Python
- glTF scene export beside the sceneify JSON format
- Physics adapter (optional) for rigid bodies

## Design rule

Keep the Python API small and Streamlit-like. Prefer:

```python
scene = Scene("level-1")
env = scene.set_environment(...)
env.set_world_glb("map.glb")
scene.place_on_world("hero", "hero.glb", x=0, z=0)
scene.run()
```

over heavy engine boilerplate.
