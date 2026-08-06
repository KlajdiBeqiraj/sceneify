"""A tiny input driven collect the target game."""

from __future__ import annotations

from sceneify import InputEvent, Scene

scene = Scene("collect-the-target")
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


scene.play()
