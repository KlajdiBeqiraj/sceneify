# Asset catalogs

An asset catalog maps stable ids to local runtime paths and provenance metadata:

* `id`: a nonempty unique string
* `path`: a project-relative runtime path
* `format`, `license`, `source`, `checksum`, `thumbnail`, and `byteSize`: optional typed metadata
* `animations`: clip names exposed by animated GLB assets
* `tags`: a list of strings
* `metadata`: a JSON object

The document identity is `sceneify-asset-catalog`, version `2`. Version 1 catalogs remain readable.
Its normative schema is `schemas/catalog.schema.json`.

```json
{
  "format": "sceneify-asset-catalog",
  "version": 2,
  "assets": [
    {
      "id": "marble-bust",
      "path": "assets/marble-bust.glb",
      "format": "glb",
      "license": "CC0-1.0",
      "source": "https://polyhaven.com/a/marble_bust_01",
      "animations": [],
      "tags": ["sculpture", "roman"],
      "metadata": {"creator": "Poly Haven"}
    }
  ]
}
```

Python usage:

```python
from sceneify.catalog import Asset, AssetCatalog

catalog = AssetCatalog(assets=[Asset(id="robot", path="assets/robot.glb", tags=["character"])])
catalog.save("assets.catalog.json")
loaded = AssetCatalog.load("assets.catalog.json")
robot = loaded.get("robot")
```

JSON is supported without optional packages. Files ending in `.yaml` or `.yml` use PyYAML and
raise a clear import error when that package is unavailable. Loading validates the format, version,
field types, unknown fields, and duplicate ids.
