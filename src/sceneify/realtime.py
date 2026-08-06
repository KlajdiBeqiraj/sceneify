"""Public types for realtime scene callbacks."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sceneify.scene import Scene


@dataclass(frozen=True, slots=True)
class InputEvent:
    """Input sent by a connected viewer."""

    action: str
    value: Any = None
    client_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SemanticEvent:
    """A game-level event emitted by the browser runtime."""

    name: str
    node_id: str | None = None
    value: Any = None
    client_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)


type CallbackResult = Awaitable[None] | None
type TickCallback = Callable[["Scene", float], CallbackResult]
type InputCallback = Callable[["Scene", InputEvent], CallbackResult]
type EventCallback = Callable[["Scene", SemanticEvent], CallbackResult]
