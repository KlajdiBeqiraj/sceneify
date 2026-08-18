"""Declarative experience manifest: present, character, or tabletop board.

``scene.experience`` is the runtime switch. ``sf.Game()`` remains sugar for a
character collect recipe and serializes into ``experience.character``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ExperienceFamily = Literal["present", "character", "board"]
RuntimeSlot = Literal["present", "character_world", "tabletop", "none"]
PrimaryInteraction = Literal["none", "poi", "overlap", "cell_pick"]
CameraMode = Literal["orbit", "look", "fixed", "follow", "first_person", "topdown"]
MatchPhase = Literal["menu", "playing", "won", "lost", "draw"]
HudMetricKind = Literal["score", "health", "timer", "text", "turn"]
ObjectiveKind = Literal["collect", "reach", "survive", "callback"]
CharacterPreset = Literal["third_person", "first_person", "topdown"]

FAMILIES: tuple[str, ...] = ("present", "character", "board")
RUNTIME_SLOTS: tuple[str, ...] = ("present", "character_world", "tabletop", "none")
PRIMARY_INTERACTIONS: tuple[str, ...] = ("none", "poi", "overlap", "cell_pick")

_FAMILY_SLOT: dict[str, str] = {
    "present": "present",
    "character": "character_world",
    "board": "tabletop",
}

_FAMILY_INTERACTION: dict[str, str] = {
    "present": "poi",
    "character": "overlap",
    "board": "cell_pick",
}

CHARACTER_PRESETS: dict[str, dict[str, float | str]] = {
    "third_person": {"controller": "simple", "distance": 6.0, "height": 3.0},
    "first_person": {"controller": "simple", "distance": 0.18, "height": 1.55},
    "topdown": {"controller": "simple", "distance": 0.4, "height": 16.0},
}


@dataclass
class CameraPolicy:
    mode: CameraMode = "orbit"
    distance: float | None = None
    height: float | None = None
    target_id: str | None = None


@dataclass
class InputPolicy:
    enabled: bool = False


@dataclass
class InteractionPolicy:
    primary: PrimaryInteraction = "none"


@dataclass
class HudMetric:
    id: str
    label: str
    kind: HudMetricKind = "text"


@dataclass
class HudPolicy:
    enabled: bool = False
    title: str | None = None
    hint: str | None = None
    description: str | None = None
    metrics: list[HudMetric] = field(default_factory=list)
    win_message: str | None = None
    lose_message: str | None = None
    draw_message: str | None = None
    start_label: str | None = None


@dataclass
class MatchState:
    phase: MatchPhase = "menu"


@dataclass
class Objective:
    kind: ObjectiveKind
    need: int | None = None
    node_id: str | None = None
    seconds: float | None = None


@dataclass
class TabletopPiece:
    id: str
    cell: tuple[int, int]
    owner: str | None = None


@dataclass
class TabletopPayload:
    rows: int
    cols: int
    cell_size: float = 1.0
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    pieces: list[TabletopPiece] = field(default_factory=list)
    turn: int = 0
    turn_count: int = 2
    selected_id: str | None = None
    highlights: list[str] = field(default_factory=list)
    owners: list[str] = field(default_factory=lambda: ["P1", "P2"])


@dataclass
class ExperienceManifest:
    """Runtime switch for the viewer: present, character world, or tabletop."""

    family: ExperienceFamily = "present"
    runtime_slot: RuntimeSlot = "present"
    schema_version: int = 1
    camera: CameraPolicy = field(default_factory=CameraPolicy)
    input: InputPolicy = field(default_factory=InputPolicy)
    interaction: InteractionPolicy = field(default_factory=InteractionPolicy)
    hud: HudPolicy = field(default_factory=HudPolicy)
    character: dict[str, Any] | None = None
    tabletop: TabletopPayload | None = None
    match: MatchState = field(default_factory=MatchState)
    objectives: list[Objective] = field(default_factory=list)
    sync: int = 0

    def __post_init__(self) -> None:
        if self.family not in FAMILIES:
            raise ValueError(f"Unsupported experience family: {self.family!r}")
        if self.runtime_slot not in RUNTIME_SLOTS:
            raise ValueError(f"Unsupported runtime slot: {self.runtime_slot!r}")
        if self.interaction.primary not in PRIMARY_INTERACTIONS:
            raise ValueError(f"Unsupported interaction: {self.interaction.primary!r}")

    def touch(self) -> None:
        self.sync += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "family": self.family,
            "runtimeSlot": self.runtime_slot,
            "camera": _camel_dict(self.camera),
            "input": _camel_dict(self.input),
            "interaction": _camel_dict(self.interaction),
            "hud": {
                **_camel_dict(self.hud),
                "metrics": [_camel_dict(item) for item in self.hud.metrics],
            },
            "character": dict(self.character) if self.character else None,
            "tabletop": _tabletop_dict(self.tabletop) if self.tabletop else None,
            "match": _camel_dict(self.match),
            "objectives": [_camel_dict(item) for item in self.objectives],
            "sync": self.sync,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ExperienceManifest:
        values = data or {}
        family = str(values.get("family") or "present")
        if family not in FAMILIES:
            raise ValueError(f"Unsupported experience family: {family!r}")
        slot = str(values.get("runtimeSlot") or values.get("runtime_slot") or _FAMILY_SLOT[family])
        interaction = values.get("interaction") or {}
        primary = str(
            interaction.get("primary") if isinstance(interaction, dict) else _FAMILY_INTERACTION[family]
        )
        camera = values.get("camera") or {}
        input_policy = values.get("input") or {}
        hud = values.get("hud") or {}
        match = values.get("match") or {}
        tabletop = values.get("tabletop")
        objectives = values.get("objectives") or []
        return cls(
            family=family,  # type: ignore[arg-type]
            runtime_slot=slot,  # type: ignore[arg-type]
            schema_version=int(values.get("schemaVersion", values.get("schema_version", 1))),
            camera=CameraPolicy(
                mode=str(camera.get("mode", "orbit")),  # type: ignore[arg-type]
                distance=camera.get("distance"),
                height=camera.get("height"),
                target_id=camera.get("targetId", camera.get("target_id")),
            ),
            input=InputPolicy(enabled=bool(input_policy.get("enabled", family != "present"))),
            interaction=InteractionPolicy(primary=primary),  # type: ignore[arg-type]
            hud=_hud_from_dict(hud) if isinstance(hud, dict) else HudPolicy(),
            character=dict(values["character"]) if isinstance(values.get("character"), dict) else None,
            tabletop=_tabletop_from_dict(tabletop) if isinstance(tabletop, dict) else None,
            match=MatchState(phase=str(match.get("phase", "menu"))),  # type: ignore[arg-type]
            objectives=[
                Objective(
                    kind=str(item.get("kind", "callback")),  # type: ignore[arg-type]
                    need=item.get("need"),
                    node_id=item.get("nodeId", item.get("node_id")),
                    seconds=item.get("seconds"),
                )
                for item in objectives
                if isinstance(item, dict)
            ],
            sync=int(values.get("sync", 0)),
        )

    @classmethod
    def present(cls, *, title: str | None = None) -> ExperienceManifest:
        return cls(
            family="present",
            runtime_slot="present",
            camera=CameraPolicy(mode="orbit"),
            input=InputPolicy(enabled=False),
            interaction=InteractionPolicy(primary="poi"),
            hud=HudPolicy(enabled=False, title=title),
        )

    @classmethod
    def character_world(
        cls,
        character: dict[str, Any] | None = None,
        *,
        preset: CharacterPreset = "third_person",
        title: str | None = None,
    ) -> ExperienceManifest:
        camera_preset = CHARACTER_PRESETS[preset]
        hud = _hud_from_character(character, title=title)
        return cls(
            family="character",
            runtime_slot="character_world",
            camera=CameraPolicy(
                mode="follow" if preset == "third_person" else preset,  # type: ignore[arg-type]
                distance=float(camera_preset["distance"]),
                height=float(camera_preset["height"]),
            ),
            input=InputPolicy(enabled=True),
            interaction=InteractionPolicy(primary="overlap"),
            hud=hud,
            character=dict(character) if character else {},
        )

    @classmethod
    def board(
        cls,
        *,
        rows: int,
        cols: int,
        cell_size: float = 1.0,
        origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
        title: str | None = None,
        owners: list[str] | None = None,
    ) -> ExperienceManifest:
        names = list(owners or ["P1", "P2"])
        return cls(
            family="board",
            runtime_slot="tabletop",
            camera=CameraPolicy(mode="orbit", height=10.0),
            input=InputPolicy(enabled=True),
            interaction=InteractionPolicy(primary="cell_pick"),
            hud=HudPolicy(
                enabled=True,
                title=title or "Table game",
                hint="Click a piece, then an empty cell.",
                description="Place pieces and write short Python rules.",
                metrics=[
                    HudMetric("turn", "Turn", "turn"),
                    HudMetric("selected", "Selected", "text"),
                ],
                win_message="You win",
                lose_message="You lose",
                draw_message="Draw",
                start_label="Start match",
            ),
            tabletop=TabletopPayload(
                rows=rows,
                cols=cols,
                cell_size=cell_size,
                origin=origin,
                owners=names,
                turn_count=max(1, len(names)),
            ),
        )


def experience_from_character(character: dict[str, Any] | None) -> dict[str, Any]:
    """Wrap a Game() collect payload as a character experience."""
    return ExperienceManifest.character_world(character).to_dict()


def character_payload(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the collect/controller payload from an experience or legacy game dict."""
    if not data:
        return None
    experience = data.get("experience")
    if isinstance(experience, dict) and isinstance(experience.get("character"), dict):
        return dict(experience["character"])
    game = data.get("game")
    if isinstance(game, dict):
        return dict(game)
    if data.get("family") == "character" and isinstance(data.get("character"), dict):
        return dict(data["character"])
    return None


def wrap_legacy_game(payload: dict[str, Any]) -> dict[str, Any]:
    """If a payload still has ``game`` and no ``experience``, wrap it in place."""
    experience = payload.get("experience")
    game = payload.get("game")
    if not isinstance(experience, dict) and isinstance(game, dict):
        payload["experience"] = experience_from_character(game)
    payload.pop("game", None)
    payload.setdefault("experience", None)
    return payload


def _hud_from_character(character: dict[str, Any] | None, *, title: str | None) -> HudPolicy:
    hud = (character or {}).get("hud") or {}
    win = (character or {}).get("win") or {}
    lose = (character or {}).get("lose") or {}
    metrics: list[HudMetric] = []
    if hud.get("showScore", True):
        metrics.append(HudMetric("score", "Relics", "score"))
    if hud.get("showHealth", True):
        metrics.append(HudMetric("health", "Health", "health"))
    if hud.get("showTimer", True):
        metrics.append(HudMetric("timer", "Time", "timer"))
    return HudPolicy(
        enabled=True,
        title=hud.get("title") or title,
        hint=hud.get("controlsHint") or hud.get("controls_hint"),
        description=hud.get("description"),
        metrics=metrics,
        win_message=win.get("message"),
        lose_message=lose.get("message"),
        start_label="Start run",
    )


def _hud_from_dict(hud: dict[str, Any]) -> HudPolicy:
    metrics = []
    for item in hud.get("metrics") or []:
        if not isinstance(item, dict):
            continue
        metrics.append(
            HudMetric(
                id=str(item.get("id") or item.get("kind") or "metric"),
                label=str(item.get("label") or item.get("id") or "Metric"),
                kind=str(item.get("kind", "text")),  # type: ignore[arg-type]
            )
        )
    return HudPolicy(
        enabled=bool(hud.get("enabled", False)),
        title=hud.get("title"),
        hint=hud.get("hint") or hud.get("controlsHint") or hud.get("controls_hint"),
        description=hud.get("description"),
        metrics=metrics,
        win_message=hud.get("winMessage") or hud.get("win_message"),
        lose_message=hud.get("loseMessage") or hud.get("lose_message"),
        draw_message=hud.get("drawMessage") or hud.get("draw_message"),
        start_label=hud.get("startLabel") or hud.get("start_label"),
    )


def _tabletop_dict(value: TabletopPayload) -> dict[str, Any]:
    return {
        "rows": value.rows,
        "cols": value.cols,
        "cellSize": value.cell_size,
        "origin": list(value.origin),
        "pieces": [
            {"id": piece.id, "cell": list(piece.cell), "owner": piece.owner} for piece in value.pieces
        ],
        "turn": value.turn,
        "turnCount": value.turn_count,
        "selectedId": value.selected_id,
        "highlights": list(value.highlights),
        "owners": list(value.owners),
    }


def _tabletop_from_dict(data: dict[str, Any]) -> TabletopPayload:
    origin = data.get("origin") or [0.0, 0.0, 0.0]
    pieces = []
    for item in data.get("pieces") or []:
        if not isinstance(item, dict):
            continue
        cell = item.get("cell") or [0, 0]
        pieces.append(
            TabletopPiece(
                id=str(item["id"]),
                cell=(int(cell[0]), int(cell[1])),
                owner=item.get("owner"),
            )
        )
    return TabletopPayload(
        rows=int(data.get("rows", 8)),
        cols=int(data.get("cols", 8)),
        cell_size=float(data.get("cellSize", data.get("cell_size", 1.0))),
        origin=(float(origin[0]), float(origin[1]), float(origin[2])),
        pieces=pieces,
        turn=int(data.get("turn", 0)),
        turn_count=int(data.get("turnCount", data.get("turn_count", 2))),
        selected_id=data.get("selectedId", data.get("selected_id")),
        highlights=[str(item) for item in data.get("highlights") or []],
        owners=[str(item) for item in data.get("owners") or ["P1", "P2"]],
    )


def _camel_dict(value: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in asdict(value).items():
        parts = key.split("_")
        result[parts[0] + "".join(part.title() for part in parts[1:])] = item
    return result
