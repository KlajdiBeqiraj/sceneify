"""Local FastAPI server that serves scene JSON and the web viewer."""

from __future__ import annotations

import mimetypes
import signal
import threading
import time
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from urllib.parse import unquote, urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from sceneify.scene import Scene

WEB_DIST = Path(__file__).resolve().parent.parent.parent / "web" / "dist"
StopMode = Literal["interrupt", "enter"]


class ServerHandle:
    """Handle for a running sceneify viewer server."""

    def __init__(self, server: object, thread: threading.Thread | None, url: str) -> None:
        self._server = server
        self._thread = thread
        self.url = url

    @property
    def running(self) -> bool:
        server = self._server
        started = getattr(server, "started", False)
        should_exit = getattr(server, "should_exit", True)
        return bool(started) and not bool(should_exit)

    def stop(self, timeout: float = 5.0) -> None:
        """Request shutdown and wait for the server thread to exit."""
        server = self._server
        if hasattr(server, "should_exit"):
            server.should_exit = True
        if hasattr(server, "force_exit"):
            server.force_exit = True
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def wait(self) -> None:
        """Block until the server thread finishes."""
        if self._thread is not None:
            self._thread.join()

    def __enter__(self) -> ServerHandle:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self.stop()


class NodePatch(BaseModel):
    position: list[float] | None = None
    rotation: list[float] | None = None
    scale: list[float] | None = None
    visible: bool | None = None
    apply_environment: bool = False


class SceneSaveRequest(BaseModel):
    path: str = Field(..., description="Absolute or cwd-relative path for the JSON scene file")


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

    @app.patch("/api/nodes/{node_id}")
    def patch_node(node_id: str, body: NodePatch) -> JSONResponse:
        try:
            updated = scene.update_node(
                node_id,
                position=body.position,
                rotation=body.rotation,
                scale=body.scale,
                visible=body.visible,
                apply_environment=body.apply_environment,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return JSONResponse({"node": updated, "scene": scene.to_dict()})

    @app.post("/api/scene/save")
    def save_scene_endpoint(body: SceneSaveRequest) -> JSONResponse:
        path = scene.save(body.path)
        return JSONResponse({"saved": str(path)})

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
    block: bool = True,
    stop_on: StopMode = "enter",
) -> ServerHandle:
    """Serve the scene viewer.

    Parameters
    ----------
    block:
        If True, keep the call occupied until the server stops.
        If False, return a ServerHandle immediately (background thread).
    stop_on:
        When block=True:
        - ``enter``: press Enter in the terminal to stop (best for demos)
        - ``interrupt``: stop with Ctrl+C
    """
    import uvicorn

    app = create_app(scene)
    url = f"http://{host}:{port}/"
    config = uvicorn.Config(app, host=host, port=port, log_level="warning", lifespan="off")
    server = uvicorn.Server(config)

    # Avoid uvicorn installing handlers that fight the demo "press Enter" loop.
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]

    if open_browser:

        def _open() -> None:
            time.sleep(0.6)
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()

    thread = threading.Thread(target=server.run, name="sceneify-server", daemon=True)
    thread.start()

    # Wait until the server is actually listening (or failed).
    deadline = time.time() + 5.0
    while time.time() < deadline and not server.started:
        if not thread.is_alive():
            break
        time.sleep(0.05)

    handle = ServerHandle(server=server, thread=thread, url=url)
    print(f"sceneify serving {scene.name!r} at {url}")

    if not block:
        print("Server runs in background. Call handle.stop() when finished.")
        return handle

    try:
        if stop_on == "enter":
            print("Press Enter to stop the server (Ctrl+C also works).")
            _wait_for_enter_or_interrupt(handle)
        else:
            print("Press Ctrl+C to stop the server.")
            _wait_for_interrupt(handle)
    finally:
        handle.stop()
        print("sceneify server stopped.")

    return handle


def _wait_for_enter_or_interrupt(handle: ServerHandle) -> None:
    stop_event = threading.Event()

    def _on_signal(signum, frame) -> None:  # type: ignore[no-untyped-def]
        stop_event.set()
        handle.stop(timeout=0.1)

    previous_int = signal.getsignal(signal.SIGINT)
    previous_term = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)
    try:

        def _read_enter() -> None:
            try:
                input()
            except EOFError:
                while handle.running and not stop_event.is_set():
                    time.sleep(0.2)
            finally:
                stop_event.set()

        reader = threading.Thread(target=_read_enter, name="sceneify-stop-reader", daemon=True)
        reader.start()
        while not stop_event.is_set():
            if not handle._thread or not handle._thread.is_alive():
                break
            time.sleep(0.1)
    finally:
        signal.signal(signal.SIGINT, previous_int)
        signal.signal(signal.SIGTERM, previous_term)


def _wait_for_interrupt(handle: ServerHandle) -> None:
    stop_event = threading.Event()

    def _on_signal(signum, frame) -> None:  # type: ignore[no-untyped-def]
        stop_event.set()
        handle.stop(timeout=0.1)

    previous_int = signal.getsignal(signal.SIGINT)
    previous_term = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)
    try:
        while not stop_event.is_set():
            if not handle._thread or not handle._thread.is_alive():
                break
            time.sleep(0.1)
    finally:
        signal.signal(signal.SIGINT, previous_int)
        signal.signal(signal.SIGTERM, previous_term)


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
