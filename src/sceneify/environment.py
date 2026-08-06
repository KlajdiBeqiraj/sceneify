"""Geometric environment: bounds, zones, ground, snap grid, and rules."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

from sceneify.types import Vec3, as_vec3

RuleMode = Literal["off", "warn", "clamp", "reject"]
ZoneRole = Literal["allowed", "forbidden", "marker"]
ZoneShape = Literal["box"]


class RuleKind(StrEnum):
    INSIDE_BOUNDS = "inside_bounds"
    ABOVE_GROUND = "above_ground"
    OUTSIDE_FORBIDDEN = "outside_forbidden"
    INSIDE_ALLOWED = "inside_allowed"
    SNAP_TO_GRID = "snap_to_grid"


@dataclass
class Bounds:
    """Axis-aligned bounding box for the playable volume."""

    min: Vec3
    max: Vec3
    visible: bool = True
    color: str = "#6c8cff"

    def __post_init__(self) -> None:
        for i, axis in enumerate("xyz"):
            if self.min[i] > self.max[i]:
                raise ValueError(f"Bounds min.{axis} must be <= max.{axis}")

    def contains(self, point: Sequence[float]) -> bool:
        p = as_vec3(point)
        return (
            self.min[0] <= p[0] <= self.max[0]
            and self.min[1] <= p[1] <= self.max[1]
            and self.min[2] <= p[2] <= self.max[2]
        )

    def clamp(self, point: Sequence[float]) -> Vec3:
        p = as_vec3(point)
        return (
            min(max(p[0], self.min[0]), self.max[0]),
            min(max(p[1], self.min[1]), self.max[1]),
            min(max(p[2], self.min[2]), self.max[2]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "min": list(self.min),
            "max": list(self.max),
            "visible": self.visible,
            "color": self.color,
        }


@dataclass
class GroundPlane:
    """Infinite ground plane at constant Y (or custom normal later)."""

    y: float = 0.0
    visible: bool = True
    color: str = "#3d4450"

    def to_dict(self) -> dict[str, Any]:
        return {"y": self.y, "visible": self.visible, "color": self.color}


@dataclass
class SnapGrid:
    """Uniform snap spacing along X/Y/Z (set an axis to 0 to disable)."""

    size: Vec3 = (0.1, 0.1, 0.1)
    visible: bool = True

    def snap(self, point: Sequence[float]) -> Vec3:
        p = as_vec3(point)
        out: list[float] = []
        for value, step in zip(p, self.size, strict=True):
            if step <= 0:
                out.append(value)
            else:
                out.append(round(value / step) * step)
        return (out[0], out[1], out[2])

    def to_dict(self) -> dict[str, Any]:
        return {"size": list(self.size), "visible": self.visible}


@dataclass
class Zone:
    """Named geometric region used by allowed/forbidden rules."""

    id: str
    role: ZoneRole = "marker"
    shape: ZoneShape = "box"
    min: Vec3 = (0.0, 0.0, 0.0)
    max: Vec3 = (1.0, 1.0, 1.0)
    label: str | None = None
    visible: bool = True
    color: str = "#56ccf2"
    opacity: float = 0.18
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for i, axis in enumerate("xyz"):
            if self.min[i] > self.max[i]:
                raise ValueError(f"Zone {self.id!r} min.{axis} must be <= max.{axis}")

    def contains(self, point: Sequence[float]) -> bool:
        if self.shape != "box":
            raise NotImplementedError(f"Zone shape {self.shape!r} is not implemented")
        p = as_vec3(point)
        return (
            self.min[0] <= p[0] <= self.max[0]
            and self.min[1] <= p[1] <= self.max[1]
            and self.min[2] <= p[2] <= self.max[2]
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "shape": self.shape,
            "min": list(self.min),
            "max": list(self.max),
            "label": self.label,
            "visible": self.visible,
            "color": self.color,
            "opacity": self.opacity,
            "meta": self.meta,
        }


@dataclass
class GeometricRule:
    """A named geometric constraint applied when validating / placing nodes."""

    kind: RuleKind
    mode: RuleMode = "warn"
    enabled: bool = True
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "mode": self.mode,
            "enabled": self.enabled,
            "meta": self.meta,
        }


@dataclass
class RuleViolation:
    rule: RuleKind
    mode: RuleMode
    node_id: str
    message: str
    point: Vec3
    suggested: Vec3 | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule.value,
            "mode": self.mode,
            "node_id": self.node_id,
            "message": self.message,
            "point": list(self.point),
            "suggested": list(self.suggested) if self.suggested is not None else None,
        }


@dataclass
class WorldMesh:
    """A GLB/glTF (or other mesh) used as the physical/visual world environment."""

    source: str
    format: str | None = "glb"
    position: Vec3 = (0.0, 0.0, 0.0)
    rotation: Vec3 = (0.0, 0.0, 0.0)
    scale: Vec3 = (1.0, 1.0, 1.0)
    visible: bool = True
    collide: bool = True
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "format": self.format,
            "position": list(self.position),
            "rotation": list(self.rotation),
            "scale": list(self.scale),
            "visible": self.visible,
            "collide": self.collide,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorldMesh:
        return cls(
            source=str(data["source"]),
            format=data.get("format"),
            position=as_vec3(data.get("position")),
            rotation=as_vec3(data.get("rotation")),
            scale=as_vec3(data.get("scale"), (1.0, 1.0, 1.0)),
            visible=bool(data.get("visible", True)),
            collide=bool(data.get("collide", True)),
            meta=dict(data.get("meta") or {}),
        )


@dataclass
class Environment:
    """Scene environment: world mesh, volume, ground, snap, zones, and geometric rules."""

    bounds: Bounds | None = None
    ground: GroundPlane | None = None
    snap_grid: SnapGrid | None = None
    world_mesh: WorldMesh | None = None
    zones: dict[str, Zone] = field(default_factory=dict)
    rules: dict[str, GeometricRule] = field(default_factory=dict)
    show_axes: bool = True
    meta: dict[str, Any] = field(default_factory=dict)
    _collision_mesh: Any = field(default=None, repr=False, compare=False)

    def set_bounds(
        self,
        min_point: Sequence[float],
        max_point: Sequence[float],
        *,
        visible: bool = True,
        color: str = "#6c8cff",
    ) -> Bounds:
        self.bounds = Bounds(
            min=as_vec3(min_point),
            max=as_vec3(max_point),
            visible=visible,
            color=color,
        )
        return self.bounds

    def set_ground(
        self,
        y: float = 0.0,
        *,
        visible: bool = True,
        color: str = "#3d4450",
    ) -> GroundPlane:
        self.ground = GroundPlane(y=y, visible=visible, color=color)
        return self.ground

    def set_snap_grid(
        self,
        size: float | Sequence[float] = 0.1,
        *,
        visible: bool = True,
    ) -> SnapGrid:
        if isinstance(size, (int, float)):
            vec = (float(size), float(size), float(size))
        else:
            vec = as_vec3(size)
        self.snap_grid = SnapGrid(size=vec, visible=visible)
        return self.snap_grid

    def set_world_glb(
        self,
        source: str,
        *,
        position: Sequence[float] | None = None,
        rotation: Sequence[float] | None = None,
        scale: Sequence[float] | None = None,
        visible: bool = True,
        collide: bool = True,
        **meta: Any,
    ) -> WorldMesh:
        """Use a GLB/glTF file as the world environment mesh."""
        return self.set_world_mesh(
            source,
            format="glb",
            position=position,
            rotation=rotation,
            scale=scale,
            visible=visible,
            collide=collide,
            **meta,
        )

    def set_world_mesh(
        self,
        source: str,
        *,
        format: str | None = None,
        position: Sequence[float] | None = None,
        rotation: Sequence[float] | None = None,
        scale: Sequence[float] | None = None,
        visible: bool = True,
        collide: bool = True,
        **meta: Any,
    ) -> WorldMesh:
        inferred = format
        if inferred is None:
            lower = source.lower().split("?", 1)[0]
            for ext in (".glb", ".gltf", ".ply", ".obj", ".stl"):
                if lower.endswith(ext):
                    inferred = ext.lstrip(".")
                    break
        self.world_mesh = WorldMesh(
            source=source,
            format=inferred,
            position=as_vec3(position),
            rotation=as_vec3(rotation),
            scale=as_vec3(scale, (1.0, 1.0, 1.0)),
            visible=visible,
            collide=collide,
            meta=meta,
        )
        self._collision_mesh = None
        return self.world_mesh

    def height_at(self, x: float, z: float, *, fallback: float | None = None) -> float:
        """Return surface height at (x, z) from world mesh collision or ground plane."""
        if self.world_mesh is not None and self.world_mesh.collide:
            hit = self._raycast_world_height(x, z)
            if hit is not None:
                return hit
        if self.ground is not None:
            return self.ground.y
        if fallback is not None:
            return fallback
        return 0.0

    def _raycast_world_height(self, x: float, z: float) -> float | None:
        mesh = self._ensure_collision_mesh()
        if mesh is None:
            return None
        try:
            import numpy as np
        except ImportError:
            return None
        origin = np.array([x, 1.0e6, z], dtype=float)
        direction = np.array([0.0, -1.0, 0.0], dtype=float)
        locations, _index_ray, _index_tri = mesh.ray.intersects_location(
            ray_origins=origin.reshape(1, 3),
            ray_directions=direction.reshape(1, 3),
        )
        if len(locations) == 0:
            return None
        return float(max(locations[:, 1]))

    def _ensure_collision_mesh(self) -> Any:
        if self._collision_mesh is not None:
            return self._collision_mesh
        if self.world_mesh is None:
            return None
        try:
            import trimesh
        except ImportError:
            return None
        path = self.world_mesh.source
        try:
            loaded = trimesh.load(path, force="scene")
        except Exception:
            return None
        if isinstance(loaded, trimesh.Scene):
            geoms = [g for g in loaded.geometry.values() if hasattr(g, "faces")]
            if not geoms:
                return None
            mesh = trimesh.util.concatenate(geoms)
        else:
            mesh = loaded
        # Apply environment world transform (scale, then rotate XYZ, then translate).
        import numpy as np

        scale = np.array(self.world_mesh.scale, dtype=float)
        mesh.apply_scale(scale)
        rx, ry, rz = self.world_mesh.rotation
        mesh.apply_transform(trimesh.transformations.euler_matrix(rx, ry, rz, axes="sxyz"))
        mesh.apply_translation(self.world_mesh.position)
        self._collision_mesh = mesh
        return mesh

    def add_zone(
        self,
        zone_id: str,
        *,
        role: ZoneRole = "marker",
        shape: ZoneShape = "box",
        min_point: Sequence[float],
        max_point: Sequence[float],
        label: str | None = None,
        visible: bool = True,
        color: str | None = None,
        opacity: float = 0.18,
        **meta: Any,
    ) -> Zone:
        if zone_id in self.zones:
            raise ValueError(f"Environment already has zone {zone_id!r}")
        default_colors = {
            "allowed": "#27ae60",
            "forbidden": "#eb5757",
            "marker": "#56ccf2",
        }
        zone = Zone(
            id=zone_id,
            role=role,
            shape=shape,
            min=as_vec3(min_point),
            max=as_vec3(max_point),
            label=label,
            visible=visible,
            color=color or default_colors[role],
            opacity=opacity,
            meta=meta,
        )
        self.zones[zone_id] = zone
        return zone

    def add_rule(
        self,
        kind: RuleKind | str,
        *,
        mode: RuleMode = "warn",
        enabled: bool = True,
        rule_id: str | None = None,
        **meta: Any,
    ) -> GeometricRule:
        parsed = RuleKind(kind) if not isinstance(kind, RuleKind) else kind
        key = rule_id or parsed.value
        if key in self.rules:
            raise ValueError(f"Environment already has rule {key!r}")
        rule = GeometricRule(kind=parsed, mode=mode, enabled=enabled, meta=meta)
        self.rules[key] = rule
        return rule

    def apply_point(
        self,
        point: Sequence[float],
        *,
        node_id: str = "<point>",
        raise_on_reject: bool = True,
    ) -> tuple[Vec3, list[RuleViolation]]:
        """Apply enabled geometric rules to a point.

        Returns the (possibly clamped) point and any recorded violations.
        """
        current = as_vec3(point)
        violations: list[RuleViolation] = []

        for rule in self.rules.values():
            if not rule.enabled or rule.mode == "off":
                continue

            if rule.kind == RuleKind.SNAP_TO_GRID and self.snap_grid is not None:
                snapped = self.snap_grid.snap(current)
                if snapped != current:
                    violations.append(
                        RuleViolation(
                            rule=rule.kind,
                            mode=rule.mode,
                            node_id=node_id,
                            message="Point snapped to grid",
                            point=current,
                            suggested=snapped,
                        )
                    )
                    if rule.mode in {"clamp", "warn"}:
                        current = snapped
                    elif rule.mode == "reject" and raise_on_reject:
                        raise ValueError(violations[-1].message)

            elif rule.kind == RuleKind.INSIDE_BOUNDS and self.bounds is not None:
                if not self.bounds.contains(current):
                    suggested = self.bounds.clamp(current)
                    violations.append(
                        RuleViolation(
                            rule=rule.kind,
                            mode=rule.mode,
                            node_id=node_id,
                            message="Point is outside environment bounds",
                            point=current,
                            suggested=suggested,
                        )
                    )
                    if rule.mode == "clamp":
                        current = suggested
                    elif rule.mode == "reject" and raise_on_reject:
                        raise ValueError(violations[-1].message)

            elif rule.kind == RuleKind.ABOVE_GROUND and self.ground is not None:
                if current[1] < self.ground.y:
                    suggested = (current[0], self.ground.y, current[2])
                    violations.append(
                        RuleViolation(
                            rule=rule.kind,
                            mode=rule.mode,
                            node_id=node_id,
                            message=f"Point is below ground y={self.ground.y}",
                            point=current,
                            suggested=suggested,
                        )
                    )
                    if rule.mode == "clamp":
                        current = suggested
                    elif rule.mode == "reject" and raise_on_reject:
                        raise ValueError(violations[-1].message)

            elif rule.kind == RuleKind.OUTSIDE_FORBIDDEN:
                for zone in self.zones.values():
                    if zone.role != "forbidden":
                        continue
                    if zone.contains(current):
                        violations.append(
                            RuleViolation(
                                rule=rule.kind,
                                mode=rule.mode,
                                node_id=node_id,
                                message=f"Point is inside forbidden zone {zone.id!r}",
                                point=current,
                                suggested=None,
                            )
                        )
                        if rule.mode == "reject" and raise_on_reject:
                            raise ValueError(violations[-1].message)

            elif rule.kind == RuleKind.INSIDE_ALLOWED:
                allowed = [z for z in self.zones.values() if z.role == "allowed"]
                if allowed and not any(z.contains(current) for z in allowed):
                    violations.append(
                        RuleViolation(
                            rule=rule.kind,
                            mode=rule.mode,
                            node_id=node_id,
                            message="Point is outside all allowed zones",
                            point=current,
                            suggested=None,
                        )
                    )
                    if rule.mode == "reject" and raise_on_reject:
                        raise ValueError(violations[-1].message)

        return current, violations

    def to_dict(self) -> dict[str, Any]:
        return {
            "bounds": self.bounds.to_dict() if self.bounds else None,
            "ground": self.ground.to_dict() if self.ground else None,
            "snapGrid": self.snap_grid.to_dict() if self.snap_grid else None,
            "worldMesh": self.world_mesh.to_dict() if self.world_mesh else None,
            "zones": [z.to_dict() for z in self.zones.values()],
            "rules": [r.to_dict() for r in self.rules.values()],
            "showAxes": self.show_axes,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Environment:
        env = cls(
            show_axes=bool(data.get("showAxes", True)),
            meta=dict(data.get("meta") or {}),
        )
        bounds = data.get("bounds")
        if bounds:
            env.bounds = Bounds(
                min=as_vec3(bounds["min"]),
                max=as_vec3(bounds["max"]),
                visible=bool(bounds.get("visible", True)),
                color=str(bounds.get("color", "#6c8cff")),
            )
        ground = data.get("ground")
        if ground:
            env.ground = GroundPlane(
                y=float(ground.get("y", 0.0)),
                visible=bool(ground.get("visible", True)),
                color=str(ground.get("color", "#3d4450")),
            )
        snap = data.get("snapGrid")
        if snap:
            env.snap_grid = SnapGrid(
                size=as_vec3(snap.get("size"), (0.1, 0.1, 0.1)),
                visible=bool(snap.get("visible", True)),
            )
        world = data.get("worldMesh")
        if world:
            env.world_mesh = WorldMesh.from_dict(world)
        for zone in data.get("zones") or []:
            env.zones[zone["id"]] = Zone(
                id=zone["id"],
                role=zone.get("role", "marker"),
                shape=zone.get("shape", "box"),
                min=as_vec3(zone["min"]),
                max=as_vec3(zone["max"]),
                label=zone.get("label"),
                visible=bool(zone.get("visible", True)),
                color=str(zone.get("color", "#56ccf2")),
                opacity=float(zone.get("opacity", 0.18)),
                meta=dict(zone.get("meta") or {}),
            )
        for rule in data.get("rules") or []:
            kind = RuleKind(rule["kind"])
            key = rule.get("id") or kind.value
            env.rules[key] = GeometricRule(
                kind=kind,
                mode=rule.get("mode", "warn"),
                enabled=bool(rule.get("enabled", True)),
                meta=dict(rule.get("meta") or {}),
            )
        return env


def build_default_environment(
    *,
    bounds_min: Sequence[float] = (-5.0, 0.0, -5.0),
    bounds_max: Sequence[float] = (5.0, 4.0, 5.0),
    ground_y: float = 0.0,
    snap: float | None = 0.1,
) -> Environment:
    """Convenience factory with common geometric defaults."""
    env = Environment()
    env.set_bounds(bounds_min, bounds_max)
    env.set_ground(ground_y)
    if snap is not None:
        env.set_snap_grid(snap)
    env.add_rule(RuleKind.INSIDE_BOUNDS, mode="clamp")
    env.add_rule(RuleKind.ABOVE_GROUND, mode="clamp")
    env.add_rule(RuleKind.OUTSIDE_FORBIDDEN, mode="reject")
    if snap is not None:
        env.add_rule(RuleKind.SNAP_TO_GRID, mode="clamp")
    return env
