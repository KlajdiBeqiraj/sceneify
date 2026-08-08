"""Present a Roman-inspired environment with an automatic camera tour.

Run from the repository root:
  uv run python examples/showcase/roman_environment.py

Let the tour run to see the presentation system; use ``--edit`` to inspect
assets, annotations, and camera stops in the authoring editor.
"""

import argparse
from pathlib import Path

from sceneify import Material, Scene, SemanticEvent


def build_scene() -> Scene:
    scene = Scene("Roman Forum Explorer", background="#cbb9a0")
    scene.set_presentation(
        environmentMap="examples/assets/roman/colosseum_1k.hdr",
        grid=False,
        helpers=False,
        shadows=True,
        exposure=1.12,
        fog={"color": "#cbb9a0", "near": 28, "far": 80},
        camera={"position": [14, 9, 16], "target": [0, 1.6, 0], "fov": 40},
        title="Fragments of Rome",
        subtitle="An automatic camera journey through the forum exhibits",
        ambientIntensity=0.5,
        keyLightIntensity=1.35,
        cameraTour={
            "autoplay": True,
            "loop": True,
            "stops": [
                {
                    "id": "overview",
                    "position": [14, 9, 16],
                    "target": [0, 1.6, 0],
                    "travel": 0.1,
                    "hold": 3.2,
                    "exposure": 1.12,
                    "lightScale": 1.0,
                    "cue": "Wide establishing shot of the forum",
                },
                {
                    "id": "approach_fountain",
                    "position": [4.8, 3.4, 7.2],
                    "target": [0, 1.1, 0],
                    "travel": 4.5,
                    "hold": 1.2,
                    "exposure": 0.95,
                    "lightScale": 0.85,
                    "cue": "Traveling into the plaza",
                },
                {
                    "id": "fountain_detail",
                    "annotationId": "poi_fountain",
                    "position": [3.6, 2.3, 5.0],
                    "target": [0, 1.15, 0],
                    "travel": 3.8,
                    "hold": 5.0,
                    "exposure": 1.05,
                    "lightScale": 0.88,
                    "spotlight": False,
                    "fov": 32,
                    "cue": "Tight FOV push — keep daylight readable",
                },
                {
                    "id": "to_bust",
                    "position": [-1.2, 3.8, 6.5],
                    "target": [-3.2, 1.6, 2.4],
                    "travel": 4.0,
                    "hold": 0.8,
                    "exposure": 0.95,
                    "lightScale": 0.8,
                    "cue": "Crossing the forum toward portraiture",
                },
                {
                    "id": "bust_detail",
                    "annotationId": "poi_bust",
                    "position": [-2.35, 2.35, 4.55],
                    "target": [-4.2, 2.15, 2.8],
                    "travel": 3.6,
                    "hold": 5.5,
                    "exposure": 0.48,
                    "lightScale": 0.16,
                    "spotlight": True,
                    "fov": 28,
                    "cue": "Sculpture study: dim the key light, add a spot",
                },
                {
                    "id": "to_horse",
                    "position": [5.2, 5.0, 9.0],
                    "target": [4.6, 2.2, 2.5],
                    "travel": 3.8,
                    "hold": 0.7,
                    "exposure": 0.95,
                    "lightScale": 0.8,
                    "fov": 40,
                    "cue": "Pull south for a head-on equestrian stand",
                },
                {
                    "id": "horse_detail",
                    "annotationId": "poi_horse",
                    # South stand at distance — with yaw 1.55 the head reads toward the lens.
                    "position": [5.8, 4.3, 10.8],
                    "target": [4.6, 2.4, 2.4],
                    "travel": 3.6,
                    "hold": 5.5,
                    "exposure": 0.45,
                    "lightScale": 0.2,
                    "spotlight": True,
                    "fov": 34,
                    "cue": "Head-on study: dim the key light to sculpt porcelain",
                },
                {
                    "id": "to_ruins",
                    "position": [1.5, 4.5, -2.0],
                    "target": [-3.2, 2.5, -6.2],
                    "travel": 4.2,
                    "hold": 0.8,
                    "exposure": 1.05,
                    "lightScale": 0.95,
                    "fov": 44,
                    "cue": "Swing past the fountain to the ruined arch",
                },
                {
                    "id": "ruins_detail",
                    "annotationId": "poi_ruins",
                    # SE stand: sees Wall_ArchRound_Broken without the west arcade in the lens.
                    "position": [1.4, 3.1, -1.2],
                    "target": [-3.8, 2.35, -6.8],
                    "travel": 3.6,
                    "hold": 5.5,
                    "exposure": 1.12,
                    "lightScale": 1.0,
                    "spotlight": False,
                    "fov": 44,
                    "cue": "Full arch hold in balanced daylight",
                },
                {
                    "id": "return_overview",
                    "position": [12, 8.5, 14],
                    "target": [0, 1.8, 0],
                    "travel": 5.0,
                    "hold": 2.5,
                    "exposure": 1.12,
                    "lightScale": 1.0,
                    "cue": "Returning to the forum overview",
                },
            ],
        },
    )
    scene.create_primitive(
        "piazza",
        "plane",
        size=(40, 0.15, 36),
        material=Material(
            "#ffffff",
            roughness=1.0,
            metalness=1.0,
            base_color_texture="examples/assets/roman/stone_pavers_diff_1k.jpg",
            normal_texture="examples/assets/roman/stone_pavers_nor_gl_1k.jpg",
            metallic_roughness_texture="examples/assets/roman/stone_pavers_arm_1k.jpg",
            texture_repeat=(10, 9),
        ),
        tags=["architecture", "ground"],
    )
    ruin_pieces = (
        ("broken_arch", "Wall_ArchRound_Broken", (-3.8, 0, -6.8), (0, 0.2, 0), (1.35, 1.35, 1.35)),
        ("arcade_left", "Curve_1_Overgrown", (-8.8, 0, -1.5), (0, 1.45, 0), (1.15, 1.15, 1.15)),
        ("arcade_right", "Window_Open_Double", (8.8, 0, -1.5), (0, -1.5, 0), (1.15, 1.15, 1.15)),
        ("fallen_wall", "Wall_Broken", (3.2, 0, -7.4), (0, -0.15, 0), (1.4, 1.4, 1.4)),
        ("forum_stairs", "Stairs", (0, 0, 8.2), (0, 3.14, 0), (1.05, 1.05, 1.05)),
        ("column_left", "Column_Round", (-7.5, 0, 5.7), (0, 0, 0), (1.2, 1.2, 1.2)),
        ("column_right", "Column_Round", (8.5, 0, -5.2), (0, 0, 0), (1.2, 1.2, 1.2)),
    )
    for node_id, model_node, position, rotation, scale in ruin_pieces:
        scene.add_glb(
            node_id,
            "examples/assets/roman/modular_ruins.glb",
            position=position,
            rotation=rotation,
            scale=scale,
            tags=["architecture", "ruins", "cc0"],
            includeNodes=[model_node],
            normalizeOrigin=True,
        )
    scene.add_glb(
        "central_fountain",
        "examples/assets/roman/fountain.glb",
        position=(0, 0, 0),
        scale=(1.8, 1.8, 1.8),
        tags=["architecture", "fountain", "cc0"],
    )
    scene.add_glb(
        "marble_bust",
        "examples/assets/roman/marble_bust.glb",
        position=(-4.2, 1.25, 2.8),
        rotation=(0, 0.65, 0),
        scale=(3.1, 3.1, 3.1),
        tags=["sculpture", "marble", "cc0"],
    )
    scene.create_primitive(
        "bust_plinth",
        "box",
        position=(-4.2, 0.65, 2.8),
        size=(1.1, 1.3, 1.1),
        material=Material("#d8d0c5", roughness=0.7),
        tags=["architecture"],
    )
    scene.add_glb(
        "horse_statue",
        "examples/assets/roman/horse_statue.glb",
        position=(4.6, 0.7, 2.4),
        rotation=(0, 1.55, 0),
        scale=(13.5, 13.5, 13.5),
        tags=["sculpture", "bronze", "cc0"],
    )
    scene.create_primitive(
        "horse_plinth",
        "box",
        position=(4.6, 0.35, 2.4),
        size=(3.5, 0.7, 1.8),
        material=Material("#776d60", roughness=0.82),
        tags=["architecture"],
    )

    points = (
        (
            "poi_ruins",
            "broken_arch",
            (0, 3.1, 0),
            "Ultimate Modular Ruins",
            (
                "Selected pieces from Quaternius' August 2021 pack of 90 modular ruins, "
                "dungeons, props, and one animated character."
            ),
            "Quaternius · CC0",
        ),
        (
            "poi_fountain",
            "central_fountain",
            (0, 1.8, 0),
            "The civic fountain",
            (
                "A CC0 fountain model by Isa Lousberg, sourced from its published "
                "Poly Pizza model page."
            ),
            "Isa Lousberg · CC0",
        ),
        (
            "poi_bust",
            "marble_bust",
            (0, 1.95, 0),
            "Marble Bust 01",
            (
                "Poly Haven describes this Rico Cilliers model as a Renaissance-style "
                "male marble bust with veining, light weathering, and a round plinth."
            ),
            "Poly Haven · CC0",
        ),
        (
            "poi_horse",
            "horse_statue",
            (0, 3.6, 0),
            "Horse Statue 01",
            (
                "A Rico Cilliers model from Poly Haven: a glossy white porcelain horse "
                "figurine rearing on a round wooden base, scaled here for the exhibit."
            ),
            "Poly Haven · CC0",
        ),
    )
    for point_id, target_id, offset, label, description, category in points:
        scene.add_annotation(
            point_id,
            target_id=target_id,
            offset=offset,
            label=label,
            description=description,
            color="#d6a65f",
            interaction={"reveal": "hover", "clickEvent": "poi_selected", "cursor": "pointer"},
            category=category,
        )
    return scene


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--edit",
        action="store_true",
        help="Open the environment editor instead of the standalone presentation.",
    )
    args = parser.parse_args()

    output = Path(__file__).with_name("roman_environment.sceneify.json")
    scene = build_scene()
    scene.save(output)

    @scene.on_event
    def log_poi(_scene: Scene, event: SemanticEvent) -> None:
        if event.name == "poi_selected" and event.node_id:
            print(f"Selected point of interest: {event.node_id}")
        if event.name == "tour_stop" and event.node_id:
            print(f"Camera tour stop: {event.node_id}")

    serve = scene.run if args.edit else scene.play
    serve(project_root=Path(__file__).parents[2])
