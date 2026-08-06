"""Annotations placed in the 3D scene."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from sceneify.types import Vec3, as_vec3


@dataclass
class Annotation:
    id: str
    position: Vec3
    target_id: str | None = None
    offset: Vec3 = (0.0, 0.0, 0.0)
    label: str | None = None
    description: str | None = None
    color: str = "#ffcc00"
    visible: bool = True
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "annotation",
            "id": self.id,
            "position": list(self.position),
            "targetId": self.target_id,
            "offset": list(self.offset),
            "label": self.label,
            "description": self.description,
            "color": self.color,
            "visible": self.visible,
            "meta": self.meta,
        }


def build_annotation(
    annotation_id: str,
    position: Sequence[float],
    *,
    target_id: str | None = None,
    offset: Sequence[float] | None = None,
    label: str | None = None,
    description: str | None = None,
    color: str = "#ffcc00",
    visible: bool = True,
    **meta: Any,
) -> Annotation:
    return Annotation(
        id=annotation_id,
        position=as_vec3(position),
        target_id=target_id,
        offset=as_vec3(offset),
        label=label,
        description=description,
        color=color,
        visible=visible,
        meta=meta,
    )
