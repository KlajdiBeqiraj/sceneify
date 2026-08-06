"""sceneify: compose interactive 3D scenes from Python."""

from sceneify.annotations import Annotation
from sceneify.environment import (
    Bounds,
    Environment,
    GeometricRule,
    GroundPlane,
    RuleKind,
    RuleViolation,
    SnapGrid,
    WorldMesh,
    Zone,
    build_default_environment,
)
from sceneify.objects import MeshAsset, SceneObject
from sceneify.scene import Scene
from sceneify.server import ServerHandle
from sceneify.trajectories import Trajectory

__all__ = [
    "Annotation",
    "Bounds",
    "Environment",
    "GeometricRule",
    "GroundPlane",
    "MeshAsset",
    "RuleKind",
    "RuleViolation",
    "Scene",
    "SceneObject",
    "ServerHandle",
    "SnapGrid",
    "Trajectory",
    "WorldMesh",
    "Zone",
    "build_default_environment",
]

__version__ = "0.3.1"
