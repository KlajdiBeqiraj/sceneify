"""Conversational MCP Sceneify example: My First Conversational Room.

Fantasy medieval village split by a river: Red Wolf district vs Blue Owl district.
Assets: procedural primitives (Poly Haven CC0 unused here).
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from sceneify import Material, Physics, Scene

FIXED = Physics(body="fixed", collider="cuboid")

# Wall / wood / roof palettes for variety
STONE = ("#6d6458", "#7a7164", "#5c5348", "#8a8070", "#4f463c")
PLASTER = ("#d8c4a8", "#cbb79a", "#e2d2b6", "#b9a68a", "#f0e2c8")
WOOD = ("#6b3f24", "#8b5a2b", "#5a3218", "#a0673a", "#4a2810")
ROOF_RED = ("#8b2e2e", "#a33a3a", "#6e2222", "#b04545", "#7a2a2a")
ROOF_BLUE = ("#2f4f8f", "#3a5fa8", "#243f72", "#4a72b8", "#1f355f")
RED_BANNER = "#b91c1c"
BLUE_BANNER = "#1d4ed8"
RIVER = "#1f6f9e"
GROUND = "#5a5346"
PATH = "#7a7060"
BRIDGE = "#8a8374"


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


def _add_ground_and_river(scene: Scene) -> None:
    # Cobblestone plaza / village floor
    _box(
        scene,
        "ground",
        size=(96.0, 0.25, 96.0),
        position=(0.0, -0.12, 0.0),
        color=GROUND,
        tags=["ground", "city"],
    )
    # Dirt paths flanking the river
    _box(
        scene,
        "path_west",
        size=(6.0, 0.08, 70.0),
        position=(-5.5, 0.02, 0.0),
        color=PATH,
        tags=["path"],
    )
    _box(
        scene,
        "path_east",
        size=(6.0, 0.08, 70.0),
        position=(5.5, 0.02, 0.0),
        color=PATH,
        tags=["path"],
    )
    # River starts outside the village and cuts through the center (along Z)
    _box(
        scene,
        "river",
        size=(4.2, 0.35, 110.0),
        position=(0.0, -0.28, 0.0),
        color=RIVER,
        opacity=0.92,
        tags=["river", "water"],
    )
    # Soft river banks
    _box(
        scene,
        "bank_west",
        size=(1.2, 0.2, 110.0),
        position=(-2.7, -0.05, 0.0),
        color="#4a6b3a",
        tags=["riverbank"],
    )
    _box(
        scene,
        "bank_east",
        size=(1.2, 0.2, 110.0),
        position=(2.7, -0.05, 0.0),
        color="#4a6b3a",
        tags=["riverbank"],
    )


def _add_bridge(scene: Scene) -> None:
    # Stone bridge spanning the river — divides red (west) from blue (east)
    scene.add_object(
        "bridge",
        label="Ponte del Confine",
        position=(0.0, 0.0, 0.0),
        tags=["bridge", "landmark"],
    )
    _box(
        scene,
        "bridge_deck",
        parent_id="bridge",
        size=(9.0, 0.35, 4.5),
        position=(0.0, 0.55, 0.0),
        color=BRIDGE,
        tags=["bridge"],
    )
    _box(
        scene,
        "bridge_rail_n",
        parent_id="bridge",
        size=(9.0, 0.55, 0.25),
        position=(0.0, 0.95, -2.1),
        color="#6f685c",
    )
    _box(
        scene,
        "bridge_rail_s",
        parent_id="bridge",
        size=(9.0, 0.55, 0.25),
        position=(0.0, 0.95, 2.1),
        color="#6f685c",
    )
    for i, x in enumerate((-2.8, -1.0, 1.0, 2.8)):
        _box(
            scene,
            f"bridge_pier_{i}",
            parent_id="bridge",
            size=(0.7, 1.1, 1.4),
            position=(x, 0.15, 0.0),
            color="#5c564c",
        )
    # Center divider crest on the bridge
    _box(
        scene,
        "bridge_crest_red",
        parent_id="bridge",
        size=(0.15, 1.4, 0.8),
        position=(-0.35, 1.4, 0.0),
        color=RED_BANNER,
    )
    _box(
        scene,
        "bridge_crest_blue",
        parent_id="bridge",
        size=(0.15, 1.4, 0.8),
        position=(0.35, 1.4, 0.0),
        color=BLUE_BANNER,
    )
    scene.add_annotation(
        "poi_bridge",
        (0.0, 2.4, 0.0),
        label="Ponte del Confine",
        description="Divide la Citta del Lupo Rosso dalla Citta del Gufo Blu",
    )


def _wolf_emblem(scene: Scene, root: str, *, x: float, z: float, scale: float = 1.0) -> None:
    """Stylized red-wolf coat of arms on a banner pole."""
    scene.add_object(
        root,
        label="Stemma Lupo Rosso",
        position=(x, 0.0, z),
        tags=["banner", "red", "wolf"],
    )
    s = scale
    _box(scene, f"{root}_pole", parent_id=root, size=(0.12 * s, 3.2 * s, 0.12 * s), position=(0, 1.6 * s, 0), color=WOOD[0])
    _box(scene, f"{root}_cloth", parent_id=root, size=(1.4 * s, 1.8 * s, 0.08 * s), position=(0.75 * s, 2.4 * s, 0), color=RED_BANNER)
    # Wolf head silhouette
    _sphere(scene, f"{root}_head", parent_id=root, radius=0.28 * s, position=(0.75 * s, 2.55 * s, 0.12 * s), color="#7f1d1d")
    _box(scene, f"{root}_snout", parent_id=root, size=(0.22 * s, 0.14 * s, 0.28 * s), position=(0.75 * s, 2.35 * s, 0.28 * s), color="#991b1b")
    _box(scene, f"{root}_ear_l", parent_id=root, size=(0.12 * s, 0.22 * s, 0.08 * s), position=(0.55 * s, 2.85 * s, 0.12 * s), color="#450a0a")
    _box(scene, f"{root}_ear_r", parent_id=root, size=(0.12 * s, 0.22 * s, 0.08 * s), position=(0.95 * s, 2.85 * s, 0.12 * s), color="#450a0a")
    _sphere(scene, f"{root}_eye_l", parent_id=root, radius=0.05 * s, position=(0.62 * s, 2.6 * s, 0.32 * s), color="#fef08a")
    _sphere(scene, f"{root}_eye_r", parent_id=root, radius=0.05 * s, position=(0.88 * s, 2.6 * s, 0.32 * s), color="#fef08a")


def _owl_emblem(scene: Scene, root: str, *, x: float, z: float, scale: float = 1.0) -> None:
    """Stylized blue-owl coat of arms on a banner pole."""
    scene.add_object(
        root,
        label="Stemma Gufo Blu",
        position=(x, 0.0, z),
        tags=["banner", "blue", "owl"],
    )
    s = scale
    _box(scene, f"{root}_pole", parent_id=root, size=(0.12 * s, 3.2 * s, 0.12 * s), position=(0, 1.6 * s, 0), color=WOOD[1])
    _box(scene, f"{root}_cloth", parent_id=root, size=(1.4 * s, 1.8 * s, 0.08 * s), position=(0.75 * s, 2.4 * s, 0), color=BLUE_BANNER)
    # Owl body + big eyes + beak
    _sphere(scene, f"{root}_body", parent_id=root, radius=0.32 * s, position=(0.75 * s, 2.4 * s, 0.12 * s), color="#1e3a8a")
    _sphere(scene, f"{root}_eye_l", parent_id=root, radius=0.12 * s, position=(0.6 * s, 2.55 * s, 0.32 * s), color="#e0f2fe")
    _sphere(scene, f"{root}_eye_r", parent_id=root, radius=0.12 * s, position=(0.9 * s, 2.55 * s, 0.32 * s), color="#e0f2fe")
    _sphere(scene, f"{root}_pupil_l", parent_id=root, radius=0.05 * s, position=(0.6 * s, 2.55 * s, 0.42 * s), color="#0f172a")
    _sphere(scene, f"{root}_pupil_r", parent_id=root, radius=0.05 * s, position=(0.9 * s, 2.55 * s, 0.42 * s), color="#0f172a")
    _box(scene, f"{root}_beak", parent_id=root, size=(0.12 * s, 0.1 * s, 0.16 * s), position=(0.75 * s, 2.28 * s, 0.38 * s), color="#f59e0b")
    _box(scene, f"{root}_tuft_l", parent_id=root, size=(0.1 * s, 0.22 * s, 0.08 * s), position=(0.52 * s, 2.8 * s, 0.1 * s), color="#172554")
    _box(scene, f"{root}_tuft_r", parent_id=root, size=(0.1 * s, 0.22 * s, 0.08 * s), position=(0.98 * s, 2.8 * s, 0.1 * s), color="#172554")


# 30 house recipes: (label, w, h, d, trait)
# trait drives unique architectural extras
HOUSE_SPECS: list[tuple[str, float, float, float, str]] = [
    ("Torre della Guardia", 2.2, 4.8, 2.2, "tower"),
    ("Locanda del Cinghiale", 4.5, 2.6, 3.4, "inn"),
    ("Casa del Fabbro", 3.2, 2.2, 3.0, "forge"),
    ("Cottage del Mulino", 2.6, 2.0, 2.4, "mill"),
    ("Villa del Mercante", 4.8, 3.0, 3.6, "balcony"),
    ("Casa a Schiera Alta", 2.0, 3.8, 2.6, "tall"),
    ("Bottega delle Spezie", 3.4, 2.3, 2.8, "stall"),
    ("Casa della Vedova", 2.4, 2.1, 2.4, "chimney"),
    ("Maniero Minore", 5.0, 3.4, 4.0, "wing"),
    ("Casa del Pescatore", 2.8, 2.0, 3.2, "dock"),
    ("Biblioteca Privata", 3.6, 3.2, 3.0, "library"),
    ("Casa Col Tetto Doppio", 3.0, 2.5, 2.8, "double_roof"),
    ("Torretta d'Angolo", 2.4, 3.6, 2.4, "corner_tower"),
    ("Casa del Fornaio", 3.3, 2.4, 3.1, "oven"),
    ("Residenza del Consigliere", 4.2, 3.1, 3.5, "porch"),
    ("Casa Stretta", 1.8, 3.2, 2.8, "narrow"),
    ("Casa con Orto", 3.0, 2.2, 2.6, "garden"),
    ("Magazzino del Porto", 4.6, 2.8, 3.8, "warehouse"),
    ("Cappella Familiare", 2.6, 3.5, 2.6, "chapel"),
    ("Casa del Cartografo", 3.1, 2.6, 2.9, "maproom"),
    ("Casa dei Tre Camini", 3.5, 2.4, 3.0, "triple_chimney"),
    ("Casa con Loggia", 3.8, 2.7, 3.2, "loggia"),
    ("Rifugio dello Scriba", 2.5, 2.3, 2.5, "scribe"),
    ("Casa del Tessitore", 3.4, 2.5, 3.3, "loom"),
    ("Casa sul Pendio", 2.9, 2.8, 2.7, "raised"),
    ("Dimora dello Scudiero", 3.7, 2.9, 3.4, "stable"),
    ("Casa della Campana", 2.7, 3.4, 2.5, "bell"),
    ("Casa delle Erbe", 2.8, 2.1, 2.8, "herbs"),
    ("Palazzetto", 4.4, 3.6, 3.8, "palace"),
    ("Casa dell'Araldo", 3.0, 2.6, 2.9, "herald"),
]


def _build_house(
    scene: Scene,
    index: int,
    *,
    x: float,
    z: float,
    yaw: float,
    faction: str,
) -> None:
    label, w, h, d, trait = HOUSE_SPECS[index]
    root = f"house_{index:02d}"
    is_red = faction == "red"
    wall = (PLASTER if index % 2 == 0 else STONE)[index % 5]
    trim = WOOD[index % 5]
    roof = (ROOF_RED if is_red else ROOF_BLUE)[index % 5]
    accent = RED_BANNER if is_red else BLUE_BANNER

    scene.add_object(
        root,
        label=f"{label} ({'Lupo' if is_red else 'Gufo'})",
        position=(x, 0.0, z),
        rotation=(0.0, yaw, 0.0),
        tags=["house", faction, trait],
    )

    # Main body
    body_y = 0.15 if trait == "raised" else 0.0
    _box(
        scene,
        f"{root}_body",
        parent_id=root,
        size=(w, h, d),
        position=(0.0, body_y + h / 2, 0.0),
        color=wall,
        tags=["house"],
    )
    # Roof slab
    _box(
        scene,
        f"{root}_roof",
        parent_id=root,
        size=(w + 0.35, 0.35, d + 0.35),
        position=(0.0, body_y + h + 0.2, 0.0),
        color=roof,
    )
    # Door
    _box(
        scene,
        f"{root}_door",
        parent_id=root,
        size=(0.7, 1.3, 0.12),
        position=(0.0, body_y + 0.65, d / 2 + 0.05),
        color=trim,
    )
    # Windows
    _box(
        scene,
        f"{root}_win_l",
        parent_id=root,
        size=(0.55, 0.55, 0.1),
        position=(-w * 0.28, body_y + h * 0.55, d / 2 + 0.04),
        color="#87ceeb",
    )
    _box(
        scene,
        f"{root}_win_r",
        parent_id=root,
        size=(0.55, 0.55, 0.1),
        position=(w * 0.28, body_y + h * 0.55, d / 2 + 0.04),
        color="#87ceeb",
    )
    # Faction fascia under the eaves
    _box(
        scene,
        f"{root}_fascia",
        parent_id=root,
        size=(w + 0.1, 0.18, 0.12),
        position=(0.0, body_y + h - 0.05, d / 2 + 0.08),
        color=accent,
    )

    # Trait-specific peculiarities
    if trait == "tower":
        _box(scene, f"{root}_spire", parent_id=root, size=(1.2, 2.2, 1.2), position=(0, body_y + h + 1.3, 0), color=wall)
        _box(scene, f"{root}_spire_roof", parent_id=root, size=(1.5, 0.4, 1.5), position=(0, body_y + h + 2.5, 0), color=roof)
    elif trait == "inn":
        _box(scene, f"{root}_sign", parent_id=root, size=(1.2, 0.7, 0.1), position=(0, body_y + 2.2, d / 2 + 0.4), color=accent)
        _box(scene, f"{root}_sign_arm", parent_id=root, size=(0.12, 0.12, 0.8), position=(0, body_y + 2.5, d / 2 + 0.2), color=trim)
    elif trait == "forge":
        _box(scene, f"{root}_anvil_block", parent_id=root, size=(1.2, 0.6, 1.0), position=(w / 2 + 0.9, 0.3, 0), color="#3f3f46")
        _sphere(scene, f"{root}_ember", parent_id=root, radius=0.18, position=(w / 2 + 0.9, 0.75, 0), color="#f97316")
    elif trait == "mill":
        _box(scene, f"{root}_wheel", parent_id=root, size=(0.25, 1.8, 1.8), position=(-w / 2 - 0.3, 1.1, 0), color=trim)
    elif trait == "balcony":
        _box(scene, f"{root}_balcony", parent_id=root, size=(w * 0.7, 0.12, 1.0), position=(0, body_y + h * 0.65, d / 2 + 0.55), color=trim)
        _box(scene, f"{root}_bal_rail", parent_id=root, size=(w * 0.7, 0.45, 0.1), position=(0, body_y + h * 0.65 + 0.28, d / 2 + 1.0), color=accent)
    elif trait == "tall":
        _box(scene, f"{root}_attic", parent_id=root, size=(w * 0.85, 1.0, d * 0.85), position=(0, body_y + h + 0.7, 0), color=wall)
    elif trait == "stall":
        _box(scene, f"{root}_awning", parent_id=root, size=(w + 0.4, 0.1, 1.6), position=(0, 2.0, d / 2 + 0.9), color=accent)
        _box(scene, f"{root}_counter", parent_id=root, size=(w * 0.8, 0.7, 0.7), position=(0, 0.35, d / 2 + 0.8), color=trim)
    elif trait == "chimney":
        _box(scene, f"{root}_chimney", parent_id=root, size=(0.55, 1.6, 0.55), position=(w * 0.3, body_y + h + 0.9, -d * 0.2), color="#4b5563")
    elif trait == "wing":
        _box(scene, f"{root}_wing", parent_id=root, size=(w * 0.55, h * 0.75, d * 0.7), position=(w * 0.55, body_y + h * 0.375, -d * 0.1), color=wall)
        _box(scene, f"{root}_wing_roof", parent_id=root, size=(w * 0.65, 0.3, d * 0.8), position=(w * 0.55, body_y + h * 0.75 + 0.15, -d * 0.1), color=roof)
    elif trait == "dock":
        _box(scene, f"{root}_pier", parent_id=root, size=(1.2, 0.2, 3.5), position=(0, 0.15, d / 2 + 1.8), color=trim)
    elif trait == "library":
        _box(scene, f"{root}_dome", parent_id=root, size=(1.4, 0.9, 1.4), position=(0, body_y + h + 0.7, 0), color=accent)
    elif trait == "double_roof":
        _box(scene, f"{root}_roof2", parent_id=root, size=(w * 0.7, 0.3, d * 0.7), position=(0, body_y + h + 0.55, 0), color=roof)
    elif trait == "corner_tower":
        _box(scene, f"{root}_ctower", parent_id=root, size=(1.3, h + 1.2, 1.3), position=(w / 2, body_y + (h + 1.2) / 2, d / 2), color=STONE[2])
        _box(scene, f"{root}_ctower_cap", parent_id=root, size=(1.6, 0.35, 1.6), position=(w / 2, body_y + h + 1.4, d / 2), color=roof)
    elif trait == "oven":
        _sphere(scene, f"{root}_oven", parent_id=root, radius=0.55, position=(-w / 2 - 0.4, 0.55, 0), color="#78716c")
    elif trait == "porch":
        _box(scene, f"{root}_porch", parent_id=root, size=(w * 0.9, 0.15, 1.4), position=(0, 0.2, d / 2 + 0.7), color=PATH)
        _box(scene, f"{root}_col_l", parent_id=root, size=(0.2, 1.8, 0.2), position=(-w * 0.35, 1.1, d / 2 + 1.2), color=trim)
        _box(scene, f"{root}_col_r", parent_id=root, size=(0.2, 1.8, 0.2), position=(w * 0.35, 1.1, d / 2 + 1.2), color=trim)
    elif trait == "narrow":
        _box(scene, f"{root}_bay", parent_id=root, size=(0.9, 1.2, 0.7), position=(0, body_y + 1.8, d / 2 + 0.35), color=wall)
    elif trait == "garden":
        _box(scene, f"{root}_hedge", parent_id=root, size=(w + 1.5, 0.7, 0.35), position=(0, 0.35, d / 2 + 1.5), color="#3f6212")
        _sphere(scene, f"{root}_bush", parent_id=root, radius=0.4, position=(w * 0.4, 0.4, d / 2 + 1.2), color="#4d7c0f")
    elif trait == "warehouse":
        _box(scene, f"{root}_crate_a", parent_id=root, size=(0.8, 0.8, 0.8), position=(w / 2 + 0.8, 0.4, 0.5), color=trim)
        _box(scene, f"{root}_crate_b", parent_id=root, size=(0.7, 0.7, 0.7), position=(w / 2 + 0.8, 0.35, -0.5), color=WOOD[2])
    elif trait == "chapel":
        _box(scene, f"{root}_steeple", parent_id=root, size=(0.7, 1.8, 0.7), position=(0, body_y + h + 1.1, 0), color=wall)
        _box(scene, f"{root}_cross_v", parent_id=root, size=(0.12, 0.7, 0.12), position=(0, body_y + h + 2.2, 0), color="#f8fafc")
        _box(scene, f"{root}_cross_h", parent_id=root, size=(0.45, 0.12, 0.12), position=(0, body_y + h + 2.35, 0), color="#f8fafc")
    elif trait == "maproom":
        _box(scene, f"{root}_oriel", parent_id=root, size=(1.1, 1.0, 0.8), position=(0, body_y + h * 0.6, d / 2 + 0.4), color="#93c5fd" if not is_red else "#fca5a5")
    elif trait == "triple_chimney":
        for i, ox in enumerate((-0.7, 0.0, 0.7)):
            _box(scene, f"{root}_ch_{i}", parent_id=root, size=(0.4, 1.3, 0.4), position=(ox, body_y + h + 0.8, -d * 0.25), color="#57534e")
    elif trait == "loggia":
        _box(scene, f"{root}_loggia", parent_id=root, size=(w * 0.85, 0.12, 1.2), position=(0, body_y + h * 0.45, d / 2 + 0.6), color=trim)
        for i, ox in enumerate((-w * 0.3, 0.0, w * 0.3)):
            _box(scene, f"{root}_log_col_{i}", parent_id=root, size=(0.18, h * 0.45, 0.18), position=(ox, body_y + h * 0.225, d / 2 + 1.1), color=STONE[1])
    elif trait == "scribe":
        _box(scene, f"{root}_lantern", parent_id=root, size=(0.25, 0.35, 0.25), position=(0, body_y + 1.8, d / 2 + 0.25), color="#fde68a")
    elif trait == "loom":
        _box(scene, f"{root}_frame", parent_id=root, size=(1.5, 1.4, 0.2), position=(w / 2 + 0.9, 0.9, 0), color=trim)
        _box(scene, f"{root}_cloth_hang", parent_id=root, size=(1.2, 1.0, 0.08), position=(w / 2 + 0.9, 0.8, 0.15), color=accent)
    elif trait == "raised":
        _box(scene, f"{root}_stilts_l", parent_id=root, size=(0.25, 0.3, 0.25), position=(-w * 0.35, 0.15, d * 0.3), color=trim)
        _box(scene, f"{root}_stilts_r", parent_id=root, size=(0.25, 0.3, 0.25), position=(w * 0.35, 0.15, d * 0.3), color=trim)
    elif trait == "stable":
        _box(scene, f"{root}_stable", parent_id=root, size=(w * 0.7, h * 0.6, d * 0.8), position=(w * 0.6, h * 0.3, 0), color=WOOD[3])
    elif trait == "bell":
        _box(scene, f"{root}_belfry", parent_id=root, size=(1.0, 1.2, 1.0), position=(0, body_y + h + 0.9, 0), color=wall)
        _sphere(scene, f"{root}_bell", parent_id=root, radius=0.25, position=(0, body_y + h + 0.85, 0), color="#ca8a04")
    elif trait == "herbs":
        for i, ox in enumerate((-0.6, 0.0, 0.6)):
            _sphere(scene, f"{root}_herb_{i}", parent_id=root, radius=0.28, position=(ox, 0.3, d / 2 + 1.0), color=("#65a30d", "#4d7c0f", "#84cc16")[i])
    elif trait == "palace":
        _box(scene, f"{root}_cornice", parent_id=root, size=(w + 0.5, 0.25, d + 0.5), position=(0, body_y + h + 0.45, 0), color=accent)
        _box(scene, f"{root}_banner_hang", parent_id=root, size=(0.9, 1.5, 0.08), position=(0, body_y + h * 0.55, d / 2 + 0.2), color=accent)
    elif trait == "herald":
        _box(scene, f"{root}_pole", parent_id=root, size=(0.1, 2.4, 0.1), position=(w / 2 + 0.5, 1.2, d / 2), color=trim)
        _box(scene, f"{root}_flag", parent_id=root, size=(1.0, 0.7, 0.06), position=(w / 2 + 1.05, 2.1, d / 2), color=accent)


def _place_districts(scene: Scene) -> None:
    # West = red wolf, East = blue owl. 15 houses each.
    # Layout: 3 rows (Z) x 5 columns (X) per side, river corridor left clear.
    red_xs = (-10.0, -15.0, -20.0, -25.0, -30.0)
    blue_xs = (10.0, 15.0, 20.0, 25.0, 30.0)
    zs = (-14.0, 0.0, 14.0)

    idx = 0
    for z in zs:
        for x in red_xs:
            _build_house(scene, idx, x=x, z=z, yaw=90.0, faction="red")
            idx += 1
    for z in zs:
        for x in blue_xs:
            _build_house(scene, idx, x=x, z=z, yaw=-90.0, faction="blue")
            idx += 1

    assert idx == 30

    # District banners along the river promenades
    for i, z in enumerate((-22.0, -12.0, -4.0, 4.0, 12.0, 22.0)):
        _wolf_emblem(scene, f"wolf_banner_{i}", x=-6.5, z=z, scale=1.0)
        _owl_emblem(scene, f"owl_banner_{i}", x=6.5, z=z, scale=1.0)

    # Large plaza standards near the bridge
    _wolf_emblem(scene, "wolf_plaza", x=-8.0, z=0.0, scale=1.35)
    _owl_emblem(scene, "owl_plaza", x=8.0, z=0.0, scale=1.35)

    scene.add_annotation(
        "poi_red",
        (-18.0, 4.0, 0.0),
        label="Quartiere del Lupo Rosso",
        description="15 dimore peculiari sotto lo stemma del lupo scarlatto",
    )
    scene.add_annotation(
        "poi_blue",
        (18.0, 4.0, 0.0),
        label="Quartiere del Gufo Blu",
        description="15 dimore peculiari sotto lo stemma del gufo azzurro",
    )
    scene.add_annotation(
        "poi_river",
        (0.0, 1.5, -28.0),
        label="Fiume Argentato",
        description="Nasce fuori dal villaggio e attraversa il centro sotto il ponte",
    )


# sceneify:scene-begin
def build_scene() -> Scene:
    scene = Scene("My First Conversational Room", background="#87a7c4")
    scene.set_presentation(
        grid=False,
        helpers=False,
        shadows=True,
        exposure=1.05,
        fog={"color": "#a8bdd0", "near": 40, "far": 120},
        camera={"position": [22, 16, 28], "target": [0, 1.5, 0], "fov": 48},
        title="Villaggio Bifronte",
        subtitle="Lupo Rosso e Gufo Blu divisi dal Fiume Argentato",
        ambientIntensity=0.55,
        keyLightIntensity=1.25,
    )
    _add_ground_and_river(scene)
    _add_bridge(scene)
    _place_districts(scene)
    return scene


# sceneify:scene-end


if __name__ == "__main__":
    build_scene().run(project_root=Path(__file__).parents[2])
