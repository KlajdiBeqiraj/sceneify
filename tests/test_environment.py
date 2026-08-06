"""Unit tests for geometric environment rules."""

from __future__ import annotations

import pytest

from sceneify.environment import Environment, RuleKind, build_default_environment
from sceneify.scene import Scene


def test_default_environment_clamps_below_ground_and_outside_bounds() -> None:
    env = build_default_environment(
        bounds_min=(-1, 0, -1),
        bounds_max=(1, 2, 1),
        ground_y=0.0,
        snap=0.5,
    )
    point, violations = env.apply_point((-3, -1, 0.2), node_id="probe")
    assert point[0] == pytest.approx(-1.0)
    assert point[1] == pytest.approx(0.0)
    assert point[2] == pytest.approx(0.0)
    kinds = {v.rule for v in violations}
    assert RuleKind.INSIDE_BOUNDS in kinds
    assert RuleKind.SNAP_TO_GRID in kinds


def test_above_ground_clamps_when_bounds_allow_negative_y() -> None:
    env = Environment()
    env.set_ground(0.0)
    env.add_rule(RuleKind.ABOVE_GROUND, mode="clamp")
    point, violations = env.apply_point((0.0, -2.0, 0.0), node_id="probe")
    assert point[1] == pytest.approx(0.0)
    assert violations[0].rule == RuleKind.ABOVE_GROUND


def test_forbidden_zone_rejects() -> None:
    env = Environment()
    env.add_zone("hot", role="forbidden", min_point=(0, 0, 0), max_point=(1, 1, 1))
    env.add_rule(RuleKind.OUTSIDE_FORBIDDEN, mode="reject")
    with pytest.raises(ValueError, match="forbidden zone"):
        env.apply_point((0.5, 0.5, 0.5), node_id="x")


def test_scene_applies_environment_on_add() -> None:
    scene = Scene("t")
    scene.set_environment(bounds_min=(-2, 0, -2), bounds_max=(2, 2, 2), ground_y=0, snap=None)
    scene.add_annotation("a", position=(5, -1, 0), label="n")
    ann = scene.to_dict()["annotations"][0]
    assert ann["position"] == [2.0, 0.0, 0.0]
