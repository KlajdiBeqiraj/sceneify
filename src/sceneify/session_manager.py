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

    def scaffold(
        self,
        family: str,
        *,
        name: str | None = None,
        title: str | None = None,
    ) -> Path:
        """Write a playable shell for present, character, or board."""
        normalized = (family or "").strip().lower()
        if normalized not in {"present", "character", "board"}:
            raise ValueError("scaffold family must be 'present', 'character', or 'board'")
        slug = _slug(name or title or normalized)
        path = self.project_root / "examples" / "mcp" / f"{slug}.py"
        if path.exists():
            raise ValueError(f"Example already exists: {path.relative_to(self.project_root)}")
        path.parent.mkdir(parents=True, exist_ok=True)
        heading = title or name or normalized.replace("_", " ").title()
        path.write_text(_scaffold_template(normalized, heading), encoding="utf-8")
        return path

    def create_example(
        self, name: str, *, title: str | None = None, kind: str = "world"
    ) -> Path:
        slug = _slug(name)
        path = self.project_root / "examples" / "mcp" / f"{slug}.py"
        if path.exists():
            raise ValueError(f"Example already exists: {path.relative_to(self.project_root)}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_example_template(title or name, kind=kind), encoding="utf-8")
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


def _example_template(title: str, *, kind: str = "world") -> str:
    normalized = (kind or "world").strip().lower()
    if normalized not in {"world", "game"}:
        raise ValueError("create_example kind must be 'world' or 'game'")
    if normalized == "game":
        return _game_example_template(title)
    return _world_example_template(title)


def _world_example_template(title: str) -> str:
    return _present_scaffold_template(title)


def _game_example_template(title: str) -> str:
    return _character_scaffold_template(title)


def _scaffold_template(family: str, title: str) -> str:
    if family == "present":
        return _present_scaffold_template(title)
    if family == "character":
        return _character_scaffold_template(title)
    return _board_scaffold_template(title)


def _present_scaffold_template(title: str) -> str:
    return f'''"""Present a room or object for the web: orbit, HDRI, embed.

Run from the repository root:
  uv run python examples/mcp/{_slug(title)}.py

Drag to orbit, scroll to zoom. After decorating, export and paste
``<sceneify-viewer>`` from dist-web/EMBED.txt. In-repo primitives; no remote cache.
"""

from pathlib import Path

from sceneify import ExperienceManifest, Material, Physics, Scene

# sceneify:scene-begin
def build_scene() -> Scene:
    scene = Scene({title!r}, background="#10131a")
    scene.set_experience(ExperienceManifest.present(title={title!r}))
    scene.set_presentation(
        shadows=True,
        environmentPreset="apartment",
        grid=False,
        helpers=False,
        camera={{"position": [6, 4, 8], "target": [0, 1, 0], "fov": 42}},
        title={title!r},
        subtitle="Drag to orbit · scroll to zoom",
    )
    scene.create_primitive(
        "floor",
        "box",
        size=(10.0, 0.16, 10.0),
        position=(0.0, -0.08, 0.0),
        material=Material("#2b3344"),
        physics=Physics(body="fixed", collider="cuboid"),
    )
    scene.create_primitive(
        "plinth",
        "box",
        size=(1.6, 0.7, 1.6),
        position=(0.0, 0.35, 0.0),
        material=Material("#8a7a66"),
    )
    return scene
# sceneify:scene-end


if __name__ == "__main__":
    scene = build_scene()
    # After decorating, embed on a site:
    #   scene.export_web("dist-web", api_base="http://127.0.0.1:8765")
    # Then paste dist-web/EMBED.txt (<sceneify-viewer> or iframe).
    scene.run(project_root=Path(__file__).parents[2])
'''


def _character_scaffold_template(title: str) -> str:
    return f'''"""Explore a space with a character controller and optional objectives.

Run from the repository root:
  uv run python examples/mcp/{_slug(title)}.py

Controls: WASD / arrows to move, Space to jump. Collect the relic, reach the exit.
Assets: in-repo primitives (no remote cache). Game() sugar is the collect recipe;
this shell uses scene.character() instead.
"""

from pathlib import Path

from sceneify import Material, Physics, Scene

# sceneify:scene-begin
def build_scene() -> Scene:
    scene = Scene({title!r}, background="#10131a")
    scene.set_presentation(
        shadows=True,
        environmentPreset="night",
        camera={{"position": [10, 8, 12], "target": [0, 1, 0], "fov": 50}},
        title={title!r},
    )
    scene.create_primitive(
        "ground",
        "box",
        size=(24.0, 0.2, 24.0),
        position=(0.0, -0.1, 0.0),
        material=Material("#2d3b32"),
        physics=Physics(body="fixed", collider="cuboid"),
        tags=["ground"],
    )
    scene.create_primitive(
        "relic_1",
        "sphere",
        position=(3.0, 0.6, -2.0),
        radius=0.28,
        material=Material("#d4af37"),
        physics=Physics(body="kinematic", collider="ball", sensor=True),
        tags=["pickup"],
    )
    scene.create_primitive(
        "exit",
        "box",
        size=(2.0, 2.0, 1.0),
        position=(0.0, 1.0, -8.0),
        material=Material("#4aa36b"),
        physics=Physics(body="kinematic", collider="cuboid", sensor=True),
        tags=["goal"],
    )
    play = scene.character(preset="third_person")
    play.hud(title={title!r}, hint="Move: WASD · Jump: Space")
    play.objective("collect", need=1)
    play.objective("reach", node_id="exit", need=1)
    return scene
# sceneify:scene-end


if __name__ == "__main__":
    build_scene().play(project_root=Path(__file__).parents[2])
'''


def _board_scaffold_template(title: str) -> str:
    return f'''"""Tabletop shell: grid, pieces, pick, turns, HUD. Rules stay in this file.

Run from the repository root:
  uv run python examples/mcp/{_slug(title)}.py

Controls: click a piece, then an empty square. HUD start/restart.
Assets: KayKit knight + mage (CC0, examples/assets/kaykit).
"""

from pathlib import Path

from sceneify import Scene

# sceneify:scene-begin
def build_scene() -> Scene:
    scene = Scene({title!r}, background="#1a1410")
    scene.set_presentation(
        shadows=True,
        environmentPreset="studio",
        grid=False,
        helpers=False,
        camera={{"position": [0, 12, 10], "target": [0, 0, 0], "fov": 40}},
        title={title!r},
    )
    board = scene.add_board(size=(8, 8), cell_size=1.0, title={title!r})
    board.place(
        "token_a",
        cell=(1, 1),
        owner="P1",
        asset="kaykit-knight",
        scale=(0.42, 0.42, 0.42),
    )
    board.place(
        "token_b",
        cell=(6, 6),
        owner="P2",
        asset="kaykit-mage",
        scale=(0.42, 0.42, 0.42),
    )
    board.hud(hint="Click a piece, then an empty square.")

    @board.on_pick
    def handle(current, pick):
        if pick.kind == "piece":
            current.select(pick.node_id)
            current.highlight(current.empty_cells())
            return
        if pick.kind == "cell" and current.selected_id and pick.cell is not None:
            if pick.cell in current.highlights:
                current.move(current.selected_id, pick.cell)
                current.clear_highlights()
                current.next_turn()

    return scene
# sceneify:scene-end


if __name__ == "__main__":
    build_scene().play(project_root=Path(__file__).parents[2])
'''
