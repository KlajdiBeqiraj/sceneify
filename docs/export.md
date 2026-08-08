# Static web export

Export a **hostable viewer frontend** that keeps talking to a live sceneify Python
backend. This is not an offline game runtime: physics/play/events stay on the
browser↔backend loop you already use with `scene.play()`.

```text
static host  →  index.html / JS / optional assets/
backend      →  /api/scene, /api/realtime, commands, recording
```

## Python API

```python
scene.export_web(
    "dist-web",
    api_base="http://127.0.0.1:8765",
    copy_assets=True,
    project_root=".",
)
```

## CLI

```bash
uv run sceneify export-web world.sceneify.json --out dist-web --api-base http://127.0.0.1:8765
```

Flags:

* `--no-copy-assets` — keep loading files through the backend `/api/asset`
* `--optimize-assets` — best-effort GLB rewrite when `trimesh` is installed
* `--project-root` — root used to resolve relative asset paths

## Output

* viewer files from the bundled Vite build (`src/sceneify/_web`)
* `sceneify.config.json` + inline `window.__SCENEIFY_CONFIG__` in `index.html`
* `scene.json` bootstrap document (live state still comes from the backend)
* optional `assets/` packed copies with remapped sources

## Runtime config

```json
{
  "apiBase": "http://127.0.0.1:8765",
  "sceneFile": "scene.json",
  "assetMode": "static"
}
```

* `apiBase` empty → same-origin (viewer served by the Python app itself)
* `assetMode: "static"` → prefer `/assets/...` from the static host
* `assetMode: "api"` → always use backend `/api/asset?path=...`

The backend already allows CORS (`*`), so a separate static origin can call it.

## Suggested workflow

1. Author/run the world with `scene.play(block=False)` (or your own serve loop)
2. Export the viewer: `scene.export_web("dist-web", api_base="https://api.example.com")`
3. Host `dist-web/` on any static server / CDN
4. Keep the Python process as the play/API backend
