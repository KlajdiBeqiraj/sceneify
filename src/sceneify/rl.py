"""Optional Gymnasium environment for kinematic reach target tasks."""

from __future__ import annotations

from typing import Any, ClassVar

_GYM_IMPORT_ERROR: ImportError | None = None

try:
    import gymnasium as gym
    import numpy as np
except ImportError as exc:
    gym = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    _GYM_IMPORT_ERROR = exc


def _missing_gymnasium() -> ImportError:
    return ImportError(
        "sceneify.rl requires Gymnasium and NumPy. Install both packages to use ReachTargetEnv."
    )


if gym is not None and np is not None:

    class ReachTargetEnv(gym.Env):
        """A small continuous control task with kinematic three dimensional motion."""

        metadata: ClassVar[dict[str, Any]] = {
            "render_modes": ["human"],
            "render_fps": 30,
        }

        def __init__(
            self,
            *,
            render_mode: str | None = None,
            world_size: float = 5.0,
            speed: float = 3.0,
            time_step: float = 1.0 / 30.0,
            target_radius: float = 0.2,
            max_steps: int = 300,
            browser_port: int = 8765,
        ) -> None:
            super().__init__()
            if render_mode not in {None, "human"}:
                raise ValueError("render_mode must be None or 'human'")
            if world_size <= 0 or speed <= 0 or time_step <= 0 or target_radius <= 0:
                raise ValueError("World and motion parameters must be greater than zero")
            if max_steps <= 0:
                raise ValueError("max_steps must be greater than zero")
            self.render_mode = render_mode
            self.world_size = float(world_size)
            self.speed = float(speed)
            self.time_step = float(time_step)
            self.target_radius = float(target_radius)
            self.max_steps = int(max_steps)
            self.browser_port = int(browser_port)
            self.action_space = gym.spaces.Box(-1.0, 1.0, shape=(3,), dtype=np.float32)
            limit = np.full(6, self.world_size, dtype=np.float32)
            self.observation_space = gym.spaces.Box(-limit, limit, dtype=np.float32)
            self._position = np.zeros(3, dtype=np.float32)
            self._target = np.zeros(3, dtype=np.float32)
            self._steps = 0
            self._scene: Any = None
            self._server: Any = None

        def reset(
            self,
            *,
            seed: int | None = None,
            options: dict[str, Any] | None = None,
        ) -> tuple[Any, dict[str, Any]]:
            super().reset(seed=seed)
            options = options or {}
            self._position = np.asarray(
                options.get("position", self.np_random.uniform(-1.0, 1.0, size=3)),
                dtype=np.float32,
            )
            self._target = np.asarray(
                options.get(
                    "target",
                    self.np_random.uniform(-self.world_size, self.world_size, size=3),
                ),
                dtype=np.float32,
            )
            self._position = np.clip(self._position, -self.world_size, self.world_size)
            self._target = np.clip(self._target, -self.world_size, self.world_size)
            self._steps = 0
            if self.render_mode == "human":
                self.render()
            return self._observation(), self._info()

        def step(self, action: Any) -> tuple[Any, float, bool, bool, dict[str, Any]]:
            velocity = np.clip(np.asarray(action, dtype=np.float32), -1.0, 1.0)
            if velocity.shape != (3,):
                raise ValueError("Action must contain three values")
            self._position += velocity * self.speed * self.time_step
            self._position = np.clip(self._position, -self.world_size, self.world_size)
            self._steps += 1
            distance = float(np.linalg.norm(self._target - self._position))
            terminated = distance <= self.target_radius
            truncated = self._steps >= self.max_steps and not terminated
            reward = 1.0 if terminated else -distance
            if self.render_mode == "human":
                self.render()
            return self._observation(), reward, terminated, truncated, self._info()

        def render(self) -> None:
            if self.render_mode != "human":
                return
            if self._scene is None:
                from sceneify.scene import Scene

                self._scene = Scene("reach-target")
                self._scene.add_annotation("agent", self._position, label="Agent", color="#56ccf2")
                self._scene.add_annotation(
                    "target",
                    self._target,
                    label="Target",
                    color="#6fcf97",
                )
                self._server = self._scene.play(
                    port=self.browser_port,
                    open_browser=True,
                    block=False,
                    tick_rate=float(self.metadata["render_fps"]),
                )
            else:
                self._scene.update_node("agent", position=self._position)
                self._scene.update_node("target", position=self._target)

        def close(self) -> None:
            if self._server is not None:
                self._server.stop()
                self._server = None
            self._scene = None

        def _observation(self) -> Any:
            return np.concatenate((self._position, self._target)).astype(np.float32)

        def _info(self) -> dict[str, float]:
            return {"distance": float(np.linalg.norm(self._target - self._position))}

else:

    class ReachTargetEnv:
        """Placeholder that reports the missing optional runtime."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise _missing_gymnasium() from _GYM_IMPORT_ERROR
