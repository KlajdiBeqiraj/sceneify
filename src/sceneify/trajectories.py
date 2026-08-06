"""Trajectories and paths in the 3D scene."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from sceneify.types import Vec3, as_vec3


@dataclass
class Trajectory:
    id: str
    points: list[Vec3]
    color: str = "#2f80ed"
    line_width: float = 2.0
    closed: bool = False
    visible: bool = True
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "trajectory",
            "id": self.id,
            "points": [list(p) for p in self.points],
            "color": self.color,
            "lineWidth": self.line_width,
            "closed": self.closed,
            "visible": self.visible,
            "meta": self.meta,
        }


def build_trajectory(
    trajectory_id: str,
    points: Sequence[Sequence[float]],
    *,
    color: str = "#2f80ed",
    line_width: float = 2.0,
    closed: bool = False,
    visible: bool = True,
    **meta: Any,
) -> Trajectory:
    if len(points) < 2:
        raise ValueError("A trajectory needs at least two points")
    return Trajectory(
        id=trajectory_id,
        points=[as_vec3(p) for p in points],
        color=color,
        line_width=line_width,
        closed=closed,
        visible=visible,
        meta=meta,
    )
