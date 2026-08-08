"""Declarative browser game manifest models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass
class ActionMap:
    """Map semantic actions to one or more browser input tokens."""

    actions: dict[str, list[str]] = field(default_factory=dict)

    def bind(self, action: str, *inputs: str) -> ActionMap:
        if not action or not inputs:
            raise ValueError("An action binding needs a name and at least one input")
        self.actions[action] = list(inputs)
        return self

    def to_dict(self) -> dict[str, list[str]]:
        return {name: list(inputs) for name, inputs in self.actions.items()}


ControllerPreset = Literal["simple", "ecctrl"]


@dataclass
class ThirdPersonController:
    """Third-person player controller declared for the browser runtime.

    ``preset="simple"`` keeps the built-in kinematic WASD controller.
    ``preset="ecctrl"`` uses the bundled ecctrl character controller (camera-relative
    movement, sprint, follow cam). ``move_speed`` / ``jump_speed`` map to ecctrl
    ``maxVelLimit`` / ``jumpVel``.
    """

    node_id: str
    move_speed: float = 5.0
    jump_speed: float = 7.0
    action_map: str = "default"
    preset: ControllerPreset = "simple"
    sprint_mult: float = 2.0

    def __post_init__(self) -> None:
        if self.preset not in {"simple", "ecctrl"}:
            raise ValueError(f"Unsupported controller preset: {self.preset!r}")
        if self.move_speed <= 0 or self.jump_speed <= 0:
            raise ValueError("Controller move_speed and jump_speed must be greater than zero")
        if self.sprint_mult <= 0:
            raise ValueError("Controller sprint_mult must be greater than zero")


@dataclass
class CameraFollow:
    target_id: str
    distance: float = 6.0
    height: float = 3.0
    smoothing: float = 0.12


@dataclass
class Collectible:
    node_id: str
    value: int = 1
    event: str = "collect"
    respawn_seconds: float | None = None


@dataclass
class Hazard:
    node_id: str
    damage: int = 1
    event: str = "hazard"
    reset_to_checkpoint: bool = True


@dataclass
class Checkpoint:
    node_id: str
    event: str = "checkpoint"


@dataclass
class Goal:
    node_id: str
    event: str = "goal"
    required_score: int = 0


@dataclass
class HUD:
    show_score: bool = True
    show_health: bool = True
    show_timer: bool = True
    title: str | None = None
    description: str | None = None
    controls_hint: str | None = None


@dataclass
class Timer:
    seconds: float
    mode: Literal["countdown", "countup"] = "countdown"
    start_on_load: bool = True
    timeout_event: str = "timeout"


@dataclass
class Outcome:
    event: str
    message: str


@dataclass
class EnemyType:
    """Continuously spawning chase enemy declared for the browser runtime."""

    kind: str
    source: str
    max_alive: int = 2
    interval_seconds: float = 4.5
    speed: float = 2.6
    scale: float = 0.75
    health: int = 3
    contact_damage: int = 1
    hit_event: str = "hazard"
    animation: dict[str, str] = field(
        default_factory=lambda: {
            "idle": "Idle",
            "run": "Running_A",
            "hit": "Hit_A",
            "death": "Death_A",
        }
    )


@dataclass
class EnemyWave:
    spawn_points: list[tuple[float, float, float]] = field(default_factory=list)
    types: list[EnemyType] = field(default_factory=list)


@dataclass
class GameManifest:
    """Complete game runtime declaration serialized in scene JSON."""

    action_maps: dict[str, ActionMap] = field(default_factory=dict)
    controllers: list[ThirdPersonController] = field(default_factory=list)
    cameras: list[CameraFollow] = field(default_factory=list)
    collectibles: list[Collectible] = field(default_factory=list)
    hazards: list[Hazard] = field(default_factory=list)
    checkpoints: list[Checkpoint] = field(default_factory=list)
    goals: list[Goal] = field(default_factory=list)
    enemies: EnemyWave | None = None
    hud: HUD | None = None
    timer: Timer | None = None
    win: Outcome = field(default_factory=lambda: Outcome("goal", "You win"))
    lose: Outcome = field(default_factory=lambda: Outcome("timeout", "You lose"))

    def action_map(self, name: str = "default", **actions: list[str]) -> ActionMap:
        mapping = ActionMap({key: list(value) for key, value in actions.items()})
        self.action_maps[name] = mapping
        return mapping

    def add_controller(self, node_id: str, **options: Any) -> ThirdPersonController:
        return self._append(self.controllers, ThirdPersonController(node_id, **options))

    def follow_camera(self, target_id: str, **options: Any) -> CameraFollow:
        return self._append(self.cameras, CameraFollow(target_id, **options))

    def add_collectible(self, node_id: str, **options: Any) -> Collectible:
        return self._append(self.collectibles, Collectible(node_id, **options))

    def add_hazard(self, node_id: str, **options: Any) -> Hazard:
        return self._append(self.hazards, Hazard(node_id, **options))

    def add_checkpoint(self, node_id: str, **options: Any) -> Checkpoint:
        return self._append(self.checkpoints, Checkpoint(node_id, **options))

    def add_goal(self, node_id: str, **options: Any) -> Goal:
        return self._append(self.goals, Goal(node_id, **options))

    def set_enemies(
        self,
        *,
        spawn_points: list[tuple[float, float, float] | list[float]],
        types: list[dict[str, Any]],
    ) -> EnemyWave:
        """Configure continuously spawning chase enemies for the runtime."""
        wave = EnemyWave(
            spawn_points=[
                (float(point[0]), float(point[1]), float(point[2])) for point in spawn_points
            ],
            types=[
                EnemyType(
                    kind=str(item["kind"]),
                    source=str(item["source"]),
                    max_alive=int(item.get("max_alive", item.get("maxAlive", 2))),
                    interval_seconds=float(
                        item.get("interval_seconds", item.get("intervalSeconds", 4.5))
                    ),
                    speed=float(item.get("speed", 2.6)),
                    scale=float(item.get("scale", 0.75)),
                    health=int(item.get("health", 3)),
                    contact_damage=int(item.get("contact_damage", item.get("contactDamage", 1))),
                    hit_event=str(item.get("hit_event", item.get("hitEvent", "hazard"))),
                    animation=dict(
                        item.get("animation")
                        or {
                            "idle": "Idle",
                            "run": "Running_A",
                            "hit": "Hit_A",
                            "death": "Death_A",
                        }
                    ),
                )
                for item in types
            ],
        )
        self.enemies = wave
        return wave

    def set_hud(self, **options: Any) -> HUD:
        self.hud = HUD(**options)
        return self.hud

    def set_timer(self, seconds: float, **options: Any) -> Timer:
        self.timer = Timer(seconds, **options)
        return self.timer

    def outcomes(
        self,
        *,
        win_event: str = "goal",
        win_message: str = "You win",
        lose_event: str = "timeout",
        lose_message: str = "You lose",
    ) -> None:
        self.win = Outcome(win_event, win_message)
        self.lose = Outcome(lose_event, lose_message)

    def set_gameplay_role(
        self,
        node_id: str,
        role: Literal["none", "player-spawn", "pickup", "hazard", "checkpoint", "goal"],
    ) -> None:
        """Assign one exclusive gameplay role to a scene node."""
        if role not in {"none", "player-spawn", "pickup", "hazard", "checkpoint", "goal"}:
            raise ValueError(f"Unsupported gameplay role: {role!r}")
        self.controllers = [item for item in self.controllers if item.node_id != node_id]
        self.cameras = [item for item in self.cameras if item.target_id != node_id]
        self.collectibles = [item for item in self.collectibles if item.node_id != node_id]
        self.hazards = [item for item in self.hazards if item.node_id != node_id]
        self.checkpoints = [item for item in self.checkpoints if item.node_id != node_id]
        self.goals = [item for item in self.goals if item.node_id != node_id]
        if role == "player-spawn":
            self.add_controller(node_id)
            self.follow_camera(node_id)
        elif role == "pickup":
            self.add_collectible(node_id)
        elif role == "hazard":
            self.add_hazard(node_id)
        elif role == "checkpoint":
            self.add_checkpoint(node_id)
        elif role == "goal":
            self.add_goal(node_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "actionMaps": {name: value.to_dict() for name, value in self.action_maps.items()},
            "controllers": [_camel_dict(value) for value in self.controllers],
            "cameras": [_camel_dict(value) for value in self.cameras],
            "collectibles": [_camel_dict(value) for value in self.collectibles],
            "hazards": [_camel_dict(value) for value in self.hazards],
            "checkpoints": [_camel_dict(value) for value in self.checkpoints],
            "goals": [_camel_dict(value) for value in self.goals],
            "enemies": (
                {
                    "spawnPoints": [list(point) for point in self.enemies.spawn_points],
                    "types": [_camel_dict(item) for item in self.enemies.types],
                }
                if self.enemies
                else None
            ),
            "hud": _camel_dict(self.hud) if self.hud else None,
            "timer": _camel_dict(self.timer) if self.timer else None,
            "win": _camel_dict(self.win),
            "lose": _camel_dict(self.lose),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> GameManifest:
        """Load a manifest from its browser-facing representation."""
        values = data or {}
        manifest = cls(
            action_maps={
                name: ActionMap({action: list(inputs) for action, inputs in mapping.items()})
                for name, mapping in (values.get("actionMaps") or {}).items()
            },
            controllers=[
                ThirdPersonController(
                    node_id=item["nodeId"],
                    move_speed=float(item.get("moveSpeed", 5.0)),
                    jump_speed=float(item.get("jumpSpeed", 7.0)),
                    action_map=str(item.get("actionMap", "default")),
                    preset=str(item.get("preset", "simple")),  # type: ignore[arg-type]
                    sprint_mult=float(item.get("sprintMult", item.get("sprint_mult", 2.0))),
                )
                for item in values.get("controllers") or []
            ],
            cameras=[
                CameraFollow(
                    target_id=item["targetId"],
                    distance=float(item.get("distance", 6.0)),
                    height=float(item.get("height", 3.0)),
                    smoothing=float(item.get("smoothing", 0.12)),
                )
                for item in values.get("cameras") or []
            ],
            collectibles=[
                Collectible(
                    node_id=item["nodeId"],
                    value=int(item.get("value", 1)),
                    event=str(item.get("event", "collect")),
                    respawn_seconds=item.get("respawnSeconds"),
                )
                for item in values.get("collectibles") or []
            ],
            hazards=[
                Hazard(
                    node_id=item["nodeId"],
                    damage=int(item.get("damage", 1)),
                    event=str(item.get("event", "hazard")),
                    reset_to_checkpoint=bool(item.get("resetToCheckpoint", True)),
                )
                for item in values.get("hazards") or []
            ],
            checkpoints=[
                Checkpoint(
                    node_id=item["nodeId"],
                    event=str(item.get("event", "checkpoint")),
                )
                for item in values.get("checkpoints") or []
            ],
            goals=[
                Goal(
                    node_id=item["nodeId"],
                    event=str(item.get("event", "goal")),
                    required_score=int(item.get("requiredScore", 0)),
                )
                for item in values.get("goals") or []
            ],
        )
        hud = values.get("hud")
        if hud:
            manifest.hud = HUD(
                show_score=bool(hud.get("showScore", True)),
                show_health=bool(hud.get("showHealth", True)),
                show_timer=bool(hud.get("showTimer", True)),
                title=hud.get("title"),
                description=hud.get("description"),
                controls_hint=hud.get("controlsHint"),
            )
        timer = values.get("timer")
        if timer:
            manifest.timer = Timer(
                seconds=float(timer["seconds"]),
                mode=timer.get("mode", "countdown"),
                start_on_load=bool(timer.get("startOnLoad", True)),
                timeout_event=str(timer.get("timeoutEvent", "timeout")),
            )
        win = values.get("win")
        lose = values.get("lose")
        if win:
            manifest.win = Outcome(
                str(win.get("event", "goal")), str(win.get("message", "You win"))
            )
        if lose:
            manifest.lose = Outcome(
                str(lose.get("event", "timeout")), str(lose.get("message", "You lose"))
            )
        enemies = values.get("enemies")
        if enemies:
            manifest.set_enemies(
                spawn_points=enemies.get("spawnPoints") or [],
                types=enemies.get("types") or [],
            )
        return manifest

    @staticmethod
    def _append(collection: list[Any], value: Any) -> Any:
        collection.append(value)
        return value


Game = GameManifest


def _camel_dict(value: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in asdict(value).items():
        parts = key.split("_")
        result[parts[0] + "".join(part.title() for part in parts[1:])] = item
    return result
