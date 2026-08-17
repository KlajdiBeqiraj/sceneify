"""sceneify: compose interactive 3D scenes from Python."""

from sceneify.agent_tools import WorldTools, tool_definition, tool_definitions
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
from sceneify.episode import Episode, EpisodeEvent
from sceneify.game import (
    HUD,
    ActionMap,
    CameraFollow,
    Checkpoint,
    Collectible,
    ControllerPreset,
    Game,
    GameManifest,
    Goal,
    Hazard,
    ThirdPersonController,
    Timer,
)
from sceneify.objects import Material, MeshAsset, Physics, PrimitiveNode, SceneObject
from sceneify.perception import (
    describe_scene,
    get_bounds,
    get_node,
    list_nodes,
    spatial_query,
    topdown_map,
)
from sceneify.prefabs import Prefab
from sceneify.realtime import InputEvent, SemanticEvent
from sceneify.remote_assets import (
    fetch_remote_asset,
    get_remote_asset_info,
    list_remote_assets,
    search_remote_assets,
)
from sceneify.scene import Scene
from sceneify.schema import load_schema
from sceneify.server import ServerHandle
from sceneify.skills import install_skill
from sceneify.source_sync import save_python, source_sync_report
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
    "ControllerPreset",
    "Environment",
    "Episode",
    "EpisodeEvent",
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
    "Prefab",
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
    "describe_scene",
    "fetch_remote_asset",
    "get_bounds",
    "get_node",
    "get_remote_asset_info",
    "install_skill",
    "list_nodes",
    "list_remote_assets",
    "load_schema",
    "save_python",
    "search_remote_assets",
    "source_sync_report",
    "spatial_query",
    "tool_definition",
    "tool_definitions",
    "topdown_map",
]

__version__ = "0.0.1"
