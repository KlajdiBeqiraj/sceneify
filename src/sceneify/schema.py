"""Access to JSON schemas bundled with the installed package."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal

SchemaName = Literal["scene", "catalog", "episode"]


def load_schema(name: SchemaName) -> dict[str, Any]:
    """Load a bundled sceneify JSON schema."""
    resource = files("sceneify").joinpath("schemas", f"{name}.schema.json")
    if not resource.is_file():
        resource = Path(__file__).resolve().parents[2] / "schemas" / f"{name}.schema.json"
    return json.loads(resource.read_text(encoding="utf-8"))
