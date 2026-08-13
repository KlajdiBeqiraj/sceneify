"""Local FastAPI server that serves scene JSON and the web viewer."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import mimetypes
import os
import re
import shutil
import signal
import struct
import subprocess
import threading
import time
import uuid
import webbrowser
from collections.abc import Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal
from urllib.parse import unquote, urlparse

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sceneify.catalog import CATALOG_FORMAT, CATALOG_VERSION, AssetCatalog
from sceneify.commands import CommandStack, RevisionConflict
from sceneify.episode import Episode, EpisodeRecorder
from sceneify.realtime import InputEvent, SemanticEvent

if TYPE_CHECKING:
    from sceneify.scene import Scene

PACKAGE_WEB = Path(__file__).resolve().parent / "_web"
DEVELOPMENT_WEB = Path(__file__).resolve().parent.parent.parent / "web" / "dist"
WEB_DIST = PACKAGE_WEB if PACKAGE_WEB.is_dir() else DEVELOPMENT_WEB
StopMode = Literal["interrupt", "enter"]
PROTOCOL_NAME = "sceneify-realtime"
PROTOCOL_VERSION = 2
MAX_ASSET_UPLOAD_BYTES = 100 * 1024 * 1024
SUPPORTED_ASSET_SUFFIXES = {".glb", ".gltf", ".ply", ".obj", ".stl"}


class ServerHandle:
    """Handle for a running sceneify viewer server."""

    def __init__(
        self,
        server: object,
        thread: threading.Thread | None,
        url: str,
        *,
        app: FastAPI | None = None,
    ) -> None:
        self._server = server
        self._thread = thread
        self.url = url
        self._app = app

    @property
    def running(self) -> bool:
        server = self._server
        started = getattr(server, "started", False)
        should_exit = getattr(server, "should_exit", True)
        return bool(started) and not bool(should_exit)

    def _runtime(self) -> RealtimeRuntime:
        if self._app is None:
            raise RuntimeError("ServerHandle has no app reference for recording/replay")
        runtime = getattr(self._app.state, "realtime", None)
        if not isinstance(runtime, RealtimeRuntime):
            raise RuntimeError("Realtime runtime is not available")
        return runtime

    def start_recording(
        self, *, episode_id: str | None = None, meta: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Start capturing browser input and semantic events into an episode."""
        return self._runtime().start_recording(episode_id=episode_id, meta=meta)

    def stop_recording(self) -> Episode:
        """Stop recording and return the finished episode."""
        return self._runtime().stop_recording()

    def replay(self, episode: Episode | dict[str, Any] | str | Path) -> dict[str, Any]:
        """Replay a recorded episode into connected browsers."""
        return self._runtime().start_replay(episode)

    def stop_replay(self) -> None:
        """Cancel an in-progress episode replay."""
        self._runtime().stop_replay()

    def stop(self, timeout: float = 5.0) -> None:
        """Request shutdown and wait for the server thread to exit."""
        server = self._server
        if hasattr(server, "should_exit"):
            server.should_exit = True
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        if self._thread is not None and self._thread.is_alive():
            if hasattr(server, "force_exit"):
                server.force_exit = True
            self._thread.join(timeout=1.0)

    def wait(self) -> None:
        """Block until the server thread finishes."""
        if self._thread is not None:
            self._thread.join()

    def __enter__(self) -> ServerHandle:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self.stop()


class NodePatch(BaseModel):
    model_config = {"extra": "allow", "populate_by_name": True}

    position: list[float] | None = None
    rotation: list[float] | None = None
    scale: list[float] | None = None
    visible: bool | None = None
    apply_environment: bool = False
    expected_revision: int | None = Field(default=None, alias="expectedRevision")
    revision: int | None = None


class SceneSaveRequest(BaseModel):
    path: str = Field(..., description="Project-root-relative path for the JSON scene file")
    expected_revision: int | None = Field(default=None, alias="expectedRevision")
    revision: int | None = None


class SceneSavePythonRequest(BaseModel):
    path: str = Field(..., description="Project-root-relative path for the Python authoring script")
    mode: str = Field(default="auto", description="markers | ast | auto")
    expected_revision: int | None = Field(default=None, alias="expectedRevision")
    revision: int | None = None


class EpisodeRecordStartRequest(BaseModel):
    episode_id: str | None = Field(default=None, alias="episodeId")
    meta: dict[str, Any] = Field(default_factory=dict)


class EpisodeReplayRequest(BaseModel):
    model_config = {"extra": "allow"}

    episode: dict[str, Any] | None = None
    path: str | None = None


class EditorCommand(BaseModel):
    model_config = {"extra": "allow"}

    action: str
    expected_revision: int | None = Field(default=None, alias="expectedRevision")


class RealtimeRuntime:
    """One shared tick loop and connection registry for a scene."""

    def __init__(
        self,
        scene: Scene,
        *,
        tick_rate: float = 60.0,
        enabled: bool = True,
        commands: CommandStack | None = None,
    ) -> None:
        if tick_rate <= 0:
            raise ValueError("tick_rate must be greater than zero")
        self.scene = scene
        self.tick_rate = float(tick_rate)
        self.enabled = enabled
        self.commands = commands or CommandStack(scene)
        self.sequence = 0
        self.last_error: Exception | None = None
        self._clients: dict[str, WebSocket] = {}
        self._task: asyncio.Task[None] | None = None
        self._started_at = 0.0
        self._recorder: EpisodeRecorder | None = None
        self._replay_task: asyncio.Task[None] | None = None
        self._last_episode: Episode | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._last_transforms: dict[str, tuple[tuple[float, float, float], ...]] | None = None
        self._last_frame_revision: int | None = None
        self._capture_waiters: dict[str, asyncio.Future[dict[str, Any]]] = {}

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        if not self.enabled or self._task is not None:
            return
        self._started_at = time.perf_counter()
        self._task = asyncio.create_task(self._tick_loop(), name="sceneify-realtime-tick")

    async def stop(self) -> None:
        self.stop_replay()
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        clients, self._clients = list(self._clients.values()), {}
        for websocket in clients:
            with contextlib.suppress(Exception):
                await websocket.close(code=1001, reason="Server shutdown")

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        client_id = uuid.uuid4().hex
        self._clients[client_id] = websocket
        # New subscribers need a full pose overlay on the next tick.
        self.invalidate_frame_cache()
        await websocket.send_json(
            {
                "type": "hello",
                "protocol": PROTOCOL_NAME,
                "version": PROTOCOL_VERSION,
                "capabilities": [
                    "snapshot",
                    "commands",
                    "undoRedo",
                    "semanticEvents",
                    "inputV1",
                    "frameV1",
                    "frameDelta",
                    "recording",
                    "replay",
                    "sourceSync",
                    "capture",
                ],
                "clientId": client_id,
                "tickRate": self.tick_rate,
                "mode": "play" if self.enabled else "edit",
                "revision": self.commands.revision,
                "recording": self._recorder is not None,
                "replaying": self._replay_task is not None and not self._replay_task.done(),
                "scene": self.scene.to_dict(),
            }
        )
        return client_id

    def disconnect(self, client_id: str) -> None:
        self._clients.pop(client_id, None)

    def start_recording(
        self, *, episode_id: str | None = None, meta: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if self._recorder is not None:
            raise ValueError("Recording is already active")
        if self._replay_task is not None and not self._replay_task.done():
            raise ValueError("Cannot record while replay is active")
        self._recorder = EpisodeRecorder(
            scene_name=self.scene.name,
            tick_rate=self.tick_rate,
            episode_id=episode_id,
            meta=meta,
        )
        self._recorder.start_clock(time.perf_counter())
        status = {
            "recording": True,
            "episodeId": self._recorder.episode.id,
            "sceneName": self.scene.name,
        }
        self._schedule(self._broadcast({"type": "record_state", **status}))
        return status

    def stop_recording(self) -> Episode:
        if self._recorder is None:
            raise ValueError("Recording is not active")
        episode = self._recorder.finish(time.perf_counter())
        self._recorder = None
        self._last_episode = episode
        self._schedule(
            self._broadcast(
                {
                    "type": "record_state",
                    "recording": False,
                    "episodeId": episode.id,
                    "duration": episode.duration,
                }
            )
        )
        return episode

    def start_replay(self, episode: Episode | dict[str, Any] | str | Path) -> dict[str, Any]:
        resolved = _coerce_episode(episode)
        if self._recorder is not None:
            raise ValueError("Cannot replay while recording is active")
        self.stop_replay()
        if self._loop is None:
            raise RuntimeError("Realtime runtime is not started")
        self._replay_task = self._loop.create_task(
            self._run_replay(resolved), name="sceneify-episode-replay"
        )
        return {
            "replaying": True,
            "episodeId": resolved.id,
            "duration": resolved.duration,
            "eventCount": len(resolved.events),
        }

    def stop_replay(self) -> None:
        task, self._replay_task = self._replay_task, None
        if task is not None and not task.done():
            task.cancel()
            self._schedule(self._broadcast({"type": "replay_control", "action": "stop"}))

    def recording_status(self) -> dict[str, Any]:
        recorder = self._recorder
        replaying = self._replay_task is not None and not self._replay_task.done()
        return {
            "recording": recorder is not None,
            "replaying": replaying,
            "episodeId": recorder.episode.id if recorder else None,
            "lastEpisodeId": self._last_episode.id if self._last_episode else None,
        }

    async def receive(self, client_id: str, message: Any) -> None:
        websocket = self._clients[client_id]
        if not isinstance(message, dict):
            await self._send_error(websocket, "Message must be a JSON object")
            return
        message_type = message.get("type")
        if message_type == "ping":
            await websocket.send_json(
                {
                    "type": "ping",
                    "timestamp": message.get("timestamp"),
                    "reply": True,
                }
            )
            return
        if message_type == "resync":
            await websocket.send_json(self.commands.snapshot())
            return
        if message_type == "command":
            await self._receive_command(websocket, message)
            return
        if message_type in {"event", "semantic_event"}:
            await self._receive_semantic_event(client_id, websocket, message)
            return
        if message_type == "record_control":
            await self._receive_record_control(websocket, message)
            return
        if message_type == "capture_result":
            await self._receive_capture_result(message)
            return
        if message_type != "input":
            await self._send_error(
                websocket,
                "Expected input, semantic_event, command, resync, record_control, "
                "capture_result, or ping",
            )
            return
        action = message.get("action")
        if not isinstance(action, str) or not action:
            await self._send_error(websocket, "Input action must be a nonempty string")
            return
        metadata = message.get("metadata", {})
        if not isinstance(metadata, dict):
            await self._send_error(websocket, "Input metadata must be an object")
            return
        if metadata.get("replay"):
            return
        if self._recorder is not None:
            self._recorder.record_input(
                time.perf_counter(),
                action,
                value=message.get("value"),
                metadata=metadata,
            )
        event = InputEvent(
            action=action,
            value=message.get("value"),
            client_id=client_id,
            metadata=metadata,
        )
        callbacks = tuple(self.scene._input_callbacks)
        try:
            for callback in callbacks:
                result = callback(self.scene, event)
                if inspect.isawaitable(result):
                    await result
        except Exception as exc:
            self.last_error = exc
            await self._send_error(websocket, f"Input callback failed: {exc}")
            return
        if callbacks:
            await self._broadcast_frame()

    async def _receive_record_control(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        action = message.get("action")
        try:
            if action == "start":
                status = self.start_recording(
                    episode_id=message.get("episodeId"),
                    meta=message.get("meta") if isinstance(message.get("meta"), dict) else None,
                )
                await websocket.send_json({"type": "record_ack", **status})
                return
            if action == "stop":
                episode = self.stop_recording()
                await websocket.send_json(
                    {
                        "type": "record_ack",
                        "recording": False,
                        "episode": episode.to_document(),
                    }
                )
                return
        except ValueError as exc:
            await self._send_error(websocket, str(exc))
            return
        await self._send_error(websocket, "record_control action must be start or stop")

    async def _run_replay(self, episode: Episode) -> None:
        await self._broadcast(
            {
                "type": "replay_control",
                "action": "start",
                "episodeId": episode.id,
                "duration": episode.duration,
                "eventCount": len(episode.events),
            }
        )
        started = time.perf_counter()
        try:
            for event in episode.events:
                delay = event.t - (time.perf_counter() - started)
                if delay > 0:
                    await asyncio.sleep(delay)
                if event.kind == "input":
                    await self._broadcast(
                        {
                            "type": "replay_input",
                            "t": event.t,
                            "action": event.action,
                            "value": event.value,
                            "metadata": {**event.metadata, "replay": True},
                        }
                    )
                elif event.kind == "marker" and event.name == "end":
                    break
            await self._broadcast(
                {
                    "type": "replay_control",
                    "action": "complete",
                    "episodeId": episode.id,
                    "duration": episode.duration,
                }
            )
        except asyncio.CancelledError:
            await self._broadcast(
                {"type": "replay_control", "action": "stop", "episodeId": episode.id}
            )
            raise
        finally:
            self._replay_task = None

    def _schedule(self, awaitable: Any) -> None:
        if self._loop is None or not self._loop.is_running():
            return
        self._loop.create_task(awaitable)

    async def _receive_command(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        command = message.get("command")
        if not isinstance(command, dict):
            await self._send_error(websocket, "command must be an object")
            return
        try:
            action = command.get("action")
            expected = message.get("revision", command.get("expectedRevision"))
            if action == "undo":
                ack = self.commands.undo(expected_revision=expected)
            elif action == "redo":
                ack = self.commands.redo(expected_revision=expected)
            else:
                ack = self.commands.execute(command, expected_revision=expected)
        except RevisionConflict:
            await websocket.send_json(
                {
                    "type": "resync",
                    "revision": self.commands.revision,
                    "scene": self.scene.to_dict(),
                }
            )
            return
        except (KeyError, TypeError, ValueError) as exc:
            await self._send_error(websocket, str(exc))
            return
        await self._broadcast(ack)

    async def _receive_semantic_event(
        self,
        client_id: str,
        websocket: WebSocket,
        message: dict[str, Any],
    ) -> None:
        name = message.get("name", message.get("event"))
        data = message.get("data", {})
        if not isinstance(name, str) or not name:
            await self._send_error(websocket, "Semantic event name must be nonempty")
            return
        if not isinstance(data, dict):
            await self._send_error(websocket, "Semantic event data must be an object")
            return
        if self._recorder is not None:
            self._recorder.record_semantic(
                time.perf_counter(),
                name,
                node_id=message.get("nodeId"),
                value=message.get("value"),
                data=data,
            )
        event = SemanticEvent(
            name=name,
            node_id=message.get("nodeId"),
            value=message.get("value"),
            client_id=client_id,
            data=data,
        )
        callbacks = tuple(self.scene._event_callbacks)
        try:
            for callback in callbacks:
                result = callback(self.scene, event)
                if inspect.isawaitable(result):
                    await result
        except Exception as exc:
            self.last_error = exc
            await self._send_error(websocket, f"Event callback failed: {exc}")
            return
        await websocket.send_json({"type": "event_ack", "name": name})

    async def _tick_loop(self) -> None:
        interval = 1.0 / self.tick_rate
        previous = time.perf_counter()
        next_tick = previous
        while True:
            now = time.perf_counter()
            delta = now - previous
            previous = now
            callbacks = tuple(self.scene._tick_callbacks)
            try:
                for callback in callbacks:
                    result = callback(self.scene, delta)
                    if inspect.isawaitable(result):
                        await result
            except Exception as exc:
                self.last_error = exc
            if callbacks:
                await self._broadcast_frame(now=now, delta=delta)
            next_tick += interval
            await asyncio.sleep(max(0.0, next_tick - time.perf_counter()))

    async def _broadcast_frame(self, *, now: float | None = None, delta: float = 0.0) -> None:
        timestamp = time.perf_counter() if now is None else now
        revision = self.commands.revision
        force_full = (
            self._last_transforms is None
            or self._last_frame_revision is None
            or revision != self._last_frame_revision
        )
        transforms, current, full = self.scene.transforms_delta(
            previous=self._last_transforms,
            force_full=force_full,
        )
        # Quiet ticks with no pose changes do not need a network payload.
        if not full and not transforms:
            self.sequence += 1
            return
        self.sequence += 1
        if not self._clients:
            return
        # Only advance the dirty cache after a frame is actually delivered.
        self._last_transforms = current
        self._last_frame_revision = revision
        await self._broadcast(
            {
                "type": "frame",
                "sequence": self.sequence,
                "time": timestamp - self._started_at,
                "delta": delta,
                "revision": revision,
                "full": full,
                "transforms": transforms,
            }
        )

    def invalidate_frame_cache(self) -> None:
        """Force the next frame to send a full transform snapshot."""
        self._last_transforms = None
        self._last_frame_revision = None

    async def request_capture(self, options: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Ask a connected browser to capture the WebGL canvas and wait for PNG data."""
        if not self._clients:
            raise RuntimeError("No connected viewer available for capture")
        request_id = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._capture_waiters[request_id] = future
        payload = {
            "type": "capture_request",
            "requestId": request_id,
            **(dict(options) if options else {}),
        }
        try:
            await self._broadcast(payload)
            return await asyncio.wait_for(future, timeout=15.0)
        except TimeoutError as exc:
            raise RuntimeError("Timed out waiting for viewer capture") from exc
        finally:
            self._capture_waiters.pop(request_id, None)

    async def _receive_capture_result(self, message: dict[str, Any]) -> None:
        request_id = message.get("requestId")
        if not isinstance(request_id, str) or request_id not in self._capture_waiters:
            return
        future = self._capture_waiters[request_id]
        if future.done():
            return
        if message.get("ok") is False:
            future.set_exception(RuntimeError(str(message.get("error") or "Capture failed")))
            return
        image = message.get("image")
        if not isinstance(image, str) or not image:
            future.set_exception(RuntimeError("Capture result missing image data"))
            return
        future.set_result(
            {
                "requestId": request_id,
                "mimeType": message.get("mimeType") or "image/png",
                "image": image,
                "width": message.get("width"),
                "height": message.get("height"),
                "camera": message.get("camera"),
                "preset": message.get("preset"),
            }
        )

    async def _broadcast(self, message: dict[str, Any]) -> None:
        if message.get("type") in {"command_ack", "snapshot", "resync"}:
            self.invalidate_frame_cache()
        if not self._clients:
            return
        clients = tuple(self._clients.items())
        results = await asyncio.gather(
            *(websocket.send_json(message) for _, websocket in clients),
            return_exceptions=True,
        )
        for (client_id, _), result in zip(clients, results, strict=True):
            if isinstance(result, Exception):
                self.disconnect(client_id)

    @staticmethod
    async def _send_error(websocket: WebSocket, detail: str) -> None:
        await websocket.send_json({"type": "error", "detail": detail})


def create_app(
    scene: Scene,
    *,
    realtime: bool = True,
    tick_rate: float = 60.0,
    project_root: str | Path | None = None,
) -> FastAPI:
    root = Path.cwd() if project_root is None else Path(project_root)
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    commands = CommandStack(scene)
    runtime = RealtimeRuntime(scene, tick_rate=tick_rate, enabled=realtime, commands=commands)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await runtime.start()
        try:
            yield
        finally:
            await runtime.stop()

    app = FastAPI(title="sceneify", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.realtime = runtime
    app.state.commands = commands
    app.state.project_root = root
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
        return JSONResponse({**scene.to_dict(), "revision": commands.revision})


    @app.post("/api/scene/capture")
    async def capture_scene(body: dict[str, Any] | None = None) -> JSONResponse:
        options = body or {}
        try:
            result = await runtime.request_capture(options)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return JSONResponse(result)

    @app.get("/api/scene/snapshot")
    def get_snapshot() -> JSONResponse:
        return JSONResponse(commands.snapshot())

    @app.websocket("/ws")
    @app.websocket("/api/realtime")
    async def realtime_socket(websocket: WebSocket) -> None:
        client_id = await runtime.connect(websocket)
        try:
            while True:
                await runtime.receive(client_id, await websocket.receive_json())
        except WebSocketDisconnect:
            pass
        finally:
            runtime.disconnect(client_id)

    @app.patch("/api/nodes/{node_id}")
    async def patch_node(node_id: str, body: NodePatch) -> JSONResponse:
        try:
            patch = body.model_dump(
                exclude={"apply_environment", "expected_revision", "revision"},
                exclude_unset=True,
                by_alias=True,
            )
            patch.update(body.model_extra or {})
            ack = commands.execute(
                {"action": "patch", "id": node_id, "patch": patch},
                expected_revision=(
                    body.expected_revision if body.expected_revision is not None else body.revision
                ),
            )
            await runtime._broadcast(ack)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RevisionConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={"message": str(exc), **commands.snapshot()},
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return JSONResponse(ack)

    @app.post("/api/nodes/primitives")
    async def create_primitive(body: dict[str, Any]) -> JSONResponse:
        return await _execute_http_command({"action": "create", "node": body}, body)

    @app.post("/api/nodes/{node_id}/duplicate")
    async def duplicate_node(node_id: str, body: dict[str, Any] | None = None) -> JSONResponse:
        values = body or {}
        return await _execute_http_command(
            {
                "action": "duplicate",
                "id": node_id,
                "newId": values.get("newId"),
                "parentId": values.get("parentId"),
            },
            values,
        )

    @app.delete("/api/nodes/{node_id}")
    async def delete_node(node_id: str, expectedRevision: int | None = None) -> JSONResponse:
        return await _execute_http_command(
            {"action": "delete", "id": node_id},
            {"expectedRevision": expectedRevision},
        )

    @app.post("/api/nodes/{node_id}/reparent")
    async def reparent_node(node_id: str, body: dict[str, Any]) -> JSONResponse:
        return await _execute_http_command(
            {"action": "reparent", "id": node_id, "parentId": body.get("parentId")},
            body,
        )

    @app.post("/api/commands")
    async def execute_command(body: dict[str, Any]) -> JSONResponse:
        action = body.get("action")
        if action in {"undo", "redo"}:
            return await _undo_redo(str(action), body.get("expectedRevision"))
        return await _execute_http_command(body, body)

    @app.post("/api/scene/commands")
    async def execute_legacy_command(body: dict[str, Any]) -> JSONResponse:
        action = body.get("action", body.get("command"))
        if action in {"undo", "redo"}:
            return await _undo_redo(str(action), _body_revision(body))
        command = {**body, "action": action}
        return await _execute_http_command(command, body)

    @app.post("/api/commands/undo")
    async def undo_command(body: dict[str, Any] | None = None) -> JSONResponse:
        return await _undo_redo("undo", (body or {}).get("expectedRevision"))

    @app.post("/api/commands/redo")
    async def redo_command(body: dict[str, Any] | None = None) -> JSONResponse:
        return await _undo_redo("redo", (body or {}).get("expectedRevision"))

    async def _execute_http_command(
        command: dict[str, Any], envelope: dict[str, Any]
    ) -> JSONResponse:
        try:
            ack = commands.execute(
                command,
                expected_revision=_body_revision(envelope),
            )
        except RevisionConflict as exc:
            raise HTTPException(
                status_code=409, detail={"message": str(exc), **commands.snapshot()}
            ) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await runtime._broadcast(ack)
        return JSONResponse(ack)

    async def _undo_redo(action: str, expected_revision: int | None) -> JSONResponse:
        try:
            operation = commands.undo if action == "undo" else commands.redo
            ack = operation(expected_revision=expected_revision)
        except RevisionConflict as exc:
            raise HTTPException(
                status_code=409, detail={"message": str(exc), **commands.snapshot()}
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await runtime._broadcast(ack)
        return JSONResponse(ack)

    @app.get("/api/episode/status")
    def episode_status() -> JSONResponse:
        return JSONResponse(runtime.recording_status())

    @app.post("/api/episode/record/start")
    def episode_record_start(body: EpisodeRecordStartRequest | None = None) -> JSONResponse:
        payload = body or EpisodeRecordStartRequest()
        try:
            return JSONResponse(
                runtime.start_recording(episode_id=payload.episode_id, meta=payload.meta)
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/episode/record/stop")
    def episode_record_stop() -> JSONResponse:
        try:
            episode = runtime.stop_recording()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return JSONResponse(episode.to_document())

    @app.post("/api/episode/replay")
    def episode_replay(body: EpisodeReplayRequest) -> JSONResponse:
        try:
            if body.path:
                target = _confined_path(root, body.path)
                if not target.is_file():
                    raise ValueError(f"Episode file not found: {body.path}")
                status = runtime.start_replay(target)
            elif body.episode is not None:
                status = runtime.start_replay(body.episode)
            else:
                raise ValueError("replay requires episode or path")
        except (OSError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return JSONResponse(status)

    @app.post("/api/episode/replay/stop")
    def episode_replay_stop() -> JSONResponse:
        runtime.stop_replay()
        return JSONResponse({"replaying": False})

    @app.post("/api/scene/save")
    def save_scene_endpoint(body: SceneSaveRequest) -> JSONResponse:
        expected = body.expected_revision if body.expected_revision is not None else body.revision
        try:
            commands.check_revision(expected)
        except RevisionConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={"message": str(exc), **commands.snapshot()},
            ) from exc
        target = _confined_path(root, body.path)
        path = scene.save(target)
        return JSONResponse({"saved": str(path), "revision": commands.revision})

    @app.get("/api/scene/source-sync")
    def get_source_sync(path: str = "world.py") -> JSONResponse:
        from sceneify.source_sync import source_sync_report

        target = _confined_path(root, path)
        report = source_sync_report(path=target)
        return JSONResponse(report.to_dict())

    @app.post("/api/scene/save-python")
    def save_python_endpoint(body: SceneSavePythonRequest) -> JSONResponse:
        from sceneify.source_sync import save_python

        expected = body.expected_revision if body.expected_revision is not None else body.revision
        try:
            commands.check_revision(expected)
        except RevisionConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={"message": str(exc), **commands.snapshot()},
            ) from exc
        if body.mode not in {"auto", "markers", "ast"}:
            raise HTTPException(status_code=400, detail="mode must be auto, markers, or ast")
        target = _confined_path(root, body.path)
        if target.suffix.lower() != ".py":
            raise HTTPException(status_code=400, detail="Python save path must end with .py")
        path, report = save_python(scene, target, mode=body.mode)  # type: ignore[arg-type]
        return JSONResponse(
            {"saved": str(path), "revision": commands.revision, "sync": report.to_dict()}
        )

    @app.get("/api/asset")
    def get_asset(path: str) -> FileResponse:
        local = _resolve_local_asset(path, root)
        if local is None or not local.is_file():
            raise HTTPException(status_code=404, detail="Asset not found")
        mime, _ = mimetypes.guess_type(str(local))
        return FileResponse(local, media_type=mime or "application/octet-stream")

    @app.get("/api/assets/catalog")
    def asset_catalog(
        q: str = "",
        tag: Annotated[list[str] | None, Query()] = None,
    ) -> dict[str, Any]:
        assets = _filter_assets(_project_assets(root), q=q, tags=tag or [])
        return {
            "format": CATALOG_FORMAT,
            "version": CATALOG_VERSION,
            "assets": assets,
        }

    @app.get("/api/assets")
    def assets(
        q: str = "",
        tag: Annotated[list[str] | None, Query()] = None,
    ) -> list[dict[str, Any]]:
        return _filter_assets(_project_assets(root), q=q, tags=tag or [])

    @app.post("/api/assets/upload")
    async def upload_asset(file: Annotated[UploadFile, File()]) -> JSONResponse:
        return JSONResponse({"asset": await _store_upload(file, require_glb=False)})

    @app.post("/api/assets/import-glb")
    async def import_glb(
        file: Annotated[UploadFile, File()],
        revision: Annotated[int | None, Form()] = None,
    ) -> JSONResponse:
        _check_http_revision(commands, revision)
        return JSONResponse({"asset": await _store_upload(file, require_glb=True)})

    @app.post("/api/assets/import")
    async def import_asset(
        file: Annotated[UploadFile, File()],
        revision: Annotated[int | None, Form()] = None,
    ) -> JSONResponse:
        _check_http_revision(commands, revision)
        asset = await _store_upload(file, require_glb=True)
        node_id = scene._available_id(str(asset["id"]))
        try:
            ack = commands.execute(
                {
                    "action": "create",
                    "kind": "mesh",
                    "id": node_id,
                    "source": asset["path"],
                    "format": "glb",
                },
                expected_revision=revision,
            )
        except RevisionConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={"message": str(exc), **commands.snapshot()},
            ) from exc
        await runtime._broadcast(ack)
        return JSONResponse({**ack, "asset": asset})

    async def _store_upload(file: UploadFile, *, require_glb: bool) -> dict[str, Any]:
        filename = _safe_filename(file.filename or "asset.glb")
        if require_glb and Path(filename).suffix.lower() != ".glb":
            raise HTTPException(status_code=400, detail="GLB import requires a .glb file")
        assets_root = root / "assets"
        assets_root.mkdir(parents=True, exist_ok=True)
        data = await file.read(MAX_ASSET_UPLOAD_BYTES + 1)
        if len(data) > MAX_ASSET_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Asset exceeds the 100 MiB upload limit")
        if require_glb:
            _validate_glb(data)
        target = _unique_upload_path(root, filename)
        target.write_bytes(data)
        compressed = _maybe_draco_compress(target) if require_glb else False
        return {
            "id": target.stem,
            "name": target.stem,
            "path": target.relative_to(root).as_posix(),
            "source": target.relative_to(root).as_posix(),
            "format": target.suffix.lower().lstrip("."),
            "byteSize": target.stat().st_size,
            "animations": [],
            "tags": [],
            "metadata": {"draco": compressed} if compressed else {},
        }

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
    realtime: bool = False,
    tick_rate: float = 60.0,
    project_root: str | Path | None = None,
) -> ServerHandle:
    """Serve the scene viewer.

    If block is true, the call remains occupied until the server stops. Otherwise it returns a
    ServerHandle immediately. The stop_on value can be ``enter`` for terminal demos or
    ``interrupt`` for Ctrl+C handling.
    """
    import uvicorn

    app = create_app(
        scene,
        realtime=realtime,
        tick_rate=tick_rate,
        project_root=project_root,
    )
    url = f"http://{host}:{port}/"
    config = uvicorn.Config(app, host=host, port=port, log_level="warning", lifespan="on")
    server = uvicorn.Server(config)

    # Keep signal handling owned by the blocking terminal loop.
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]

    if open_browser:

        def _open() -> None:
            time.sleep(0.6)
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()

    thread = threading.Thread(target=server.run, name="sceneify-server", daemon=True)
    thread.start()

    # Wait until the server is listening or has failed.
    deadline = time.time() + 5.0
    while time.time() < deadline and not server.started:
        if not thread.is_alive():
            break
        time.sleep(0.05)

    handle = ServerHandle(server=server, thread=thread, url=url, app=app)
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


def _resolve_local_asset(path: str, project_root: Path | None = None) -> Path | None:
    raw = unquote(path)
    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"}:
        return None
    candidate = Path(raw).expanduser()
    try:
        root = (project_root or Path.cwd()).resolve()
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.resolve(strict=False)
        candidate.relative_to(root)
    except OSError:
        return None
    except ValueError:
        return None
    return candidate


def _project_assets(project_root: Path) -> list[dict[str, Any]]:
    catalog_path = project_root / "assets.catalog.json"
    if catalog_path.is_file():
        try:
            catalog = AssetCatalog.load(catalog_path)
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid asset catalog: {exc}") from exc
        return [
            _catalog_asset_payload(asset.to_document(), project_root) for asset in catalog.assets
        ]

    assets_root = project_root / "assets"
    if not assets_root.is_dir():
        return []
    return [
        {
            "id": item.relative_to(assets_root).with_suffix("").as_posix(),
            "name": item.stem,
            "path": item.relative_to(project_root).as_posix(),
            "source": item.relative_to(project_root).as_posix(),
            "format": item.suffix.lower().lstrip("."),
            "byteSize": item.stat().st_size,
            "animations": [],
            "tags": [],
            "metadata": {},
        }
        for item in sorted(assets_root.rglob("*"))
        if item.is_file() and item.suffix.lower() in SUPPORTED_ASSET_SUFFIXES
    ]


def _catalog_asset_payload(asset: dict[str, Any], project_root: Path) -> dict[str, Any]:
    payload = dict(asset)
    path = payload.get("path")
    if isinstance(path, str):
        payload["path"] = path if _is_web_url(path) else _catalog_local_path(path, project_root)

    source = payload.get("source")
    if isinstance(source, str):
        payload["source"] = (
            source if _is_web_url(source) else _catalog_local_path(source, project_root)
        )
    elif isinstance(payload.get("path"), str):
        payload["source"] = payload["path"]

    thumbnail = payload.get("thumbnail")
    if isinstance(thumbnail, str) and not _is_web_url(thumbnail):
        payload["thumbnail"] = _catalog_local_path(thumbnail, project_root)

    location = payload.get("path") or payload.get("source") or payload["id"]
    payload["name"] = Path(urlparse(str(location)).path).stem or payload["id"]
    return payload


def _catalog_local_path(value: str, project_root: Path) -> str:
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        raise HTTPException(status_code=400, detail="Catalog local path must be project-relative")
    local = _resolve_local_asset(value, project_root)
    if local is None:
        raise HTTPException(status_code=400, detail="Catalog path escapes project root")
    return local.relative_to(project_root).as_posix()


def _is_web_url(value: str) -> bool:
    return urlparse(value).scheme.lower() in {"http", "https"}


def _filter_assets(
    assets: list[dict[str, Any]],
    *,
    q: str,
    tags: list[str],
) -> list[dict[str, Any]]:
    query = q.strip().casefold()
    requested_tags = {item.strip().casefold() for item in tags if item.strip()}
    filtered: list[dict[str, Any]] = []
    for asset in assets:
        asset_tags = {
            str(item).casefold() for item in asset.get("tags", []) if isinstance(item, str)
        }
        searchable = " ".join(
            str(asset.get(key, "")) for key in ("id", "name", "path", "source", "format")
        ).casefold()
        if query and query not in searchable and not any(query in item for item in asset_tags):
            continue
        if requested_tags and not requested_tags.issubset(asset_tags):
            continue
        filtered.append(asset)
    return filtered


def _unique_upload_path(project_root: Path, filename: str) -> Path:
    candidate = _confined_path(project_root, f"assets/{filename}")
    if not candidate.exists():
        return candidate
    source = Path(filename)
    index = 1
    while True:
        candidate = _confined_path(
            project_root,
            f"assets/{source.stem}-{index}{source.suffix}",
        )
        if not candidate.exists():
            return candidate
        index += 1


def _validate_glb(data: bytes) -> None:
    if len(data) < 12:
        raise HTTPException(status_code=400, detail="Invalid GLB: header is truncated")
    magic, version, declared_length = struct.unpack_from("<4sII", data)
    if magic != b"glTF" or version != 2 or declared_length != len(data):
        raise HTTPException(status_code=400, detail="Invalid GLB binary header")


def _maybe_draco_compress(path: Path) -> bool:
    """Optionally recompress a GLB with Draco when SCENEIFY_DRACO=1 and npx is available."""
    if os.environ.get("SCENEIFY_DRACO", "").strip() not in {"1", "true", "yes"}:
        return False
    if path.suffix.lower() != ".glb":
        return False
    if shutil.which("npx") is None:
        return False
    output = path.with_suffix(".draco.glb")
    try:
        subprocess.run(
            [
                "npx",
                "--yes",
                "@gltf-transform/cli",
                "optimize",
                str(path),
                str(output),
                "--compress",
                "draco",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        with contextlib.suppress(OSError):
            output.unlink(missing_ok=True)
        return False
    if not output.is_file() or output.stat().st_size <= 0:
        return False
    output.replace(path)
    return True


def _coerce_episode(value: Episode | dict[str, Any] | str | Path) -> Episode:
    if isinstance(value, Episode):
        return value
    if isinstance(value, (str, Path)):
        return Episode.load(value)
    if not isinstance(value, dict):
        raise ValueError("Episode must be an Episode, mapping, or file path")
    if value.get("format") == "sceneify-episode" or "episode" in value:
        return Episode.from_document(value)
    return Episode.from_dict(value)


def _confined_path(project_root: Path, value: str | Path) -> Path:
    raw = Path(value).expanduser()
    candidate = raw if raw.is_absolute() else project_root / raw
    candidate = candidate.resolve(strict=False)
    try:
        candidate.relative_to(project_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Path escapes project root") from exc
    return candidate


def _safe_filename(value: str) -> str:
    name = Path(value.replace("\\", "/")).name
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    if not safe:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return safe


def _body_revision(body: dict[str, Any]) -> int | None:
    value = body.get("expectedRevision", body.get("revision"))
    if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
        raise HTTPException(status_code=400, detail="revision must be an integer")
    return value


def _check_http_revision(commands: CommandStack, revision: int | None) -> None:
    try:
        commands.check_revision(revision)
    except RevisionConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": str(exc), **commands.snapshot()},
        ) from exc
