"""Shim tests for the moved ReachTargetEnv entry point."""

from __future__ import annotations

import pytest

from sceneify.rl import ReachTargetEnv


def test_rl_shim_points_to_scenegym() -> None:
    with pytest.raises(ImportError, match="scenegym"):
        ReachTargetEnv()
