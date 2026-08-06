# Geometric environment

Define a playable volume and constraints for scene nodes.

## Concepts

- **Bounds**: axis-aligned box for the world volume
- **Ground**: plane at constant `y`
- **Snap grid**: quantize positions on X/Y/Z
- **Zones**: named boxes with role `allowed`, `forbidden`, or `marker`
- **Rules**: how constraints behave when placing or validating points

## Rule modes

- `off`: ignored
- `warn`: record a violation, keep the point (except snap/clamp kinds that still suggest)
- `clamp`: move the point to a legal suggestion when possible
- `reject`: raise `ValueError` on violation

## Default factory

`scene.set_environment(...)` builds defaults:

- bounds + ground
- optional snap grid
- rules: `inside_bounds` clamp, `above_ground` clamp, `outside_forbidden` reject,
  and `snap_to_grid` clamp when snap is set

## World mesh (GLB as environment)

```python
env = scene.set_environment(...)
env.set_world_glb("factory.glb")
scene.place_on_world("robot", "robot.glb", x=1.0, z=2.0, offset_y=0.05)
```

`place_on_world` uses world-mesh raycast when `pip install sceneify[mesh]`
(trimesh) is available; otherwise it falls back to `ground.y`.

```python
violations = scene.validate_environment()
for item in violations:
    print(item.rule, item.node_id, item.message)
```

## Viewer

The web client draws bounds (wireframe), ground, zone volumes, and axes when an
environment is present in `/api/scene`.
