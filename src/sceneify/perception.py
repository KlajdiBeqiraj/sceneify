"""Agent-facing scene perception helpers (world poses, maps, spatial queries)."""

from __future__ import annotations

import json
import math
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from sceneify.annotations import Annotation
from sceneify.objects import MeshAsset, PrimitiveNode, SceneObject
from sceneify.scene import Scene
from sceneify.types import Vec3

DetailLevel = Literal["summary", "full"]
NodeKind = Literal["mesh", "object", "primitive", "annotation"]
SpatialMode = Literal["nearest", "distance", "relative", "in_radius", "height_at"]

# Axes convention for agent-facing maps: Y-up, +X east, -Z north, +Z south.
AXES = {"up": "+Y", "east": "+X", "north": "-Z", "south": "+Z"}

_READ_ACTIONS = frozenset(
    {
        "describe_scene",
        "get_node",
        "list_nodes",
        "topdown_map",
        "spatial_query",
        "get_bounds",
        "get_scene",
        "validate_scene",
        "list_assets",
        "search_assets",
        "list_remote",
        "search_remote",
        "info_remote",
        "capture_view",
    }
)


def is_read_action(action: str) -> bool:
    """Return True when an action is inspection/discovery (no scene dump by default)."""
    return action in _READ_ACTIONS


def _vec_list(value: Sequence[float]) -> list[float]:
    return [float(value[0]), float(value[1]), float(value[2])]


def _transform_dict(position: Vec3, rotation: Vec3, scale: Vec3) -> dict[str, list[float]]:
    return {
        "position": _vec_list(position),
        "rotation": _vec_list(rotation),
        "scale": _vec_list(scale),
    }


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


def _bearing_xz(dx: float, dz: float) -> tuple[str, float]:
    """Return cardinal bearing and yaw degrees (0 = north / -Z, clockwise)."""
    if abs(dx) < 1e-9 and abs(dz) < 1e-9:
        return "here", 0.0
    # atan2(dx, -dz): 0 when moving toward -Z (north)
    yaw = math.degrees(math.atan2(dx, -dz))
    if yaw < 0:
        yaw += 360.0
    sectors = (
        (22.5, "north"),
        (67.5, "northeast"),
        (112.5, "east"),
        (157.5, "southeast"),
        (202.5, "south"),
        (247.5, "southwest"),
        (292.5, "west"),
        (337.5, "northwest"),
        (360.1, "north"),
    )
    for limit, name in sectors:
        if yaw < limit:
            return name, yaw
    return "north", yaw


def _node_kind(node: MeshAsset | SceneObject | PrimitiveNode | Annotation) -> NodeKind:
    if isinstance(node, MeshAsset):
        return "mesh"
    if isinstance(node, SceneObject):
        return "object"
    if isinstance(node, PrimitiveNode):
        return "primitive"
    return "annotation"


def _local_aabb_primitive(node: PrimitiveNode) -> tuple[Vec3, Vec3]:
    if node.primitive == "box":
        hx, hy, hz = node.size[0] / 2, node.size[1] / 2, node.size[2] / 2
        return (-hx, -hy, -hz), (hx, hy, hz)
    if node.primitive == "plane":
        hx, hz = node.size[0] / 2, node.size[2] / 2
        return (-hx, 0.0, -hz), (hx, 0.0, hz)
    if node.primitive == "sphere":
        r = node.radius
        return (-r, -r, -r), (r, r, r)
    # capsule: radius + half-height along Y
    r = node.radius
    half = node.height / 2
    return (-r, -half - r, -r), (r, half + r, r)


def glb_local_bounds(path: str | Path) -> tuple[Vec3, Vec3] | None:
    """Read axis-aligned bounds from glTF accessors in a GLB file."""
    file_path = Path(path)
    if not file_path.is_file():
        return None
    data = file_path.read_bytes()
    if len(data) < 20:
        return None
    try:
        chunk_len, chunk_type = struct.unpack_from("<I4s", data, 12)
    except struct.error:
        return None
    if chunk_type != b"JSON":
        return None
    try:
        document = json.loads(data[20 : 20 + chunk_len])
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    mins: list[list[float]] = []
    maxs: list[list[float]] = []
    for accessor in document.get("accessors") or []:
        if accessor.get("type") != "VEC3":
            continue
        if "min" not in accessor or "max" not in accessor:
            continue
        mins.append([float(v) for v in accessor["min"]])
        maxs.append([float(v) for v in accessor["max"]])
    if not mins:
        return None
    gmin = (min(m[0] for m in mins), min(m[1] for m in mins), min(m[2] for m in mins))
    gmax = (max(m[0] for m in maxs), max(m[1] for m in maxs), max(m[2] for m in maxs))
    return gmin, gmax


def _transform_aabb(
    local_min: Vec3, local_max: Vec3, position: Vec3, scale: Vec3
) -> tuple[Vec3, Vec3]:
    """AABB after non-uniform scale + translation (rotation ignored for footprint)."""
    corners = [
        (
            position[0] + x * scale[0],
            position[1] + y * scale[1],
            position[2] + z * scale[2],
        )
        for x in (local_min[0], local_max[0])
        for y in (local_min[1], local_max[1])
        for z in (local_min[2], local_max[2])
    ]
    return (
        (min(c[0] for c in corners), min(c[1] for c in corners), min(c[2] for c in corners)),
        (max(c[0] for c in corners), max(c[1] for c in corners), max(c[2] for c in corners)),
    )


def node_bounds(scene: Scene, node_id: str) -> dict[str, Any]:
    """Return world-space AABB for a graph node or annotation."""
    nodes = scene._graph_nodes()
    if node_id in nodes:
        node = nodes[node_id]
        world = scene.world_transform(node_id)
        position = (
            float(world["position"][0]),
            float(world["position"][1]),
            float(world["position"][2]),
        )
        scale = (
            float(world["scale"][0]),
            float(world["scale"][1]),
            float(world["scale"][2]),
        )
        source: str | None = None
        if isinstance(node, PrimitiveNode):
            local_min, local_max = _local_aabb_primitive(node)
            method = "primitive"
        elif isinstance(node, MeshAsset):
            source = node.source
            local = glb_local_bounds(node.source)
            if local is None:
                return {
                    "id": node_id,
                    "kind": "mesh",
                    "method": "point",
                    "min": list(position),
                    "max": list(position),
                    "center": list(position),
                    "size": [0.0, 0.0, 0.0],
                    "source": source,
                }
            local_min, local_max = local
            method = "glb_accessors"
        else:
            return {
                "id": node_id,
                "kind": "object",
                "method": "point",
                "min": list(position),
                "max": list(position),
                "center": list(position),
                "size": [0.0, 0.0, 0.0],
            }
        world_min, world_max = _transform_aabb(local_min, local_max, position, scale)
        center = (
            (world_min[0] + world_max[0]) / 2,
            (world_min[1] + world_max[1]) / 2,
            (world_min[2] + world_max[2]) / 2,
        )
        size = (
            world_max[0] - world_min[0],
            world_max[1] - world_min[1],
            world_max[2] - world_min[2],
        )
        payload: dict[str, Any] = {
            "id": node_id,
            "kind": _node_kind(node),
            "method": method,
            "min": _vec_list(world_min),
            "max": _vec_list(world_max),
            "center": _vec_list(center),
            "size": _vec_list(size),
        }
        if source is not None:
            payload["source"] = source
        return payload

    annotation = scene._annotations.get(node_id)
    if annotation is None:
        raise KeyError(f"Unknown node id {node_id!r}")
    position = _annotation_world_position(scene, annotation)
    return {
        "id": node_id,
        "kind": "annotation",
        "method": "point",
        "min": list(position),
        "max": list(position),
        "center": list(position),
        "size": [0.0, 0.0, 0.0],
    }


def scene_bounds(scene: Scene) -> dict[str, Any]:
    """Union AABB of environment bounds and all graph nodes."""
    mins: list[list[float]] = []
    maxs: list[list[float]] = []
    env = scene.environment
    if env and env.bounds is not None:
        mins.append(list(env.bounds.min))
        maxs.append(list(env.bounds.max))
    for node_id in scene._graph_nodes():
        bounds = node_bounds(scene, node_id)
        mins.append(bounds["min"])
        maxs.append(bounds["max"])
    if not mins:
        return {
            "min": [0.0, 0.0, 0.0],
            "max": [0.0, 0.0, 0.0],
            "center": [0.0, 0.0, 0.0],
            "size": [0.0, 0.0, 0.0],
            "source": "empty",
        }
    world_min = [min(m[i] for m in mins) for i in range(3)]
    world_max = [max(m[i] for m in maxs) for i in range(3)]
    return {
        "min": world_min,
        "max": world_max,
        "center": [(world_min[i] + world_max[i]) / 2 for i in range(3)],
        "size": [world_max[i] - world_min[i] for i in range(3)],
        "source": "union",
    }


def _annotation_world_position(scene: Scene, annotation: Annotation) -> list[float]:
    if annotation.target_id and annotation.target_id in scene._graph_nodes():
        world = scene.world_transform(annotation.target_id)
        pos = world["position"]
        return [
            float(pos[0]) + float(annotation.offset[0]),
            float(pos[1]) + float(annotation.offset[1]),
            float(pos[2]) + float(annotation.offset[2]),
        ]
    return _vec_list(annotation.position)


def _children_map(scene: Scene) -> dict[str | None, list[str]]:
    children: dict[str | None, list[str]] = {None: []}
    for node_id, node in scene._graph_nodes().items():
        children.setdefault(node.parent_id, []).append(node_id)
        children.setdefault(node_id, [])
    for parent_id in children:
        children[parent_id].sort()
    return children


def _describe_node(
    scene: Scene,
    node_id: str,
    *,
    children_map: dict[str | None, list[str]],
    include_bounds: bool = False,
) -> dict[str, Any]:
    nodes = scene._graph_nodes()
    if node_id in nodes:
        node = nodes[node_id]
        world = scene.world_transform(node_id)
        payload: dict[str, Any] = {
            "id": node.id,
            "kind": _node_kind(node),
            "tags": list(node.tags),
            "parentId": node.parent_id,
            "children": list(children_map.get(node.id, [])),
            "childrenCount": len(children_map.get(node.id, [])),
            "visible": node.visible,
            "local": _transform_dict(node.position, node.rotation, node.scale),
            "world": world,
        }
        if isinstance(node, SceneObject) and node.label:
            payload["label"] = node.label
        if isinstance(node, MeshAsset):
            payload["source"] = node.source
            payload["format"] = node.format
        if isinstance(node, PrimitiveNode):
            payload["primitive"] = node.primitive
            payload["size"] = _vec_list(node.size)
            payload["radius"] = node.radius
            payload["height"] = node.height
        if include_bounds:
            payload["bounds"] = node_bounds(scene, node_id)
        return payload

    annotation = scene._annotations[node_id]
    position = _annotation_world_position(scene, annotation)
    return {
        "id": annotation.id,
        "kind": "annotation",
        "tags": [],
        "parentId": annotation.target_id,
        "children": [],
        "childrenCount": 0,
        "visible": annotation.visible,
        "label": annotation.label,
        "description": annotation.description,
        "targetId": annotation.target_id,
        "local": {
            "position": _vec_list(annotation.position),
            "rotation": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
        },
        "world": {
            "position": position,
            "rotation": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
        },
    }


def _build_tree(children_map: dict[str | None, list[str]], root_id: str | None = None) -> str:
    lines: list[str] = []

    def visit(node_id: str, depth: int) -> None:
        lines.append(f"{'  ' * depth}{node_id}")
        for child_id in children_map.get(node_id, []):
            visit(child_id, depth + 1)

    roots = children_map.get(None, []) if root_id is None else [root_id]
    for root in roots:
        visit(root, 0)
    return "\n".join(lines)


def describe_scene(
    scene: Scene,
    *,
    detail: DetailLevel = "summary",
    tags: Sequence[str] | None = None,
    roots: Sequence[str] | None = None,
    max_nodes: int = 200,
    include_annotations: bool = True,
) -> dict[str, Any]:
    """Compact scene overview with world poses for coding agents."""
    if detail not in {"summary", "full"}:
        raise ValueError("detail must be 'summary' or 'full'")
    children_map = _children_map(scene)
    tag_filter = {tag.lower() for tag in tags} if tags else None
    if roots:
        selected_ids: list[str] = []
        for root in roots:
            if root not in scene._graph_nodes():
                raise KeyError(f"Unknown root id {root!r}")
            selected_ids.append(root)
            selected_ids.extend(scene.descendants(root))
    elif detail == "summary" and tag_filter is None:
        selected_ids = list(children_map.get(None, []))
    else:
        selected_ids = sorted(scene._graph_nodes())

    node_payloads: list[dict[str, Any]] = []
    for node_id in selected_ids:
        node = scene._graph_nodes()[node_id]
        if tag_filter is not None and not tag_filter.intersection(t.lower() for t in node.tags):
            continue
        node_payloads.append(
            _describe_node(
                scene,
                node_id,
                children_map=children_map,
                include_bounds=detail == "full",
            )
        )
        if len(node_payloads) >= max_nodes:
            break

    annotations: list[dict[str, Any]] = []
    if include_annotations:
        for annotation in scene._annotations.values():
            annotations.append(
                {
                    "id": annotation.id,
                    "label": annotation.label,
                    "description": annotation.description,
                    "targetId": annotation.target_id,
                    "worldPosition": _annotation_world_position(scene, annotation),
                }
            )

    env = scene.environment
    environment: dict[str, Any] | None = None
    if env is not None:
        environment = {
            "boundsMin": list(env.bounds.min) if env.bounds else None,
            "boundsMax": list(env.bounds.max) if env.bounds else None,
            "groundY": env.ground.y if env.ground else None,
            "zoneCount": len(env.zones),
            "hasWorldMesh": env.world_mesh is not None,
        }

    presentation = dict(scene._presentation)
    camera = presentation.get("camera")
    tree_roots = list(roots) if roots else None
    tree = (
        "\n".join(_build_tree(children_map, root) for root in tree_roots)
        if tree_roots
        else _build_tree(children_map)
    )

    return {
        "name": scene.name,
        "detail": detail,
        "axes": AXES,
        "counts": {
            "meshes": len(scene._meshes),
            "objects": len(scene._objects),
            "primitives": len(scene._primitives),
            "annotations": len(scene._annotations),
            "trajectories": len(scene._trajectories),
            "prefabs": len(scene._prefabs),
        },
        "environment": environment,
        "camera": camera,
        "tree": tree,
        "nodes": node_payloads,
        "annotations": annotations,
        "truncated": len(node_payloads) >= max_nodes,
        "maxNodes": max_nodes,
    }


def list_nodes(
    scene: Scene,
    *,
    tag: str | None = None,
    kind: NodeKind | None = None,
    query: str | None = None,
    parent_id: str | object | None = ...,
    page_offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Paginated node listing with optional filters."""
    if page_offset < 0:
        raise ValueError("pageOffset must be >= 0")
    if limit < 1:
        raise ValueError("limit must be >= 1")
    children_map = _children_map(scene)
    rows: list[dict[str, Any]] = []
    query_l = query.lower() if query else None
    tag_l = tag.lower() if tag else None

    for node_id in sorted(scene._graph_nodes()):
        node = scene._graph_nodes()[node_id]
        node_kind = _node_kind(node)
        if kind is not None and node_kind != kind:
            continue
        if tag_l is not None and tag_l not in {t.lower() for t in node.tags}:
            continue
        if parent_id is not ... and node.parent_id != parent_id:
            continue
        label = getattr(node, "label", None)
        haystack = " ".join(
            part for part in (node_id, label or "", " ".join(node.tags), node_kind) if part
        ).lower()
        if query_l and query_l not in haystack:
            continue
        rows.append(_describe_node(scene, node_id, children_map=children_map))

    if kind in {None, "annotation"}:
        for annotation in sorted(scene._annotations.values(), key=lambda item: item.id):
            if kind is not None and kind != "annotation":
                continue
            if tag_l is not None:
                continue
            if parent_id is not ... and annotation.target_id != parent_id:
                continue
            haystack = " ".join(
                part
                for part in (
                    annotation.id,
                    annotation.label or "",
                    annotation.description or "",
                    "annotation",
                )
                if part
            ).lower()
            if query_l and query_l not in haystack:
                continue
            rows.append(_describe_node(scene, annotation.id, children_map=children_map))

    total = len(rows)
    page = rows[page_offset : page_offset + limit]
    next_offset = page_offset + len(page)
    return {
        "nodes": page,
        "total": total,
        "offset": page_offset,
        "limit": limit,
        "count": len(page),
        "hasMore": next_offset < total,
        "nextOffset": next_offset if next_offset < total else None,
        "query": query,
        "tag": tag,
        "kind": kind,
    }


def get_node(scene: Scene, node_id: str, *, include_bounds: bool = True) -> dict[str, Any]:
    """Detailed inspection for one node including anchored annotations."""
    children_map = _children_map(scene)
    if node_id not in scene._graph_nodes() and node_id not in scene._annotations:
        raise KeyError(f"Unknown node id {node_id!r}")
    payload = _describe_node(
        scene,
        node_id,
        children_map=children_map,
        include_bounds=include_bounds,
    )
    anchored = [
        {
            "id": annotation.id,
            "label": annotation.label,
            "description": annotation.description,
            "offset": _vec_list(annotation.offset),
            "worldPosition": _annotation_world_position(scene, annotation),
        }
        for annotation in scene._annotations.values()
        if annotation.target_id == node_id
    ]
    payload["anchoredAnnotations"] = anchored
    if include_bounds and "bounds" not in payload:
        payload["bounds"] = node_bounds(scene, node_id)
    return payload


def _map_extent(
    scene: Scene,
    focus: Sequence[float] | None,
    half_span: float | None,
) -> tuple[float, float, float, float]:
    if focus is not None and half_span is not None:
        fx = float(focus[0])
        fz = float(focus[2]) if len(focus) > 2 else float(focus[1])
        return fx - half_span, fx + half_span, fz - half_span, fz + half_span
    bounds = scene_bounds(scene)
    return bounds["min"][0], bounds["max"][0], bounds["min"][2], bounds["max"][2]


def _symbol_for_node(scene: Scene, node_id: str) -> str:
    node = scene._graph_nodes().get(node_id)
    if node is None:
        return "?"
    tags = {tag.lower() for tag in node.tags}
    if "player" in tags or "player-spawn" in tags:
        return "P"
    if "ground" in tags or "floor" in tags:
        return "G"
    if "goal" in tags or "exit" in tags:
        return "X"
    if "hazard" in tags:
        return "!"
    if "pickup" in tags or "collectible" in tags:
        return "*"
    if isinstance(node, MeshAsset):
        return "A"
    if isinstance(node, PrimitiveNode) and node.physics and node.physics.body == "fixed":
        return "#"
    if isinstance(node, SceneObject):
        return "O"
    return "o"


def topdown_map(
    scene: Scene,
    *,
    cell_size: float = 1.0,
    width: int | None = None,
    height: int | None = None,
    focus: Sequence[float] | None = None,
    max_cells: int = 80,
) -> dict[str, Any]:
    """ASCII occupancy map on the XZ plane."""
    if cell_size <= 0:
        raise ValueError("cellSize must be > 0")
    min_x, max_x, min_z, max_z = _map_extent(
        scene,
        focus,
        half_span=(max_cells * cell_size) / 2 if focus is not None else None,
    )
    # Pad empty/degenerate extents.
    if abs(max_x - min_x) < cell_size:
        min_x -= cell_size * 2
        max_x += cell_size * 2
    if abs(max_z - min_z) < cell_size:
        min_z -= cell_size * 2
        max_z += cell_size * 2

    cols = max(1, math.ceil((max_x - min_x) / cell_size))
    rows = max(1, math.ceil((max_z - min_z) / cell_size))
    if width is not None:
        cols = max(1, width)
    if height is not None:
        rows = max(1, height)
    cols = min(cols, max_cells)
    rows = min(rows, max_cells)

    grid = [["." for _ in range(cols)] for _ in range(rows)]
    cells: dict[str, list[str]] = {}
    legend = {
        ".": "empty",
        "P": "player",
        "G": "ground",
        "#": "solid/fixed",
        "A": "mesh asset",
        "O": "object",
        "o": "primitive",
        "X": "goal",
        "!": "hazard",
        "*": "pickup",
        "z": "zone",
        "?": "unknown",
    }

    def cell_for(x: float, z: float) -> tuple[int, int] | None:
        col = int((x - min_x) / cell_size)
        # Row 0 is north (-Z / min_z) so the ASCII map reads naturally top=north.
        row = int((z - min_z) / cell_size)
        row = rows - 1 - row
        if 0 <= col < cols and 0 <= row < rows:
            return row, col
        return None

    env = scene.environment
    if env is not None:
        for zone in env.zones.values():
            cx = (zone.min[0] + zone.max[0]) / 2
            cz = (zone.min[2] + zone.max[2]) / 2
            loc = cell_for(cx, cz)
            if loc is None:
                continue
            row, col = loc
            if grid[row][col] == ".":
                grid[row][col] = "z"
            key = f"{col},{row}"
            cells.setdefault(key, []).append(f"zone:{zone.id}")

    for node_id in sorted(scene._graph_nodes()):
        world = scene.world_transform(node_id)
        x, z = float(world["position"][0]), float(world["position"][2])
        loc = cell_for(x, z)
        if loc is None:
            continue
        row, col = loc
        symbol = _symbol_for_node(scene, node_id)
        priority = {
            ".": 0,
            "z": 1,
            "o": 2,
            "O": 3,
            "G": 4,
            "A": 5,
            "#": 6,
            "*": 7,
            "!": 8,
            "X": 9,
            "P": 10,
        }
        if priority.get(symbol, 0) >= priority.get(grid[row][col], 0):
            grid[row][col] = symbol
        key = f"{col},{row}"
        cells.setdefault(key, []).append(node_id)

    ascii_rows = ["".join(row) for row in grid]
    return {
        "ascii": "\n".join(ascii_rows),
        "axes": AXES,
        "cellSize": cell_size,
        "origin": {"x": min_x, "z": min_z},
        "extent": {"minX": min_x, "maxX": max_x, "minZ": min_z, "maxZ": max_z},
        "width": cols,
        "height": rows,
        "cells": cells,
        "legend": legend,
        "note": "Row 0 (top of ascii) is north (-Z). Column 0 is west (-X / minX).",
    }


def _resolve_point(
    scene: Scene,
    *,
    node_id: str | None = None,
    point: Sequence[float] | None = None,
) -> list[float]:
    if point is not None:
        values = list(point)
        if len(values) != 3:
            raise ValueError("point must be [x, y, z]")
        return [float(v) for v in values]
    if not node_id:
        raise ValueError("Provide id or point")
    if node_id in scene._graph_nodes():
        return list(scene.world_transform(node_id)["position"])
    if node_id in scene._annotations:
        return _annotation_world_position(scene, scene._annotations[node_id])
    raise KeyError(f"Unknown node id {node_id!r}")


def spatial_query(
    scene: Scene,
    *,
    mode: SpatialMode,
    id: str | None = None,
    from_id: str | None = None,
    to_id: str | None = None,
    point: Sequence[float] | None = None,
    k: int = 5,
    radius: float | None = None,
    tag: str | None = None,
    kind: NodeKind | None = None,
    x: float | None = None,
    z: float | None = None,
) -> dict[str, Any]:
    """Spatial relations over world positions."""
    if mode == "height_at":
        if x is None or z is None:
            raise ValueError("height_at requires x and z")
        env = scene.environment
        if env is None:
            raise ValueError("Scene has no environment; call set_environment first")
        return {
            "mode": mode,
            "x": float(x),
            "z": float(z),
            "y": float(env.height_at(float(x), float(z))),
        }

    if mode == "distance":
        origin_point = point if from_id is None and id is None else None
        a = _resolve_point(scene, node_id=from_id or id, point=origin_point)
        b = _resolve_point(scene, node_id=to_id)
        return {
            "mode": mode,
            "from": from_id or id or point,
            "to": to_id,
            "distance": _distance(a, b),
            "delta": [b[i] - a[i] for i in range(3)],
        }

    if mode == "relative":
        origin_id = from_id or id
        if not origin_id or not to_id:
            raise ValueError("relative requires fromId/id and toId")
        a = _resolve_point(scene, node_id=origin_id)
        b = _resolve_point(scene, node_id=to_id)
        delta = [b[i] - a[i] for i in range(3)]
        bearing, yaw = _bearing_xz(delta[0], delta[2])
        return {
            "mode": mode,
            "from": origin_id,
            "to": to_id,
            "distance": _distance(a, b),
            "delta": delta,
            "bearing": bearing,
            "yawDegrees": yaw,
            "elevation": delta[1],
            "axes": AXES,
        }

    origin = _resolve_point(scene, node_id=id, point=point)
    tag_l = tag.lower() if tag else None
    candidates: list[tuple[float, str, list[float]]] = []
    for node_id, node in scene._graph_nodes().items():
        if id is not None and node_id == id:
            continue
        if kind is not None and _node_kind(node) != kind:
            continue
        if tag_l is not None and tag_l not in {t.lower() for t in node.tags}:
            continue
        pos = list(scene.world_transform(node_id)["position"])
        dist = _distance(origin, pos)
        candidates.append((dist, node_id, pos))
    candidates.sort(key=lambda item: (item[0], item[1]))

    if mode == "nearest":
        top = candidates[: max(1, k)]
        return {
            "mode": mode,
            "origin": {"id": id, "point": origin},
            "k": k,
            "results": [
                {
                    "id": node_id,
                    "distance": dist,
                    "worldPosition": pos,
                    **(
                        {"bearing": _bearing_xz(pos[0] - origin[0], pos[2] - origin[2])[0]}
                    ),
                }
                for dist, node_id, pos in top
            ],
        }

    if mode == "in_radius":
        if radius is None or radius < 0:
            raise ValueError("in_radius requires radius >= 0")
        inside = [item for item in candidates if item[0] <= radius]
        return {
            "mode": mode,
            "origin": {"id": id, "point": origin},
            "radius": radius,
            "count": len(inside),
            "results": [
                {"id": node_id, "distance": dist, "worldPosition": pos}
                for dist, node_id, pos in inside
            ],
        }

    raise ValueError(f"Unsupported spatial mode: {mode!r}")


def get_bounds(scene: Scene, node_id: str | None = None) -> dict[str, Any]:
    """Bounds for one node or the whole scene."""
    if node_id is None:
        return {"scope": "scene", **scene_bounds(scene)}
    return {"scope": "node", **node_bounds(scene, node_id)}


def apply_perception(scene: Scene, command: Mapping[str, Any]) -> dict[str, Any]:
    """Dispatch a perception action against a scene."""
    action = command.get("action")
    if action == "describe_scene":
        tags = command.get("tags")
        roots = command.get("roots")
        return describe_scene(
            scene,
            detail=str(command.get("detail") or "summary"),  # type: ignore[arg-type]
            tags=tags if isinstance(tags, list) else None,
            roots=roots if isinstance(roots, list) else None,
            max_nodes=int(command.get("maxNodes") or 200),
            include_annotations=bool(command.get("includeAnnotations", True)),
        )
    if action == "get_node":
        node_id = command.get("id")
        if not isinstance(node_id, str) or not node_id:
            raise ValueError("get_node requires id")
        return get_node(scene, node_id, include_bounds=bool(command.get("includeBounds", True)))
    if action == "list_nodes":
        parent = command.get("parentId", ...)
        return list_nodes(
            scene,
            tag=command.get("tag") if isinstance(command.get("tag"), str) else None,
            kind=command.get("kind") if isinstance(command.get("kind"), str) else None,  # type: ignore[arg-type]
            query=command.get("query") if isinstance(command.get("query"), str) else None,
            parent_id=parent,
            page_offset=int(command.get("pageOffset") or 0),
            limit=int(command.get("limit") or 50),
        )
    if action == "topdown_map":
        focus = command.get("focus")
        return topdown_map(
            scene,
            cell_size=float(command.get("cellSize") or 1.0),
            width=int(command["width"]) if "width" in command else None,
            height=int(command["height"]) if "height" in command else None,
            focus=focus if isinstance(focus, list) else None,
            max_cells=int(command.get("maxCells") or 80),
        )
    if action == "spatial_query":
        mode = command.get("mode")
        if not isinstance(mode, str):
            raise ValueError("spatial_query requires mode")
        return spatial_query(
            scene,
            mode=mode,  # type: ignore[arg-type]
            id=command.get("id") if isinstance(command.get("id"), str) else None,
            from_id=command.get("fromId") if isinstance(command.get("fromId"), str) else None,
            to_id=command.get("toId") if isinstance(command.get("toId"), str) else None,
            point=command.get("point") if isinstance(command.get("point"), list) else None,
            k=int(command.get("k") or 5),
            radius=float(command["radius"]) if "radius" in command else None,
            tag=command.get("tag") if isinstance(command.get("tag"), str) else None,
            kind=command.get("kind") if isinstance(command.get("kind"), str) else None,  # type: ignore[arg-type]
            x=float(command["x"]) if "x" in command else None,
            z=float(command["z"]) if "z" in command else None,
        )
    if action == "get_bounds":
        node_id = command.get("id")
        return get_bounds(scene, node_id if isinstance(node_id, str) else None)
    raise ValueError(f"Unsupported perception action: {action!r}")
