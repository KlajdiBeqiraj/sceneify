"""Emit canonical Scene authoring Python (one node = one call)."""

from __future__ import annotations

import json
from typing import Any

from sceneify.scene import Scene


def _fmt(value: Any) -> str:
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, bool):
        return "True" if value else "False"
    if value is None:
        return "None"
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, int):
        return repr(value)
    if isinstance(value, tuple):
        return "(" + ", ".join(_fmt(item) for item in value) + ")"
    if isinstance(value, list):
        return "[" + ", ".join(_fmt(item) for item in value) + "]"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return repr(value)


def _vec(values: list[Any] | tuple[Any, ...] | None) -> str:
    assert values is not None
    return "(" + ", ".join(_fmt(float(v)) for v in values) + ")"


def _near(a: list[Any] | None, b: list[float]) -> bool:
    if a is None:
        return True
    if len(a) != len(b):
        return False
    return all(abs(float(x) - y) < 1e-9 for x, y in zip(a, b, strict=True))


def _material_expr(data: dict[str, Any] | None) -> str | None:
    if not data:
        return None
    parts: list[str] = []
    color = data.get("color", "#ffffff")
    parts.append(_fmt(color))
    mapping = (
        ("roughness", "roughness", 1.0),
        ("metalness", "metalness", 0.0),
        ("opacity", "opacity", 1.0),
        ("wireframe", "wireframe", False),
        ("baseColorTexture", "base_color_texture", None),
        ("normalTexture", "normal_texture", None),
        ("metallicRoughnessTexture", "metallic_roughness_texture", None),
    )
    for key, arg, default in mapping:
        value = data.get(key, default)
        if value == default or value is None:
            continue
        parts.append(f"{arg}={_fmt(value)}")
    repeat = data.get("textureRepeat")
    if repeat and list(repeat) != [1, 1]:
        parts.append(f"texture_repeat={_vec(list(repeat))}")
    if len(parts) == 1 and color == "#ffffff":
        return None
    return f"Material({', '.join(parts)})"


def _physics_expr(data: dict[str, Any] | None) -> str | None:
    if not data:
        return None
    parts = [f"body={_fmt(data.get('body', 'fixed'))}"]
    collider = data.get("collider", "cuboid")
    if collider != "cuboid":
        parts.append(f"collider={_fmt(collider)}")
    if data.get("sensor"):
        parts.append("sensor=True")
    mass = data.get("mass", 1.0)
    if mass != 1.0:
        parts.append(f"mass={_fmt(mass)}")
    return f"Physics({', '.join(parts)})"


def _call_kwargs(node: dict[str, Any]) -> list[str]:
    args: list[str] = []
    if not _near(node.get("position"), [0.0, 0.0, 0.0]):
        args.append(f"position={_vec(node['position'])}")
    if not _near(node.get("rotation"), [0.0, 0.0, 0.0]):
        args.append(f"rotation={_vec(node['rotation'])}")
    if not _near(node.get("scale"), [1.0, 1.0, 1.0]):
        args.append(f"scale={_vec(node['scale'])}")
    if node.get("parentId"):
        args.append(f"parent_id={_fmt(node['parentId'])}")
    if node.get("tags"):
        args.append(f"tags={_fmt(list(node['tags']))}")
    if node.get("visible") is False:
        args.append("visible=False")
    material = _material_expr(node.get("material"))
    if material:
        args.append(f"material={material}")
    physics = _physics_expr(node.get("physics"))
    if physics:
        args.append(f"physics={physics}")
    for key, value in (node.get("meta") or {}).items():
        args.append(f"{key}={_fmt(value)}")
    return args


def emit_build_scene(scene: Scene, *, function_name: str = "build_scene") -> str:
    """Return a marked-region body: imports + ``def build_scene()``."""
    data = scene.to_dict()
    lines: list[str] = [
        "from sceneify import Game, Material, Physics, Scene",
        "",
        "",
        f"def {function_name}() -> Scene:",
        f"    scene = Scene({_fmt(data.get('name', 'scene'))}, "
        f"background={_fmt(data.get('background', '#0f1115'))})",
    ]
    presentation = data.get("presentation")
    if presentation:
        kwargs = [
            f"{key}={_fmt(value)}" for key, value in presentation.items() if value is not None
        ]
        if kwargs:
            lines.append(f"    scene.set_presentation({', '.join(kwargs)})")

    for primitive in data.get("primitives") or []:
        args = [_fmt(primitive["id"]), _fmt(primitive.get("primitive", "box"))]
        kind = primitive.get("primitive", "box")
        if kind in {"box", "plane"} and primitive.get("size"):
            args.append(f"size={_vec(primitive['size'])}")
        if kind in {"sphere", "capsule"} and primitive.get("radius") is not None:
            args.append(f"radius={_fmt(float(primitive['radius']))}")
        if kind == "capsule" and primitive.get("height") is not None:
            args.append(f"height={_fmt(float(primitive['height']))}")
        args.extend(_call_kwargs(primitive))
        lines.append(f"    scene.create_primitive({', '.join(args)})")

    for mesh in data.get("meshes") or []:
        source = mesh.get("source", "")
        fmt = (mesh.get("format") or "").lower()
        is_glb = fmt in {"glb", "gltf"} or str(source).lower().endswith((".glb", ".gltf"))
        args = [_fmt(mesh["id"]), _fmt(source)]
        if not is_glb and fmt:
            args.append(f"format={_fmt(fmt)}")
        args.extend(_call_kwargs(mesh))
        method = "add_glb" if is_glb else "add_mesh"
        lines.append(f"    scene.{method}({', '.join(args)})")

    for obj in data.get("objects") or []:
        args = [_fmt(obj["id"])]
        if obj.get("label"):
            args.append(f"label={_fmt(obj['label'])}")
        args.extend(_call_kwargs(obj))
        lines.append(f"    scene.add_object({', '.join(args)})")

    for ann in data.get("annotations") or []:
        args = [_fmt(ann["id"])]
        if ann.get("targetId"):
            args.append(f"target_id={_fmt(ann['targetId'])}")
            if ann.get("offset") and not _near(ann.get("offset"), [0.0, 0.0, 0.0]):
                args.append(f"offset={_vec(ann['offset'])}")
        elif ann.get("position") is not None:
            args.append(f"position={_vec(ann['position'])}")
        if ann.get("label"):
            args.append(f"label={_fmt(ann['label'])}")
        if ann.get("description"):
            args.append(f"description={_fmt(ann['description'])}")
        if ann.get("color") and ann["color"] != "#ffcc00":
            args.append(f"color={_fmt(ann['color'])}")
        if ann.get("visible") is False:
            args.append("visible=False")
        lines.append(f"    scene.add_annotation({', '.join(args)})")

    game = data.get("game")
    if game:
        lines.append(f"    scene.set_game(Game.from_dict({_fmt(game)}))")

    lines.append("    return scene")
    lines.append("")
    return "\n".join(lines)
