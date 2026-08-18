"""Protocol demo: Python owns a marker pose from browser WASD input.

This is not a character_world or board game. It shows ``@scene.on_input``
updating a node; the viewer is just a viewport. For playable characters see
``examples/game/collect_escape.py`` / ``examples/mcp/ruins.py``.

Run from the repository root:
  uv run python examples/realtime/realtime_minigame.py

Controls: WASD or arrows. Reach the green target to relabel it Collected.
Assets: none (annotation markers only).
"""

from __future__ import annotations

from pathlib import Path

from sceneify import InputEvent, Scene

ROOT = Path(__file__).resolve().parents[2]


def build_scene() -> Scene:
    scene = Scene("collect-the-target")
    scene.set_presentation(
        title="Realtime input callback",
        subtitle="Protocol demo — not a character or board game. WASD moves the cyan marker.",
    )
    player = scene.add_annotation("player", (0, 0, 0), label="Player", color="#56ccf2")
    target = scene.add_annotation("target", (2, 0, 2), label="Target", color="#6fcf97")

    @scene.on_input
    def move_player(current: Scene, event: InputEvent) -> None:
        directions = {
            "ArrowLeft": (-0.25, 0.0, 0.0),
            "a": (-0.25, 0.0, 0.0),
            "ArrowRight": (0.25, 0.0, 0.0),
            "d": (0.25, 0.0, 0.0),
            "ArrowUp": (0.0, 0.0, -0.25),
            "w": (0.0, 0.0, -0.25),
            "ArrowDown": (0.0, 0.0, 0.25),
            "s": (0.0, 0.0, 0.25),
        }
        if (
            event.action != "keydown"
            or not isinstance(event.value, str)
            or event.value not in directions
        ):
            return
        offset = directions[event.value]
        next_position = tuple(a + b for a, b in zip(player.position, offset, strict=True))
        current.update_node("player", position=next_position)
        if sum((a - b) ** 2 for a, b in zip(player.position, target.position, strict=True)) < 0.1:
            target.label = "Collected"

    return scene


if __name__ == "__main__":
    print("Click the browser window, then WASD / arrows to move the cyan marker to the green target.")
    build_scene().play(project_root=ROOT)
