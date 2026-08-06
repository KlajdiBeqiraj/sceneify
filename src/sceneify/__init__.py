"""sceneify: compose interactive 3D scenes from Python."""

from sceneify.scene import Scene
from sceneify.objects import SceneObject, MeshAsset
from sceneify.annotations import Annotation
from sceneify.trajectories import Trajectory

__all__ = [
    "Scene",
    "SceneObject",
    "MeshAsset",
    "Annotation",
    "Trajectory",
]

__version__ = "0.1.0"
