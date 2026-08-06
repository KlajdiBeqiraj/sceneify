"""Shared geometry helpers."""

from __future__ import annotations

from typing import Sequence

Vec3 = tuple[float, float, float]


def as_vec3(value: Sequence[float] | None, default: Vec3 = (0.0, 0.0, 0.0)) -> Vec3:
    if value is None:
        return default
    if len(value) != 3:
        raise ValueError("Expected a 3-length sequence for x, y, z")
    return (float(value[0]), float(value[1]), float(value[2]))
