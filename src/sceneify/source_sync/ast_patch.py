"""Level-2 AST patching of imperative sceneify authoring calls via parso."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from sceneify.scene import Scene
from sceneify.source_sync.emit import emit_build_scene

try:
    import parso
except ImportError:  # pragma: no cover
    parso = None  # type: ignore[assignment]

AUTHORING_METHODS = {
    "create_primitive",
    "add_glb",
    "add_mesh",
    "add_object",
    "add_annotation",
    "add_primitive",
}


@dataclass
class SourceAnalysis:
    patchable: bool
    patchable_ids: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    has_markers: bool = False
    mode: str = "json"


def _walk(node: Any) -> Iterator[Any]:
    yield node
    for child in getattr(node, "children", []) or []:
        yield from _walk(child)


def analyze_source(source: str) -> SourceAnalysis:
    """Inspect whether a Python file can be AST-patched safely."""
    from sceneify.source_sync.markers import BEGIN_MARKER, END_MARKER

    has_markers = BEGIN_MARKER in source and END_MARKER in source
    if parso is None:
        return SourceAnalysis(
            patchable=False,
            blockers=["parso is not installed"],
            has_markers=has_markers,
            mode="markers" if has_markers else "json",
        )

    tree = parso.parse(source)
    blockers: list[str] = []
    patchable_ids: list[str] = []

    for node in _walk(tree):
        type_name = getattr(node, "type", None)
        if type_name in {"for_stmt", "while_stmt", "listcomp", "genexpr", "dictcomp", "setcomp"}:
            blockers.append(f"dynamic construct: {type_name}")
        if type_name == "atom_expr":
            call = _match_authoring_call(node)
            if call is None:
                continue
            node_id = _literal_id(call)
            if node_id is None:
                blockers.append("authoring call without literal id")
            else:
                patchable_ids.append(node_id)

    unique_ids = sorted(set(patchable_ids))
    patchable = not blockers and bool(unique_ids)
    mode = "ast" if patchable else ("markers" if has_markers else "json")
    return SourceAnalysis(
        patchable=patchable,
        patchable_ids=unique_ids,
        blockers=sorted(set(blockers)),
        has_markers=has_markers,
        mode=mode,
    )


def patch_source_ast(source: str, scene: Scene) -> tuple[str, SourceAnalysis]:
    """Patch literal authoring call transforms; report fallback when unsafe."""
    analysis = analyze_source(source)
    if not analysis.patchable or parso is None:
        return source, analysis

    data = scene.to_dict()
    node_by_id = {
        node["id"]: node
        for group in (
            data.get("meshes") or [],
            data.get("objects") or [],
            data.get("primitives") or [],
            data.get("annotations") or [],
        )
        for node in group
    }
    scene_ids = set(node_by_id)
    missing = sorted(scene_ids - set(analysis.patchable_ids))
    if missing:
        return source, SourceAnalysis(
            patchable=False,
            patchable_ids=analysis.patchable_ids,
            blockers=[*analysis.blockers, f"missing authoring calls for: {', '.join(missing)}"],
            has_markers=analysis.has_markers,
            mode="markers" if analysis.has_markers else "json",
        )

    # Text-level transform kwarg rewrite keyed by literal id (stable for simple scripts).
    updated = source
    for node_id, node in node_by_id.items():
        updated = _patch_call_transforms(updated, node_id, node)

    return updated, analysis


def emit_fallback_body(scene: Scene) -> str:
    return emit_build_scene(scene)


def _match_authoring_call(atom_expr: Any) -> Any | None:
    children = getattr(atom_expr, "children", None)
    if not children or len(children) < 2:
        return None
    name = None
    call_trailer = None
    for child in children:
        if getattr(child, "type", None) != "trailer" or len(child.children) < 2:
            continue
        head = getattr(child.children[0], "value", None)
        if head == "." and getattr(child.children[1], "value", None):
            name = child.children[1].value
        if head == "(":
            call_trailer = child
    if name in AUTHORING_METHODS and call_trailer is not None:
        return call_trailer
    return None


def _literal_id(call_trailer: Any) -> str | None:
    children = call_trailer.children
    if len(children) < 3:
        return None
    arglist = children[1]
    first = arglist.children[0] if getattr(arglist, "children", None) else arglist
    return _string_literal(first)


def _string_literal(node: Any) -> str | None:
    if getattr(node, "type", None) == "string":
        text = node.value
        if len(text) >= 2 and text[0] in {'"', "'"}:
            return text[1:-1]
    children = getattr(node, "children", None)
    if children:
        return _string_literal(children[0])
    return None


def _patch_call_transforms(source: str, node_id: str, node: dict[str, Any]) -> str:
    """Replace position/rotation/scale kwargs on the call whose first arg is node_id."""
    pattern = re.compile(
        rf"""(?P<head>\.(?:create_primitive|add_glb|add_mesh|add_object|add_annotation|add_primitive)\(\s*['"]{re.escape(node_id)}['"])(?P<body>.*?)(?P<tail>\))""",
        re.DOTALL,
    )

    def replacer(match: re.Match[str]) -> str:
        body = match.group("body")
        for key in ("position", "rotation", "scale"):
            values = node.get(key)
            if values is None:
                continue
            replacement = f"{key}=({', '.join(repr(float(v)) for v in values)})"
            body = _replace_kwarg(body, key, replacement)
        return f"{match.group('head')}{body}{match.group('tail')}"

    return pattern.sub(replacer, source, count=1)


def _replace_kwarg(arg_code: str, key: str, replacement: str) -> str:
    pattern = re.compile(rf"{key}\s*=\s*\([^)]*\)")
    if pattern.search(arg_code):
        return pattern.sub(replacement, arg_code, count=1)
    stripped = arg_code.rstrip()
    if not stripped:
        return replacement
    if stripped.endswith(","):
        return f"{stripped} {replacement}"
    return f"{stripped}, {replacement}"
