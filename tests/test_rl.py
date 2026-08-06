"""Tests for the optional reach target environment."""

from __future__ import annotations

import importlib.util

import pytest

from sceneify.rl import ReachTargetEnv


def test_optional_import_has_clear_error() -> None:
    if importlib.util.find_spec("gymnasium") is None:
        with pytest.raises(ImportError, match="requires Gymnasium and NumPy"):
            ReachTargetEnv()


def test_reach_target_env_headless_step() -> None:
    pytest.importorskip("gymnasium")
    np = pytest.importorskip("numpy")
    environment = ReachTargetEnv(max_steps=2)
    observation, info = environment.reset(
        seed=7,
        options={"position": [0, 0, 0], "target": [1, 0, 0]},
    )
    assert observation.shape == (6,)
    assert info["distance"] == pytest.approx(1.0)

    observation, reward, terminated, truncated, info = environment.step(
        np.array([1, 0, 0], dtype=np.float32)
    )
    assert observation.shape == (6,)
    assert reward < 0
    assert not terminated
    assert not truncated
    assert info["distance"] < 1.0
    environment.close()


def test_reach_target_env_terminates_at_target() -> None:
    pytest.importorskip("gymnasium")
    environment = ReachTargetEnv()
    environment.reset(options={"position": [0, 0, 0], "target": [0, 0, 0]})
    _, reward, terminated, truncated, _ = environment.step([0, 0, 0])
    assert reward == 1.0
    assert terminated
    assert not truncated
    environment.close()


def test_reach_target_env_passes_gymnasium_checker() -> None:
    pytest.importorskip("gymnasium")
    from gymnasium.utils.env_checker import check_env

    environment = ReachTargetEnv()
    check_env(environment, skip_render_check=True)
    environment.close()
