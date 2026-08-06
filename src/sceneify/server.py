"""Local FastAPI server that serves scene JSON and the web viewer."""

from __future__ import annotations

import mimetypes
import threading
import time
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

if TYPE_CHECKING:
    from sceneify.scene import Scene

WEB_DIST = Path(__file__).resolve().parent.parent.parent / "web" / "dist"


def create_app(scene: Scene) -> FastAPI:
    app = FastAPI(title="sceneify", docs_url=None, redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "package": "sceneify"}

    @app.get("/api/scene")
    def get_scene() -> JSONResponse:
        return JSONResponse(scene.to_dict())

    @app.get("/api/asset")
    def get_asset(path: str) -> FileResponse:
        local = _resolve_local_asset(path)
        if local is None or not local.is_file():
            raise HTTPException(status_code=404, detail="Asset not found")
        mime, _ = mimetypes.guess_type(str(local))
        return FileResponse(local, media_type=mime or "application/octet-stream")

    if WEB_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="viewer")
    else:

        @app.get("/")
        def missing_frontend() -> JSONResponse:
            return JSONResponse(
                {
                    "message": (
                        "sceneify web viewer is not built yet. "
                        "Run `npm install && npm run build` inside web/, "
                        "or open /api/scene for the scene JSON."
                    ),
                    "scene": scene.to_dict(),
                }
            )

    return app


def serve_scene(
    scene: Scene,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    import uvicorn

    app = create_app(scene)
    url = f"http://{host}:{port}/"

    if open_browser:

        def _open() -> None:
            time.sleep(0.6)
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()

    print(f"sceneify serving {scene.name!r} at {url}")
    uvicorn.run(app, host=host, port=port, log_level="info")


def _resolve_local_asset(path: str) -> Path | None:
    raw = unquote(path)
    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"}:
        return None
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    try:
        candidate = candidate.resolve(strict=False)
    except OSError:
        return None
    return candidate
