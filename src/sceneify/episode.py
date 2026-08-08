"""Versioned game episode recording and replay models."""

from __future__ import annotations

import copy
import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

EPISODE_FORMAT = "sceneify-episode"
EPISODE_VERSION = 1

EventKind = Literal["input", "semantic", "marker"]


@dataclass
class EpisodeEvent:
    """One timestamped event inside an episode timeline."""

    t: float
    kind: EventKind
    action: str | None = None
    name: str | None = None
    value: Any = None
    node_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in {"input", "semantic", "marker"}:
            raise ValueError(f"Unsupported episode event kind: {self.kind!r}")
        if self.t < 0:
            raise ValueError("Episode event time must be >= 0")
        if self.kind == "input" and not self.action:
            raise ValueError("Input episode events require an action")
        if self.kind in {"semantic", "marker"} and not self.name:
            raise ValueError(f"{self.kind} episode events require a name")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"t": float(self.t), "kind": self.kind}
        if self.kind == "input":
            payload["action"] = self.action
            payload["value"] = copy.deepcopy(self.value)
            payload["metadata"] = copy.deepcopy(self.metadata)
        elif self.kind == "semantic":
            payload["name"] = self.name
            payload["nodeId"] = self.node_id
            payload["value"] = copy.deepcopy(self.value)
            payload["data"] = copy.deepcopy(self.data)
        else:
            payload["name"] = self.name
            payload["data"] = copy.deepcopy(self.data)
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EpisodeEvent:
        kind = data.get("kind")
        if kind not in {"input", "semantic", "marker"}:
            raise ValueError(f"Unsupported episode event kind: {kind!r}")
        return cls(
            t=float(data.get("t", 0.0)),
            kind=kind,  # type: ignore[arg-type]
            action=data.get("action"),
            name=data.get("name"),
            value=copy.deepcopy(data.get("value")),
            node_id=data.get("nodeId", data.get("node_id")),
            data=copy.deepcopy(dict(data.get("data") or {})),
            metadata=copy.deepcopy(dict(data.get("metadata") or {})),
        )


@dataclass
class Episode:
    """A recorded play session: timed browser inputs and semantic events."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    scene_name: str = "scene"
    tick_rate: float = 60.0
    duration: float = 0.0
    events: list[EpisodeEvent] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def add_input(
        self,
        t: float,
        action: str,
        *,
        value: Any = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> EpisodeEvent:
        event = EpisodeEvent(
            t=t,
            kind="input",
            action=action,
            value=value,
            metadata=dict(metadata or {}),
        )
        self._append(event)
        return event

    def add_semantic(
        self,
        t: float,
        name: str,
        *,
        node_id: str | None = None,
        value: Any = None,
        data: Mapping[str, Any] | None = None,
    ) -> EpisodeEvent:
        event = EpisodeEvent(
            t=t,
            kind="semantic",
            name=name,
            node_id=node_id,
            value=value,
            data=dict(data or {}),
        )
        self._append(event)
        return event

    def add_marker(
        self, t: float, name: str, *, data: Mapping[str, Any] | None = None
    ) -> EpisodeEvent:
        event = EpisodeEvent(t=t, kind="marker", name=name, data=dict(data or {}))
        self._append(event)
        return event

    def inputs(self) -> list[EpisodeEvent]:
        return [event for event in self.events if event.kind == "input"]

    def semantic_events(self) -> list[EpisodeEvent]:
        return [event for event in self.events if event.kind == "semantic"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sceneName": self.scene_name,
            "tickRate": float(self.tick_rate),
            "duration": float(self.duration),
            "events": [event.to_dict() for event in self.events],
            "meta": copy.deepcopy(self.meta),
        }

    def to_document(self) -> dict[str, Any]:
        return {
            "format": EPISODE_FORMAT,
            "version": EPISODE_VERSION,
            "episode": self.to_dict(),
        }

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_document(), indent=2) + "\n", encoding="utf-8")
        return target

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Episode:
        events_raw = data.get("events") or []
        if not isinstance(events_raw, Sequence) or isinstance(events_raw, (str, bytes)):
            raise ValueError("Episode events must be an array")
        events = [EpisodeEvent.from_dict(item) for item in events_raw]
        events.sort(key=lambda item: item.t)
        duration = float(data.get("duration", events[-1].t if events else 0.0))
        if events:
            duration = max(duration, events[-1].t)
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex),
            scene_name=str(data.get("sceneName", data.get("scene_name", "scene"))),
            tick_rate=float(data.get("tickRate", data.get("tick_rate", 60.0))),
            duration=duration,
            events=events,
            meta=copy.deepcopy(dict(data.get("meta") or {})),
        )

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Episode:
        if document.get("format") != EPISODE_FORMAT:
            raise ValueError(f"Unsupported episode format: {document.get('format')!r}")
        version = document.get("version")
        if isinstance(version, bool) or version != EPISODE_VERSION:
            raise ValueError(f"Unsupported episode version: {version!r}")
        payload = document.get("episode")
        if not isinstance(payload, Mapping):
            raise ValueError("Episode document payload must be an object")
        return cls.from_dict(payload)

    @classmethod
    def load(cls, path: str | Path) -> Episode:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Episode file must contain a JSON object")
        if "episode" in raw or raw.get("format") == EPISODE_FORMAT:
            return cls.from_document(raw)
        return cls.from_dict(raw)

    def _append(self, event: EpisodeEvent) -> None:
        self.events.append(event)
        self.events.sort(key=lambda item: item.t)
        self.duration = max(self.duration, event.t)


class EpisodeRecorder:
    """Accumulate timed events while a play session is active."""

    def __init__(
        self,
        *,
        scene_name: str,
        tick_rate: float,
        episode_id: str | None = None,
        meta: Mapping[str, Any] | None = None,
    ) -> None:
        self.started_at = 0.0
        self._clock_started = False
        self.episode = Episode(
            id=episode_id or uuid.uuid4().hex,
            scene_name=scene_name,
            tick_rate=tick_rate,
            meta=dict(meta or {}),
        )

    def start_clock(self, now: float) -> None:
        if not self._clock_started:
            self.started_at = now
            self._clock_started = True

    def elapsed(self, now: float) -> float:
        self.start_clock(now)
        return max(0.0, now - self.started_at)

    def record_input(
        self,
        now: float,
        action: str,
        *,
        value: Any = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.episode.add_input(self.elapsed(now), action, value=value, metadata=metadata)

    def record_semantic(
        self,
        now: float,
        name: str,
        *,
        node_id: str | None = None,
        value: Any = None,
        data: Mapping[str, Any] | None = None,
    ) -> None:
        self.episode.add_semantic(
            self.elapsed(now),
            name,
            node_id=node_id,
            value=value,
            data=data,
        )

    def finish(self, now: float) -> Episode:
        self.episode.duration = max(self.episode.duration, self.elapsed(now))
        self.episode.add_marker(self.episode.duration, "end")
        return self.episode
