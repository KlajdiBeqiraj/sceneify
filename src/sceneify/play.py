"""Character play helper: movement preset plus assignable objectives."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from sceneify.experience import CHARACTER_PRESETS, ExperienceManifest, Objective
from sceneify.game import GameManifest

if TYPE_CHECKING:
    from sceneify.scene import Scene

CharacterPreset = Literal["third_person", "first_person", "topdown"]
ObjectiveKind = Literal["collect", "reach", "survive", "callback"]


class CharacterPlay:
    """Returned by ``scene.character()`` for HUD and objectives."""

    def __init__(self, scene: Scene) -> None:
        self.scene = scene

    def hud(self, **options: Any) -> None:
        game = self._game()
        mapped = dict(options)
        if "hint" in mapped and "controls_hint" not in mapped:
            mapped["controls_hint"] = mapped.pop("hint")
        game.set_hud(**{key: value for key, value in mapped.items() if key in {
            "show_score",
            "show_health",
            "show_timer",
            "title",
            "description",
            "controls_hint",
        }})
        if "win_message" in options or "lose_message" in options:
            game.outcomes(
                win_message=str(options.get("win_message", game.win.message)),
                lose_message=str(options.get("lose_message", game.lose.message)),
            )
        self._commit_game(game)

    def objective(self, kind: ObjectiveKind, **options: Any) -> Objective:
        if kind not in {"collect", "reach", "survive", "callback"}:
            raise ValueError(f"Unsupported objective: {kind!r}")
        objective = Objective(
            kind=kind,
            need=options.get("need"),
            node_id=options.get("node_id"),
            seconds=options.get("seconds"),
        )
        game = self._game()
        if kind == "collect":
            if not game.collectibles:
                for node in self.scene._primitives.values():
                    if "pickup" in node.tags:
                        game.add_collectible(node.id)
            need = int(options.get("need") or max(1, len(game.collectibles)))
            if game.goals:
                game.goals[0].required_score = need
            objective.need = need
        elif kind == "reach":
            node_id = options.get("node_id")
            if not isinstance(node_id, str) or not node_id:
                raise ValueError("reach objective requires node_id")
            if not any(item.node_id == node_id for item in game.goals):
                game.add_goal(node_id, required_score=int(options.get("need") or 0))
        elif kind == "survive":
            seconds = float(options.get("seconds") or 60)
            game.set_timer(seconds)
            objective.seconds = seconds
        self._commit_game(game, extra_objective=objective)
        return objective

    def _game(self) -> GameManifest:
        raw = self.scene._experience
        character = raw.get("character") if isinstance(raw, dict) else None
        return GameManifest.from_dict(character if isinstance(character, dict) else None)

    def _commit_game(self, game: GameManifest, *, extra_objective: Objective | None = None) -> None:
        raw = self.scene._experience if isinstance(self.scene._experience, dict) else {}
        preset = str(raw.get("camera", {}).get("mode") or "third_person")
        if preset not in CHARACTER_PRESETS:
            preset = "third_person"
        manifest = ExperienceManifest.character_world(
            game.to_dict(),
            preset=preset,  # type: ignore[arg-type]
            title=game.hud.title if game.hud else None,
        )
        existing = ExperienceManifest.from_dict(raw).objectives if raw else []
        manifest.objectives = list(existing)
        if extra_objective is not None:
            manifest.objectives = [
                item for item in manifest.objectives if item.kind != extra_objective.kind
            ]
            manifest.objectives.append(extra_objective)
        manifest.touch()
        self.scene.set_experience(manifest)
