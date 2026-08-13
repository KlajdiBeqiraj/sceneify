"""Conversational MCP Sceneify example: Fiera del Fiume Biforcuto.

A medieval river fair (not a fake city of cloned "houses").
Layout is intentional:
  - River spine north-south
  - Neutral stone bridge + treaty plaza at the center
  - West bank: Red Wolf tavern & food market
  - East bank: Blue Owl crafts, games & stage
  - North/south gates on the main road

Assets: OS3A medieval-fair GLBs (Polygonal Mind, CC0).
HDRI: Lilienstein from Poly Haven (CC0).
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Sequence

from sceneify import Material, Physics, Scene

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".sceneify_cache"
FAIR = CACHE / "os3a" / "pm-medieval-fair"
FIXED = Physics(body="fixed", collider="cuboid")

WOOD = ("#6b3f24", "#8b5a2b", "#5a3218", "#a0673a")
RED = "#b91c1c"
BLUE = "#1d4ed8"
RIVER = "#1f6f9e"
GROUND = "#5a5346"
PATH = "#7a7060"
PLAZA = "#8a8374"
BANK = "#4a6b3a"
STONE = "#6f685c"


def _m(color: str, *, roughness: float = 0.9, metalness: float = 0.0, opacity: float = 1.0) -> Material:
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
    tags: Sequence[str] | None = None,
) -> None:
    scene.create_primitive(
        node_id,
        "sphere",
        parent_id=parent_id,
        radius=radius,
        position=tuple(position),
        material=_m(color),
        physics=FIXED,
        tags=list(tags or []),
    )


def _poi(scene: Scene, node_id: str, position: Sequence[float], label: str, description: str) -> None:
    scene.add_annotation(node_id, tuple(position), label=label, description=description)


def _glb_bounds(path: Path) -> tuple[list[float], list[float], list[float]] | None:
    data = path.read_bytes()
    chunk_len, chunk_type = struct.unpack_from("<I4s", data, 12)
    if chunk_type != b"JSON":
        return None
    js = json.loads(data[20 : 20 + chunk_len])
    mins: list[list[float]] = []
    maxs: list[list[float]] = []
    for acc in js.get("accessors", []):
        if acc.get("type") == "VEC3" and "min" in acc and "max" in acc:
            mins.append(acc["min"])
            maxs.append(acc["max"])
    if not mins:
        return None
    gmin = [min(m[i] for m in mins) for i in range(3)]
    gmax = [max(m[i] for m in maxs) for i in range(3)]
    ext = [gmax[i] - gmin[i] for i in range(3)]
    return gmin, gmax, ext


def _place_glb(
    scene: Scene,
    node_id: str,
    path: Path,
    *,
    position: Sequence[float],
    yaw: float = 0.0,
    target_height: float = 4.0,
    scale_mult: float = 1.0,
    tags: Sequence[str] | None = None,
) -> bool:
    """Place a GLB with height-normalized scale and bottom on the ground plane."""
    if not path.exists():
        return False
    bounds = _glb_bounds(path)
    if bounds is None:
        return False
    gmin, _gmax, ext = bounds
    height = max(ext[1], 0.001)
    s = (target_height / height) * scale_mult
    y = -gmin[1] * s
    scene.add_glb(
        node_id,
        path,
        position=(float(position[0]), y, float(position[2])),
        rotation=(0.0, yaw, 0.0),
        scale=(s, s, s),
        tags=list(tags or []),
    )
    return True


def _wolf_banner(scene: Scene, root: str, *, x: float, z: float, scale: float = 1.0, yaw: float = 0.0) -> None:
    scene.add_object(root, label="Stemma Lupo Rosso", position=(x, 0.0, z), rotation=(0.0, yaw, 0.0), tags=["banner", "red", "wolf"])
    s = scale
    _box(scene, f"{root}_pole", parent_id=root, size=(0.12 * s, 3.2 * s, 0.12 * s), position=(0, 1.6 * s, 0), color=WOOD[0])
    _box(scene, f"{root}_cloth", parent_id=root, size=(1.4 * s, 1.8 * s, 0.08 * s), position=(0.75 * s, 2.4 * s, 0), color=RED)
    _sphere(scene, f"{root}_head", parent_id=root, radius=0.28 * s, position=(0.75 * s, 2.55 * s, 0.12 * s), color="#7f1d1d")
    _box(scene, f"{root}_snout", parent_id=root, size=(0.22 * s, 0.14 * s, 0.28 * s), position=(0.75 * s, 2.35 * s, 0.28 * s), color="#991b1b")
    _box(scene, f"{root}_ear_l", parent_id=root, size=(0.12 * s, 0.22 * s, 0.08 * s), position=(0.55 * s, 2.85 * s, 0.12 * s), color="#450a0a")
    _box(scene, f"{root}_ear_r", parent_id=root, size=(0.12 * s, 0.22 * s, 0.08 * s), position=(0.95 * s, 2.85 * s, 0.12 * s), color="#450a0a")
    _sphere(scene, f"{root}_eye_l", parent_id=root, radius=0.05 * s, position=(0.62 * s, 2.6 * s, 0.32 * s), color="#fef08a")
    _sphere(scene, f"{root}_eye_r", parent_id=root, radius=0.05 * s, position=(0.88 * s, 2.6 * s, 0.32 * s), color="#fef08a")


def _owl_banner(scene: Scene, root: str, *, x: float, z: float, scale: float = 1.0, yaw: float = 0.0) -> None:
    scene.add_object(root, label="Stemma Gufo Blu", position=(x, 0.0, z), rotation=(0.0, yaw, 0.0), tags=["banner", "blue", "owl"])
    s = scale
    _box(scene, f"{root}_pole", parent_id=root, size=(0.12 * s, 3.2 * s, 0.12 * s), position=(0, 1.6 * s, 0), color=WOOD[1])
    _box(scene, f"{root}_cloth", parent_id=root, size=(1.4 * s, 1.8 * s, 0.08 * s), position=(0.75 * s, 2.4 * s, 0), color=BLUE)
    _sphere(scene, f"{root}_body", parent_id=root, radius=0.32 * s, position=(0.75 * s, 2.4 * s, 0.12 * s), color="#1e3a8a")
    _sphere(scene, f"{root}_eye_l", parent_id=root, radius=0.12 * s, position=(0.6 * s, 2.55 * s, 0.32 * s), color="#e0f2fe")
    _sphere(scene, f"{root}_eye_r", parent_id=root, radius=0.12 * s, position=(0.9 * s, 2.55 * s, 0.32 * s), color="#e0f2fe")
    _sphere(scene, f"{root}_pupil_l", parent_id=root, radius=0.05 * s, position=(0.6 * s, 2.55 * s, 0.42 * s), color="#0f172a")
    _sphere(scene, f"{root}_pupil_r", parent_id=root, radius=0.05 * s, position=(0.9 * s, 2.55 * s, 0.42 * s), color="#0f172a")
    _box(scene, f"{root}_beak", parent_id=root, size=(0.12 * s, 0.1 * s, 0.16 * s), position=(0.75 * s, 2.28 * s, 0.38 * s), color="#f59e0b")
    _box(scene, f"{root}_tuft_l", parent_id=root, size=(0.1 * s, 0.22 * s, 0.08 * s), position=(0.52 * s, 2.8 * s, 0.1 * s), color="#172554")
    _box(scene, f"{root}_tuft_r", parent_id=root, size=(0.1 * s, 0.22 * s, 0.08 * s), position=(0.98 * s, 2.8 * s, 0.1 * s), color="#172554")


def _add_terrain(scene: Scene) -> None:
    """Ground, river, banks, and roads that form the town skeleton."""
    _box(scene, "ground", size=(80.0, 0.25, 90.0), position=(0.0, -0.12, 0.0), color=GROUND, tags=["ground"])

    # River runs north-south through the center (narrower near bridge, wider at docks).
    _box(scene, "river", size=(5.0, 0.35, 100.0), position=(0.0, -0.28, 0.0), color=RIVER, opacity=0.92, tags=["river", "water"])
    _box(scene, "bank_west", size=(1.4, 0.18, 100.0), position=(-3.2, -0.04, 0.0), color=BANK, tags=["riverbank"])
    _box(scene, "bank_east", size=(1.4, 0.18, 100.0), position=(3.2, -0.04, 0.0), color=BANK, tags=["riverbank"])

    # Main road along both banks (parallel to river).
    _box(scene, "road_west", size=(5.5, 0.08, 72.0), position=(-7.0, 0.02, 0.0), color=PATH, tags=["path", "road"])
    _box(scene, "road_east", size=(5.5, 0.08, 72.0), position=(7.0, 0.02, 0.0), color=PATH, tags=["path", "road"])

    # Bridge approaches (east-west spurs).
    _box(scene, "approach_west", size=(8.0, 0.08, 5.0), position=(-8.0, 0.03, 0.0), color=PLAZA, tags=["path"])
    _box(scene, "approach_east", size=(8.0, 0.08, 5.0), position=(8.0, 0.03, 0.0), color=PLAZA, tags=["path"])

    # District plazas.
    _box(scene, "plaza_treaty", size=(12.0, 0.1, 12.0), position=(0.0, 0.04, 0.0), color=PLAZA, tags=["plaza", "neutral"])
    _box(scene, "plaza_wolf", size=(14.0, 0.08, 16.0), position=(-14.0, 0.03, -6.0), color="#6e6558", tags=["plaza", "red"])
    _box(scene, "plaza_owl", size=(14.0, 0.08, 16.0), position=(14.0, 0.03, 6.0), color="#5e6670", tags=["plaza", "blue"])

    # Wooden dock pads by the river (south of bridge).
    _box(scene, "dock_west", size=(3.5, 0.22, 8.0), position=(-4.5, 0.08, 14.0), color=WOOD[0], tags=["dock", "red"])
    _box(scene, "dock_east", size=(3.5, 0.22, 8.0), position=(4.5, 0.08, 14.0), color=WOOD[1], tags=["dock", "blue"])

    _poi(
        scene,
        "poi_river",
        (0.0, 1.8, -30.0),
        "Fiume Argentato",
        "Corre da nord a sud e divide le due rive rivali. Solo il ponte e neutro.",
    )


def _add_bridge(scene: Scene) -> None:
    scene.add_object("bridge", label="Ponte del Confine", position=(0.0, 0.0, 0.0), tags=["bridge", "landmark", "neutral"])
    _box(scene, "bridge_deck", parent_id="bridge", size=(10.0, 0.35, 5.0), position=(0.0, 0.55, 0.0), color=PLAZA, tags=["bridge"])
    _box(scene, "bridge_rail_n", parent_id="bridge", size=(10.0, 0.55, 0.25), position=(0.0, 0.95, -2.35), color=STONE)
    _box(scene, "bridge_rail_s", parent_id="bridge", size=(10.0, 0.55, 0.25), position=(0.0, 0.95, 2.35), color=STONE)
    for i, x in enumerate((-3.2, -1.1, 1.1, 3.2)):
        _box(scene, f"bridge_pier_{i}", parent_id="bridge", size=(0.75, 1.15, 1.5), position=(x, 0.15, 0.0), color="#5c564c")
    # Split crest: red west half, blue east half.
    _box(scene, "bridge_crest_red", parent_id="bridge", size=(0.18, 1.5, 0.9), position=(-0.4, 1.45, 0.0), color=RED)
    _box(scene, "bridge_crest_blue", parent_id="bridge", size=(0.18, 1.5, 0.9), position=(0.4, 1.45, 0.0), color=BLUE)
    _poi(
        scene,
        "poi_bridge",
        (0.0, 2.6, 0.0),
        "Ponte del Confine",
        "Trattato delle Due Rive: qui Lupo e Gufo si incontrano senza armi. Centro della fiera.",
    )


def _add_gates(scene: Scene) -> None:
    """City gates close the north/south road axes."""
    _place_glb(
        scene,
        "gate_north",
        FAIR / "medieval-fair-016" / "Fair_Entry.glb",
        position=(0.0, 0.0, -36.0),
        yaw=0.0,
        target_height=7.2,
        scale_mult=0.75,
        tags=["gate", "landmark", "north"],
    )
    _poi(
        scene,
        "poi_gate_north",
        (0.0, 5.5, -36.0),
        "Porta Settentrionale",
        "Ingresso principale della fiera. Da qui arrivano carri e pellegrini.",
    )

    _place_glb(
        scene,
        "gate_south",
        FAIR / "medieval-fair-015" / "FairSecondaryEntrance.glb",
        position=(0.0, 0.0, 36.0),
        yaw=180.0,
        target_height=6.2,
        tags=["gate", "landmark", "south"],
    )
    _poi(
        scene,
        "poi_gate_south",
        (0.0, 4.8, 36.0),
        "Porta Meridionale",
        "Uscita verso i campi. Usata dai mercanti che lasciano la fiera a sera.",
    )

    # Wayfinding signs near bridge approaches.
    _place_glb(
        scene,
        "sign_west_approach",
        FAIR / "medieval-fair-026" / "SignPost.glb",
        position=(-9.5, 0.0, -3.5),
        yaw=90.0,
        target_height=2.8,
        tags=["prop", "sign", "red"],
    )
    _place_glb(
        scene,
        "sign_east_approach",
        FAIR / "medieval-fair-026" / "SignPost.glb",
        position=(9.5, 0.0, 3.5),
        yaw=-90.0,
        target_height=2.8,
        tags=["prop", "sign", "blue"],
    )


def _add_red_wolf_district(scene: Scene) -> None:
    """West bank: tavern, food stalls, beer store, riverside dock."""
    # Tavern anchors the district — faces the plaza / bridge.
    _place_glb(
        scene,
        "tavern_wolf",
        FAIR / "medieval-fair-032" / "Tabern.glb",
        position=(-16.0, 0.0, -2.0),
        yaw=90.0,
        target_height=5.4,
        tags=["building", "tavern", "red"],
    )
    _poi(
        scene,
        "poi_tavern",
        (-16.0, 4.8, -2.0),
        "Locanda del Lupo Rosso",
        "Cuore della riva ovest. Qui si beve birra di fiume e si fanno affari rumorosi.",
    )

    # Food market row facing the west road (south of tavern).
    food_row = (
        ("stall_bread", "medieval-fair-007", "Booth_Food01.glb", (-12.5, -12.0), "Bottega del Pane", "Pane caldo e focacce per i viandanti."),
        ("stall_spices", "medieval-fair-008", "Booth_Food02.glb", (-17.5, -12.0), "Bottega delle Spezie", "Sale, pepe e erbe dal sud. Odore forte sulla piazza."),
    )
    for node_id, remote, filename, (x, z), label, desc in food_row:
        _place_glb(
            scene,
            node_id,
            FAIR / remote / filename,
            position=(x, 0.0, z),
            yaw=90.0,
            target_height=3.6,
            tags=["stall", "food", "red", "market"],
        )
        _poi(scene, f"poi_{node_id}", (x, 3.4, z), label, desc)

    # Beer mountain + barrels behind the tavern (storage / cellar yard).
    _place_glb(
        scene,
        "beer_store",
        FAIR / "medieval-fair-004" / "Barrel_Beer_Mountain.glb",
        position=(-21.0, 0.0, 2.5),
        yaw=20.0,
        target_height=2.4,
        tags=["prop", "storage", "red"],
    )
    _poi(
        scene,
        "poi_beer",
        (-21.0, 2.8, 2.5),
        "Cantina del Lupo",
        "Pile di botti dietro la locanda. La birra arriva dal molo ovest.",
    )

    barrel = FAIR / "medieval-fair-003" / "Barrel.glb"
    if barrel.exists():
        for i, (x, z) in enumerate(((-19.5, 4.0), (-20.2, 4.8), (-18.8, 4.5))):
            scene.add_glb(
                f"barrel_wolf_{i}",
                barrel,
                position=(x, 0.0, z),
                rotation=(0.0, i * 35.0, 0.0),
                scale=(1.0, 1.0, 1.0),
                tags=["prop", "red"],
            )

    # Cart on the dock approach — goods coming off the river.
    _place_glb(
        scene,
        "cart_dock_west",
        FAIR / "medieval-fair-011" / "Cart.glb",
        position=(-6.5, 0.0, 12.0),
        yaw=10.0,
        target_height=1.8,
        tags=["prop", "cart", "red", "dock"],
    )

    # Raised platform for tavern outdoor seating / announcements.
    _place_glb(
        scene,
        "platform_wolf",
        FAIR / "medieval-fair-035" / "WoodPlatform.glb",
        position=(-12.0, 0.0, 4.0),
        yaw=0.0,
        target_height=2.2,
        tags=["platform", "red"],
    )

    # Flag line along the west road edge facing the river.
    _place_glb(
        scene,
        "flags_wolf",
        FAIR / "medieval-fair-017" / "Fair_Flags_Line.glb",
        position=(-5.2, 0.0, -8.0),
        yaw=90.0,
        target_height=3.0,
        scale_mult=0.4,
        tags=["banner", "red"],
    )

    for i, z in enumerate((-18.0, -6.0, 8.0, 20.0)):
        _wolf_banner(scene, f"wolf_banner_{i}", x=-5.0, z=z, scale=0.95, yaw=90.0)

    _wolf_banner(scene, "wolf_plaza_banner", x=-10.0, z=0.0, scale=1.35, yaw=90.0)

    # Street lamps along west road.
    for i, z in enumerate((-22.0, 10.0)):
        _place_glb(
            scene,
            f"lamp_wolf_{i}",
            FAIR / "medieval-fair-019" / "Lamp.glb",
            position=(-5.0, 0.0, z),
            yaw=0.0,
            target_height=3.0,
            tags=["prop", "lamp", "red"],
        )

    _poi(
        scene,
        "poi_wolf_district",
        (-14.0, 5.2, -6.0),
        "Riva del Lupo Rosso",
        "Cibo, birra e locanda. La riva ovest vive di osteria e mercato alimentare.",
    )
    _poi(
        scene,
        "poi_dock_west",
        (-4.5, 1.6, 14.0),
        "Molo Ovest",
        "Qui scaricano grano e botti per la Locanda del Lupo.",
    )


def _add_blue_owl_district(scene: Scene) -> None:
    """East bank: crafts, games, covered market, stage."""
    # Covered market canopy as the district landmark (north of plaza).
    _place_glb(
        scene,
        "covered_market",
        FAIR / "medieval-fair-024" / "Roof.glb",
        position=(15.0, 0.0, -4.0),
        yaw=-90.0,
        target_height=4.2,
        tags=["building", "market", "blue"],
    )
    _poi(
        scene,
        "poi_covered_market",
        (15.0, 4.0, -4.0),
        "Mercato Coperto del Gufo",
        "Tetto comune per i mercanti della riva est. Qui si tratta di stoffe e oggetti.",
    )

    # Craft / wearables stall facing the east road.
    _place_glb(
        scene,
        "stall_tailor",
        FAIR / "medieval-fair-010" / "Booth_Wearables.glb",
        position=(12.5, 0.0, 10.0),
        yaw=-90.0,
        target_height=3.7,
        tags=["stall", "craft", "blue", "market"],
    )
    _poi(
        scene,
        "poi_tailor",
        (12.5, 3.5, 10.0),
        "Sartoria del Gufo",
        "Mantelli, cappelli e stemmi azzurri. Il mestiere quieto della riva est.",
    )

    # Games booth south-east of the crafts row.
    _place_glb(
        scene,
        "stall_games",
        FAIR / "medieval-fair-009" / "Booth_Pretzelgame.glb",
        position=(17.5, 0.0, 12.0),
        yaw=-90.0,
        target_height=3.5,
        tags=["stall", "games", "blue"],
    )
    _poi(
        scene,
        "poi_games",
        (17.5, 3.4, 12.0),
        "Giochi del Gufo",
        "Tiri, scommesse leggere e risate. Attrazione della sera sulla riva blu.",
    )

    # Second tavern as quieter owl inn (library/meeting vibe via placement north).
    _place_glb(
        scene,
        "tavern_owl",
        FAIR / "medieval-fair-032" / "Tabern.glb",
        position=(18.0, 0.0, 2.0),
        yaw=-90.0,
        target_height=5.0,
        scale_mult=0.92,
        tags=["building", "tavern", "blue"],
    )
    _poi(
        scene,
        "poi_owl_inn",
        (18.0, 4.6, 2.0),
        "Locanda del Gufo Blu",
        "Piu raccolta della sorella rossa. Qui si parla piano e si vendono mappe.",
    )

    # Stage platform for proclamations (faces west toward bridge / river).
    _place_glb(
        scene,
        "stage_owl",
        FAIR / "medieval-fair-035" / "WoodPlatform.glb",
        position=(11.0, 0.0, -10.0),
        yaw=180.0,
        target_height=2.6,
        tags=["platform", "stage", "blue"],
    )
    _poi(
        scene,
        "poi_stage",
        (11.0, 2.8, -10.0),
        "Palco delle Proclamazioni",
        "Da qui il Gufo annuncia regole della fiera e accordi col Lupo.",
    )

    # Storage barrels near the east dock.
    _place_glb(
        scene,
        "barrels_owl",
        FAIR / "medieval-fair-004" / "Barrel_Beer_Mountain.glb",
        position=(21.0, 0.0, 8.0),
        yaw=-25.0,
        target_height=2.2,
        tags=["prop", "storage", "blue"],
    )
    barrel = FAIR / "medieval-fair-003" / "Barrel.glb"
    if barrel.exists():
        for i, (x, z) in enumerate(((6.2, 16.0), (6.8, 16.6), (5.8, 17.0))):
            scene.add_glb(
                f"barrel_owl_{i}",
                barrel,
                position=(x, 0.0, z),
                rotation=(0.0, i * 40.0, 0.0),
                scale=(1.0, 1.0, 1.0),
                tags=["prop", "blue", "dock"],
            )

    _place_glb(
        scene,
        "cart_dock_east",
        FAIR / "medieval-fair-011" / "Cart.glb",
        position=(6.5, 0.0, 11.5),
        yaw=-15.0,
        target_height=1.8,
        tags=["prop", "cart", "blue", "dock"],
    )

    _place_glb(
        scene,
        "flags_owl",
        FAIR / "medieval-fair-017" / "Fair_Flags_Line.glb",
        position=(5.2, 0.0, 8.0),
        yaw=-90.0,
        target_height=3.0,
        scale_mult=0.4,
        tags=["banner", "blue"],
    )

    for i, z in enumerate((-18.0, -6.0, 8.0, 20.0)):
        _owl_banner(scene, f"owl_banner_{i}", x=5.0, z=z, scale=0.95, yaw=-90.0)

    _owl_banner(scene, "owl_plaza_banner", x=10.0, z=0.0, scale=1.35, yaw=-90.0)

    for i, z in enumerate((-22.0, 10.0)):
        _place_glb(
            scene,
            f"lamp_owl_{i}",
            FAIR / "medieval-fair-019" / "Lamp.glb",
            position=(5.0, 0.0, z),
            yaw=0.0,
            target_height=3.0,
            tags=["prop", "lamp", "blue"],
        )

    _poi(
        scene,
        "poi_owl_district",
        (14.0, 5.2, 6.0),
        "Riva del Gufo Blu",
        "Mestieri, giochi e mercato coperto. La riva est e piu ordinata e cerimoniosa.",
    )
    _poi(
        scene,
        "poi_dock_east",
        (4.5, 1.6, 14.0),
        "Molo Est",
        "Arrivano stoffe e merci fini per la Sartoria e il Mercato Coperto.",
    )


def _add_treaty_plaza_props(scene: Scene) -> None:
    """Shared center props around the bridge — neutral ground."""
    # Floor tiles hint (if present) under plaza corners.
    floor = FAIR / "medieval-fair-018" / "Floor.glb"
    if floor.exists():
        for i, (x, z) in enumerate(((-3.5, -3.5), (3.5, -3.5), (-3.5, 3.5), (3.5, 3.5))):
            _place_glb(
                scene,
                f"plaza_floor_{i}",
                floor,
                position=(x, 0.0, z),
                yaw=i * 90.0,
                target_height=0.35,
                scale_mult=1.2,
                tags=["plaza", "neutral"],
            )

    _poi(
        scene,
        "poi_treaty",
        (0.0, 3.2, -6.0),
        "Piazza del Trattato",
        "Spazio neutro intorno al ponte. Nessuna fazione puo chiudere il passaggio.",
    )


# sceneify:scene-begin
def build_scene() -> Scene:
    scene = Scene("Fiera del Fiume Biforcuto", background="#87a7c4")
    hdri = CACHE / "polyhaven" / "lilienstein" / "1k" / "lilienstein_1k.hdr"
    presentation: dict = {
        "grid": False,
        "helpers": False,
        "shadows": True,
        "exposure": 1.05,
        "fog": {"color": "#a8bdd0", "near": 40, "far": 120},
        "camera": {"position": [22, 16, 28], "target": [0, 2.0, 0], "fov": 48},
        "title": "Fiera del Fiume Biforcuto",
        "subtitle": "Lupo Rosso (ovest) · Gufo Blu (est) · Ponte neutro",
        "ambientIntensity": 0.55,
        "keyLightIntensity": 1.25,
        "environmentPreset": "sunset",
    }
    if hdri.exists():
        presentation["environmentMap"] = str(hdri.relative_to(ROOT))
    scene.set_presentation(**presentation)
    scene.set_environment(
        bounds_min=(-40.0, 0.0, -42.0),
        bounds_max=(40.0, 16.0, 42.0),
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
    _add_bridge(scene)
    _add_gates(scene)
    _add_treaty_plaza_props(scene)
    _add_red_wolf_district(scene)
    _add_blue_owl_district(scene)
    return scene


# sceneify:scene-end


if __name__ == "__main__":
    build_scene().run(project_root=ROOT)
