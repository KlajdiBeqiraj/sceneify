"""sceneify: compose interactive 3D scenes from Python."""

from sceneify.agent_tools import WorldTools, tool_definition
from sceneify.annotations import Annotation
from sceneify.catalog import Asset, AssetCatalog
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
from sceneify.game import (
    HUD,
    ActionMap,
    CameraFollow,
    Checkpoint,
    Collectible,
    Game,
    GameManifest,
    Goal,
    Hazard,
    ThirdPersonController,
    Timer,
)
from sceneify.objects import Material, MeshAsset, Physics, PrimitiveNode, SceneObject
from sceneify.realtime import InputEvent, SemanticEvent
from sceneify.scene import Scene
from sceneify.schema import load_schema
from sceneify.server import ServerHandle
from sceneify.trajectories import Trajectory

__all__ = [
    "HUD",
    "ActionMap",
    "Annotation",
    "Asset",
    "AssetCatalog",
    "Bounds",
    "CameraFollow",
    "Checkpoint",
    "Collectible",
    "Environment",
    "Game",
    "GameManifest",
    "GeometricRule",
    "Goal",
    "GroundPlane",
    "Hazard",
    "InputEvent",
    "Material",
    "MeshAsset",
    "Physics",
    "PrimitiveNode",
    "RuleKind",
    "RuleViolation",
    "Scene",
    "SceneObject",
    "SemanticEvent",
    "ServerHandle",
    "SnapGrid",
    "ThirdPersonController",
    "Timer",
    "Trajectory",
    "WorldMesh",
    "WorldTools",
    "Zone",
    "build_default_environment",
    "load_schema",
    "tool_definition",
]

__version__ = "0.4.0"
