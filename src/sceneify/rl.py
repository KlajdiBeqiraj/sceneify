"""RL environments moved to the scenegym package."""

from __future__ import annotations

from typing import Any


class ReachTargetEnv:
    """Compatibility shim. Install scenegym for the Gymnasium environment."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise ImportError(
            "ReachTargetEnv moved to scenegym. "
            "Install with: uv add scenegym  "
            "(and optionally: uv add 'scenegym[sb3]')."
        )
