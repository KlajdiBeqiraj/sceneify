"""Launch and manage isolated Sceneify example sessions."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx


@dataclass
class SceneSession:
    """A running Python example and its browser server."""

    id: str
    script: Path
    port: int
    process: subprocess.Popen[bytes]
    log_path: Path
    started_at: float

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def running(self) -> bool:
        return self.process.poll() is None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "script": str(self.script),
            "port": self.port,
            "url": self.url,
            "running": self.running,
            "logPath": str(self.log_path),
            "startedAt": self.started_at,
        }


class SessionManager:
    """Create, start, inspect, and stop local Python scene sessions."""

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.sessions: dict[str, SceneSession] = {}

    def create_example(self, name: str, *, title: str | None = None) -> Path:
        slug = _slug(name)
        path = self.project_root / "examples" / "mcp" / f"{slug}.py"
        if path.exists():
            raise ValueError(f"Example already exists: {path.relative_to(self.project_root)}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_example_template(title or name), encoding="utf-8")
        return path

    def start(
        self, script: str | Path, *, session_id: str | None = None, timeout: float = 10.0
    ) -> SceneSession:
        target = self._example_path(script)
        if not target.is_file():
            raise ValueError(f"Example script not found: {script}")
        identifier = session_id or _slug(target.stem)
        if identifier in self.sessions and self.sessions[identifier].running:
            raise ValueError(f"Session already running: {identifier}")
        port = _free_port()
        log_dir = self.project_root / ".sceneify_cache" / "sessions"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{identifier}.log"
        environment = {
            **os.environ,
            "SCENEIFY_HOST": "127.0.0.1",
            "SCENEIFY_PORT": str(port),
            "SCENEIFY_OPEN_BROWSER": "0",
        }
        with log_path.open("wb") as log:
            process = subprocess.Popen(
                [sys.executable, str(target)],
                cwd=self.project_root,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        session = SceneSession(identifier, target, port, process, log_path, time.time())
        self.sessions[identifier] = session
        self._wait_ready(session, timeout)
        return session

    def list(self) -> list[dict[str, object]]:
        return [session.to_dict() for session in self.sessions.values()]

    def get(self, session_id: str) -> SceneSession:
        try:
            return self.sessions[session_id]
        except KeyError as exc:
            raise ValueError(f"Unknown session: {session_id}") from exc

    def stop(self, session_id: str, *, timeout: float = 5.0) -> dict[str, object]:
        session = self.get(session_id)
        if session.running:
            os.killpg(session.process.pid, signal.SIGTERM)
            try:
                session.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(session.process.pid, signal.SIGKILL)
                session.process.wait()
        return session.to_dict()

    def _example_path(self, script: str | Path) -> Path:
        candidate = (self.project_root / script).resolve()
        allowed = (self.project_root / "examples" / "mcp").resolve()
        try:
            candidate.relative_to(allowed)
        except ValueError as exc:
            raise ValueError("Session scripts must be under examples/mcp") from exc
        return candidate

    def _wait_ready(self, session: SceneSession, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not session.running:
                raise RuntimeError(f"Session exited before becoming ready; see {session.log_path}")
            try:
                if httpx.get(f"{session.url}/api/health", timeout=0.25).is_success:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        self.stop(session.id)
        raise TimeoutError(f"Session did not become ready within {timeout} seconds")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _slug(value: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise ValueError("Example name must contain letters or numbers")
    return slug


def _example_template(title: str) -> str:
    return f'''"""Conversational MCP Sceneify example: {title}."""

from pathlib import Path

from sceneify import Material, Physics, Scene

# sceneify:scene-begin
def build_scene() -> Scene:
    scene = Scene({title!r}, background="#10131a")
    scene.create_primitive(
        "floor",
        "box",
        size=(8.0, 0.2, 8.0),
        position=(0.0, -0.1, 0.0),
        material=Material("#2b3344"),
        physics=Physics(body="fixed", collider="cuboid"),
    )
    return scene
# sceneify:scene-end


if __name__ == "__main__":
    build_scene().run(project_root=Path(__file__).parents[2])
'''
