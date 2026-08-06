# Scene format

Sceneify writes a versioned JSON document. The current identity is:

* `format`: `sceneify-scene`
* `version`: `2`
* `scene`: the scene payload

`Scene.save()` always writes this wrapper. `Scene.load()` requires both identity fields on wrapped
documents and rejects unknown versions. Version 1 documents are migrated to version 2 when loaded.
For compatibility, the loader also accepts an unwrapped scene payload.

The normative schema is `schemas/scene.schema.json`. Consumers should reject document fields not
described by that schema.

Version 2 adds:

* primitive nodes for box, sphere, capsule, and plane geometry
* one explicit `parentId` per graph node
* material, physics, tags, and validated graph relationships
* a declarative game manifest separate from runtime state
* optional presentation settings for local HDR environments, camera, fog, shadows, and helpers
* typed browser metadata for GLB animation states, runtime visuals, and interactive POIs

Annotations may use `targetId` plus a world-space `offset` instead of duplicating an
absolute position. The browser resolves the target's current scene-graph transform, so
the POI continues to follow an object moved in the editor.

Example:

```json
{
  "format": "sceneify-scene",
  "version": 2,
  "scene": {
    "schemaVersion": 2,
    "name": "example",
    "background": "#0f1115",
    "environment": null,
    "meshes": [],
    "objects": [],
    "primitives": [
      {
        "kind": "primitive",
        "id": "ground",
        "parentId": null,
        "primitive": "plane",
        "position": [0, 0, 0],
        "rotation": [0, 0, 0],
        "scale": [1, 1, 1],
        "size": [12, 1, 12],
        "radius": 0.5,
        "height": 1,
        "visible": true,
        "tags": ["level"],
        "material": {
          "color": "#344054",
          "opacity": 1,
          "wireframe": false,
          "roughness": 0.65,
          "metalness": 0.05
        },
        "physics": {"body": "fixed", "collider": "cuboid", "sensor": false, "mass": 1},
        "meta": {}
      }
    ],
    "annotations": [],
    "trajectories": [],
    "game": null,
    "presentation": {
      "grid": false,
      "helpers": false,
      "shadows": true,
      "exposure": 1.05
    }
  }
}
```
