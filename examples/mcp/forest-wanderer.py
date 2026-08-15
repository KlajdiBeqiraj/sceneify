"""Conversational MCP Sceneify example: Bosco dell'Esploratore.

A mossy forest clearing with a playable mage character.

Note: Poly Haven downloads arrive as multi-file glTF (.gltf + .bin + textures).
The viewer loads meshes via `/api/asset?path=...`, which breaks relative texture
URIs — so this example uses KayKit GLB + procedural trees/props, plus a Poly Haven
HDRI for lighting (HDRI is a single file and works fine).

Assets: Poly Haven mossy_forest HDRI (CC0) + KayKit mage (examples/assets/kaykit).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path

from sceneify import Game, Material, Physics, Scene

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".sceneify_cache"
PH = CACHE / "polyhaven"
KAYKIT = "examples/assets/kaykit"

FIXED = Physics(body="fixed", collider="cuboid")
CAPSULE_HALF = 0.4
CAPSULE_RADIUS = 0.3

GROUND = "#3d5c3a"
PATH = "#6b5b45"
MOSS = "#2f4a32"
BARK = "#4a3424"
NEEDLE = "#1f4d2e"
NEEDLE_DARK = "#163821"
ROCK = "#6a655c"
STONE = "#8a8478"
CLOAK = "#3b6ea5"
SKIN = "#e7c6a0"


def _m(
    color: str, *, roughness: float = 0.92, metalness: float = 0.0, opacity: float = 1.0
) -> Material:
    return Material(color=color, roughness=roughness, metalness=metalness, opacity=opacity)


def _box(
    scene: Scene,
    node_id: str,
    *,
    size: Sequence[float],
    position: Sequence[float],
    color: str,
    parent_id: str | None = None,
    rotation: Sequence[float] | None = None,
    physics: Physics | None = FIXED,
    opacity: float = 1.0,
    tags: Sequence[str] | None = None,
) -> None:
    scene.create_primitive(
        node_id,
        "box",
        parent_id=parent_id,
        size=tuple(size),
        position=tuple(position),
        rotation=tuple(rotation) if rotation else None,
        material=_m(color, opacity=opacity),
        physics=physics,
        tags=list(tags or []),
    )


def _sphere(
    scene: Scene,
    node_id: str,
    *,
    radius: float,
    position: Sequence[float],
    color: str,
    parent_id: str | None = None,
    scale: Sequence[float] | None = None,
    tags: Sequence[str] | None = None,
    physics: Physics | None = None,
) -> None:
    scene.create_primitive(
        node_id,
        "sphere",
        parent_id=parent_id,
        radius=radius,
        position=tuple(position),
        scale=tuple(scale) if scale else None,
        material=_m(color),
        physics=physics,
        tags=list(tags or []),
    )


def _fir(
    scene: Scene,
    node_id: str,
    *,
    x: float,
    z: float,
    height: float = 6.0,
    yaw: float = 0.0,
) -> None:
    """Stylized fir from trunk + layered canopies."""
    scene.add_object(
        node_id,
        label="Abete",
        position=(x, 0.0, z),
        rotation=(0.0, yaw, 0.0),
        tags=["tree", "fir"],
    )
    trunk_h = height * 0.22
    trunk_r = max(0.12, height * 0.04)
    _box(
        scene,
        f"{node_id}_trunk",
        parent_id=node_id,
        size=(trunk_r * 2, trunk_h, trunk_r * 2),
        position=(0.0, trunk_h / 2, 0.0),
        color=BARK,
        tags=["tree", "trunk"],
    )
    layers = (
        (height * 0.38, height * 0.42, NEEDLE_DARK),
        (height * 0.30, height * 0.58, NEEDLE),
        (height * 0.22, height * 0.78, NEEDLE),
    )
    for i, (w, y, color) in enumerate(layers):
        _sphere(
            scene,
            f"{node_id}_canopy_{i}",
            parent_id=node_id,
            radius=w / 2,
            position=(0.0, y, 0.0),
            scale=(1.0, 1.35, 1.0),
            color=color,
            tags=["tree", "foliage"],
        )


def _stump(scene: Scene, node_id: str, *, x: float, z: float, yaw: float = 0.0) -> None:
    scene.add_object(
        node_id,
        label="Ceppo",
        position=(x, 0.0, z),
        rotation=(0.0, yaw, 0.0),
        tags=["prop", "stump"],
    )
    _box(
        scene,
        f"{node_id}_body",
        parent_id=node_id,
        size=(0.9, 0.55, 0.9),
        position=(0.0, 0.28, 0.0),
        color=BARK,
    )
    _sphere(
        scene,
        f"{node_id}_top",
        parent_id=node_id,
        radius=0.48,
        position=(0.0, 0.55, 0.0),
        scale=(1.0, 0.25, 1.0),
        color="#5a4030",
        tags=["prop"],
    )


def _rock(
    scene: Scene, node_id: str, *, x: float, z: float, scale: float = 1.0, yaw: float = 0.0
) -> None:
    scene.add_object(
        node_id,
        label="Roccia",
        position=(x, 0.0, z),
        rotation=(0.0, yaw, 0.0),
        tags=["prop", "rock"],
    )
    _sphere(
        scene,
        f"{node_id}_a",
        parent_id=node_id,
        radius=0.45 * scale,
        position=(0.0, 0.28 * scale, 0.0),
        scale=(1.2, 0.7, 1.0),
        color=ROCK,
        physics=FIXED,
        tags=["prop", "rock"],
    )
    _sphere(
        scene,
        f"{node_id}_b",
        parent_id=node_id,
        radius=0.28 * scale,
        position=(0.35 * scale, 0.18 * scale, 0.15 * scale),
        scale=(1.0, 0.65, 0.9),
        color="#5c574f",
        tags=["prop", "rock"],
    )


def _shrine(scene: Scene, node_id: str, *, x: float, z: float) -> None:
    """Simple stone shrine figure (placeholder for a woodland guardian)."""
    scene.add_object(node_id, label="Santuario", position=(x, 0.0, z), tags=["prop", "shrine"])
    _box(
        scene,
        f"{node_id}_base",
        parent_id=node_id,
        size=(1.4, 0.25, 1.4),
        position=(0.0, 0.12, 0.0),
        color=STONE,
    )
    _box(
        scene,
        f"{node_id}_plinth",
        parent_id=node_id,
        size=(0.7, 0.5, 0.7),
        position=(0.0, 0.5, 0.0),
        color="#7a7468",
    )
    scene.create_primitive(
        f"{node_id}_body",
        "capsule",
        parent_id=node_id,
        radius=0.28,
        height=0.7,
        position=(0.0, 1.35, 0.0),
        material=_m("#9a9488"),
        tags=["prop", "shrine"],
    )
    _sphere(
        scene,
        f"{node_id}_head",
        parent_id=node_id,
        radius=0.22,
        position=(0.0, 1.95, 0.0),
        color="#aea89c",
    )


def _add_terrain(scene: Scene) -> None:
    _box(
        scene,
        "ground",
        size=(48.0, 0.25, 48.0),
        position=(0.0, -0.12, 0.0),
        color=GROUND,
        tags=["ground"],
    )
    _box(
        scene,
        "moss_patch",
        size=(18.0, 0.08, 14.0),
        position=(0.0, 0.02, -2.0),
        color=MOSS,
        tags=["ground", "moss"],
    )
    _box(
        scene, "path", size=(3.2, 0.06, 28.0), position=(0.0, 0.04, 2.0), color=PATH, tags=["path"]
    )
    _box(
        scene,
        "clearing",
        size=(10.0, 0.05, 10.0),
        position=(0.0, 0.03, 4.0),
        color="#4a6b42",
        tags=["clearing"],
    )


def _add_forest(scene: Scene) -> None:
    firs = (
        (-8.0, -6.0, 7.5, 20.0),
        (9.0, -4.0, 8.0, -35.0),
        (-10.0, 8.0, 6.5, 110.0),
        (11.0, 10.0, 7.0, -80.0),
        (-6.0, 14.0, 6.0, 45.0),
        (7.0, 16.0, 7.2, -15.0),
        (-14.0, -10.0, 7.5, 0.0),
        (-16.0, -2.0, 6.2, 30.0),
        (-15.0, 6.0, 8.0, 70.0),
        (-13.0, 14.0, 6.8, 120.0),
        (14.0, -12.0, 7.0, 10.0),
        (16.0, -3.0, 8.5, -40.0),
        (15.0, 7.0, 6.5, 90.0),
        (13.0, 15.0, 7.8, -100.0),
        (-4.0, -14.0, 6.0, 15.0),
        (3.0, -15.0, 7.2, -25.0),
        (-9.0, -12.0, 5.5, 55.0),
        (10.0, -14.0, 6.4, -60.0),
    )
    for i, (x, z, h, yaw) in enumerate(firs):
        _fir(scene, f"fir_{i}", x=x, z=z, height=h, yaw=yaw)

    _stump(scene, "stump_clearing", x=-2.8, z=2.2, yaw=40.0)
    _rock(scene, "rocks_west", x=-5.5, z=6.0, scale=1.2, yaw=25.0)
    _rock(scene, "rocks_east", x=5.0, z=1.5, scale=0.9, yaw=-55.0)
    _rock(scene, "rocks_path", x=1.8, z=-3.5, scale=0.7, yaw=10.0)
    _shrine(scene, "shrine", x=0.0, z=-8.0)

    scene.add_annotation(
        "poi_shrine",
        (0.0, 3.0, -8.0),
        label="Santuario del Bosco",
        description="Una figura di pietra veglia sul sentiero.",
    )
    scene.add_annotation(
        "poi_clearing",
        (0.0, 2.2, 4.0),
        label="Radura",
        description="Qui inizia il sentiero. Muovi il mago con WASD.",
    )


def _add_player(scene: Scene) -> None:
    player_y = CAPSULE_HALF + CAPSULE_RADIUS
    mage = Path(KAYKIT) / "mage.glb"
    scene.create_primitive(
        "player",
        "capsule",
        position=(0.0, player_y, 8.0),
        radius=CAPSULE_RADIUS,
        height=CAPSULE_HALF * 2,
        material=_m("#7dd3fc"),
        physics=Physics(body="dynamic", collider="capsule", mass=1),
        tags=["player"],
        renderPrimitive=False,
    )
    if (ROOT / mage).exists():
        # EcctrlPlayer wraps visuals with an extra yaw of π (calibrated for KayKit
        # knight, which faces -Z). The mage faces +Z, so cancel that flip here
        # or the follow camera sits in front of the character.
        scene.add_glb(
            "player_visual",
            mage,
            parent_id="player",
            position=(0.0, -(CAPSULE_HALF + CAPSULE_RADIUS), 0.0),
            rotation=(0.0, math.pi, 0.0),
            scale=(0.78, 0.78, 0.78),
            apply_environment=False,
            visualFor="player",
            animation={
                "autoplay": "Idle",
                "states": {
                    "idle": "Idle",
                    "move": "Walking_A",
                    "run": "Running_A",
                    "jump": "Jump_Full_Short",
                },
                "fadeSeconds": 0.12,
            },
        )
    else:
        scene.create_primitive(
            "player_body",
            "capsule",
            parent_id="player",
            position=(0.0, 0.0, 0.0),
            radius=0.28,
            height=0.7,
            material=_m(CLOAK),
            apply_environment=False,
            tags=["player", "visual"],
        )
        _sphere(
            scene,
            "player_head",
            parent_id="player",
            radius=0.22,
            position=(0.0, 0.55, 0.0),
            color=SKIN,
            tags=["player", "visual"],
        )

    game = Game()
    game.action_map(
        moveForward=["KeyW", "ArrowUp"],
        moveBack=["KeyS", "ArrowDown"],
        moveLeft=["KeyA", "ArrowLeft"],
        moveRight=["KeyD", "ArrowRight"],
        jump=["Space"],
    )
    game.add_controller("player", preset="ecctrl", move_speed=5.0, jump_speed=7.0)
    game.follow_camera("player", distance=7.0, height=3.2)
    game.set_hud(title="Bosco dell'Esploratore", controls_hint="Muovi: WASD · Salta: Spazio")
    scene.set_game(game)


# sceneify:scene-begin
def build_scene() -> Scene:
    scene = Scene("Bosco dell'Esploratore", background="#1a2a1f")
    hdri = PH / "mossy_forest" / "1k" / "mossy_forest_1k.hdr"
    presentation: dict = {
        "grid": False,
        "helpers": False,
        "shadows": True,
        "exposure": 1.05,
        "fog": {"color": "#1a2a1f", "near": 18, "far": 55},
        "camera": {"position": [10, 8, 16], "target": [0, 1.2, 4], "fov": 48},
        "title": "Bosco dell'Esploratore",
        "subtitle": "Una radura muschiosa · WASD per muoverti",
        "ambientIntensity": 0.45,
        "keyLightIntensity": 1.1,
        "environmentPreset": "park",
    }
    if hdri.exists():
        presentation["environmentMap"] = str(hdri.relative_to(ROOT))
    scene.set_presentation(**presentation)
    scene.set_environment(
        bounds_min=(-20.0, 0.0, -20.0),
        bounds_max=(20.0, 14.0, 20.0),
        ground_y=0.0,
        snap=0.5,
    )
    if scene.environment is not None:
        if scene.environment.bounds is not None:
            scene.environment.bounds.visible = False
        if scene.environment.ground is not None:
            scene.environment.ground.visible = False
        if scene.environment.snap_grid is not None:
            scene.environment.snap_grid.visible = False
        scene.environment.show_axes = False

    _add_terrain(scene)
    _add_forest(scene)
    _add_player(scene)
    return scene


# sceneify:scene-end


if __name__ == "__main__":
    build_scene().run(project_root=ROOT)
