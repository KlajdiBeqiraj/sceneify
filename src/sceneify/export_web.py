"""Export a hostable static viewer that talks to a sceneify Python backend."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from sceneify.io import scene_document

if TYPE_CHECKING:
    from sceneify.scene import Scene

PACKAGE_WEB = Path(__file__).resolve().parent / "_web"
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def export_web(
    scene: Scene,
    out_dir: str | Path,
    *,
    api_base: str = "http://127.0.0.1:8765",
    copy_assets: bool = True,
    project_root: str | Path | None = None,
    optimize_assets: bool = False,
) -> Path:
    """Write a static viewer bundle that connects to a live sceneify backend.

    The export is a frontend package (HTML/JS/CSS + optional packed assets). The
    Python server remains the source of truth for play loop, commands, and WS.
    """
    target = Path(out_dir).expanduser().resolve()
    web_root = _viewer_root()
    if target == web_root.resolve():
        raise ValueError("Refusing to export into the packaged viewer directory")
    target.mkdir(parents=True, exist_ok=True)

    _copy_viewer(web_root, target)

    root = Path(project_root or Path.cwd()).expanduser().resolve()
    payload = scene.to_dict()
    copied: list[str] = []
    if copy_assets:
        copied = _pack_assets(payload, target / "assets", root, optimize=optimize_assets)

    document = scene_document(scene)
    document["scene"] = payload
    (target / "scene.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    family = _experience_family(payload)
    mode = "play" if family in {"character", "board"} else "look"
    config = {
        "apiBase": api_base.rstrip("/"),
        "sceneFile": "scene.json",
        "assetMode": "static" if copy_assets else "api",
        "copiedAssets": copied,
        "chrome": "none",
        "mode": mode,
    }
    (target / "sceneify.config.json").write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )
    _inject_config(target / "index.html", {**config, "chrome": "editor"})
    _write_embed(target, config)
    (target / "sceneify-element.js").write_text(_element_script(), encoding="utf-8")
    snippets = embed_snippets(api_base=config["apiBase"], mode=mode, src="./embed.html")
    (target / "EMBED.txt").write_text(snippets["readme"], encoding="utf-8")
    (target / "README.sceneify-export.txt").write_text(
        _readme_text(api_base=config["apiBase"], asset_count=len(copied)),
        encoding="utf-8",
    )
    return target


def _viewer_root() -> Path:
    if PACKAGE_WEB.is_dir() and (PACKAGE_WEB / "index.html").is_file():
        return PACKAGE_WEB
    raise FileNotFoundError(
        "Bundled viewer not found at src/sceneify/_web. "
        "Run `npm ci && npm run build` inside web/ first."
    )


def _copy_viewer(web_root: Path, target: Path) -> None:
    for item in web_root.iterdir():
        destination = target / item.name
        if item.is_dir():
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)


def _pack_assets(
    payload: dict[str, Any],
    assets_dir: Path,
    project_root: Path,
    *,
    optimize: bool,
) -> list[str]:
    assets_dir.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()
    copied: list[str] = []
    for source_path, assign in _iter_asset_slots(payload):
        if not source_path or _is_web_url(source_path):
            continue
        local = _resolve_local(project_root, source_path)
        if local is None or not local.is_file():
            continue
        name = _unique_asset_name(local.name, used_names)
        used_names.add(name)
        destination = assets_dir / name
        shutil.copy2(local, destination)
        if optimize:
            _maybe_optimize_glb(destination)
        new_source = f"assets/{name}"
        assign(new_source)
        copied.append(new_source)
    return copied


def _iter_asset_slots(payload: dict[str, Any]):
    for mesh in payload.get("meshes") or []:
        if isinstance(mesh, dict) and isinstance(mesh.get("source"), str):

            def assign(value: str, node: dict[str, Any] = mesh) -> None:
                node["source"] = value

            yield mesh["source"], assign
            material = mesh.get("material")
            if isinstance(material, dict):
                yield from _material_slots(material)

    for obj in payload.get("objects") or []:
        if isinstance(obj, dict) and isinstance(obj.get("material"), dict):
            yield from _material_slots(obj["material"])

    for primitive in payload.get("primitives") or []:
        if isinstance(primitive, dict) and isinstance(primitive.get("material"), dict):
            yield from _material_slots(primitive["material"])

    presentation = payload.get("presentation")
    if isinstance(presentation, dict) and isinstance(presentation.get("environmentMap"), str):

        def assign_env(value: str, node: dict[str, Any] = presentation) -> None:
            node["environmentMap"] = value

        yield presentation["environmentMap"], assign_env

    environment = payload.get("environment")
    if isinstance(environment, dict):
        world = environment.get("worldMesh")
        if isinstance(world, dict) and isinstance(world.get("source"), str):

            def assign_world(value: str, node: dict[str, Any] = world) -> None:
                node["source"] = value

            yield world["source"], assign_world


def _material_slots(material: dict[str, Any]):
    for key in ("baseColorTexture", "normalTexture", "metallicRoughnessTexture"):
        value = material.get(key)
        if isinstance(value, str):

            def assign(
                next_value: str,
                target: dict[str, Any] = material,
                field: str = key,
            ) -> None:
                target[field] = next_value

            yield value, assign


def embed_snippets(
    *,
    api_base: str = "http://127.0.0.1:8765",
    mode: str = "look",
    src: str = "./embed.html",
    chrome: str = "none",
) -> dict[str, str]:
    """Copy-paste iframe and web-component snippets for a host page."""
    iframe = (
        f'<iframe src="{src}" title="Sceneify" '
        'style="width:100%;height:480px;border:0" allow="fullscreen"></iframe>'
    )
    component = (
        '<script src="./sceneify-element.js"></script>\n'
        f'<sceneify-viewer src="{src}" api-base="{api_base}" mode="{mode}" chrome="{chrome}">'
        "</sceneify-viewer>"
    )
    readme = (
        "sceneify embed snippets\n"
        "=======================\n\n"
        "Keep the Python backend running. The viewer talks to it over HTTP/WebSocket.\n\n"
        "iframe:\n"
        f"{iframe}\n\n"
        "web component:\n"
        f"{component}\n"
    )
    return {"iframe": iframe, "webComponent": component, "readme": readme}


def _experience_family(payload: dict[str, Any]) -> str | None:
    experience = payload.get("experience")
    if isinstance(experience, dict) and isinstance(experience.get("family"), str):
        return experience["family"]
    if payload.get("game"):
        return "character"
    return None


def _write_embed(target: Path, config: dict[str, Any]) -> None:
    index = target / "index.html"
    embed = target / "embed.html"
    if index.is_file():
        shutil.copy2(index, embed)
    _inject_config(embed, {**config, "chrome": "none"})


def _element_script() -> str:
    return """(() => {
  class SceneifyViewer extends HTMLElement {
    connectedCallback() {
      if (this.dataset.ready === "1") return;
      this.dataset.ready = "1";
      const iframe = document.createElement("iframe");
      const src = this.getAttribute("src") || "embed.html";
      const url = new URL(src, document.baseURI);
      const api = this.getAttribute("api-base");
      const mode = this.getAttribute("mode") || "look";
      const chrome = this.getAttribute("chrome") || "none";
      if (api) url.searchParams.set("apiBase", api);
      url.searchParams.set("mode", mode);
      url.searchParams.set("chrome", chrome);
      iframe.setAttribute("src", url.toString());
      iframe.setAttribute("title", this.getAttribute("title") || "Sceneify");
      iframe.setAttribute("allow", "fullscreen");
      iframe.style.cssText = "width:100%;height:100%;border:0;display:block;background:transparent";
      this.style.display = this.style.display || "block";
      this.style.width = this.style.width || "100%";
      this.style.height = this.style.height || "480px";
      this.appendChild(iframe);
    }
  }
  if (!customElements.get("sceneify-viewer")) {
    customElements.define("sceneify-viewer", SceneifyViewer);
  }
})();
"""


def _inject_config(index_path: Path, config: dict[str, Any]) -> None:
    if not index_path.is_file():
        raise FileNotFoundError(f"Missing viewer index at {index_path}")
    html = index_path.read_text(encoding="utf-8")
    snippet = (
        f"<script>window.__SCENEIFY_CONFIG__={json.dumps(config, separators=(',', ':'))};</script>"
    )
    if "window.__SCENEIFY_CONFIG__" in html:
        html = re.sub(
            r"<script>window\.__SCENEIFY_CONFIG__=.*?</script>",
            snippet,
            html,
            count=1,
            flags=re.DOTALL,
        )
    elif "<head>" in html:
        html = html.replace("<head>", f"<head>\n    {snippet}", 1)
    else:
        html = snippet + html
    index_path.write_text(html, encoding="utf-8")


def _resolve_local(project_root: Path, source: str) -> Path | None:
    candidate = Path(source)
    if candidate.is_absolute():
        return candidate if candidate.is_file() else None
    relative = (project_root / source).resolve()
    try:
        relative.relative_to(project_root)
    except ValueError:
        return None
    return relative if relative.is_file() else None


def _unique_asset_name(filename: str, used: set[str]) -> str:
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    safe = _SAFE_NAME.sub("_", stem).strip("._") or "asset"
    name = f"{safe}{suffix}"
    if name not in used:
        return name
    index = 2
    while f"{safe}-{index}{suffix}" in used:
        index += 1
    return f"{safe}-{index}{suffix}"


def _maybe_optimize_glb(path: Path) -> None:
    """Best-effort GLB touch-up when trimesh is installed; never fails the export."""
    if path.suffix.lower() != ".glb":
        return
    try:
        import trimesh
    except ImportError:
        return
    try:
        loaded = trimesh.load(path, force="scene")
        exported = loaded.export(file_type="glb")
        if isinstance(exported, (bytes, bytearray)):
            path.write_bytes(exported)
    except Exception:
        return


def _is_web_url(value: str) -> bool:
    return urlparse(value).scheme.lower() in {"http", "https"}


def _readme_text(*, api_base: str, asset_count: int) -> str:
    return (
        "sceneify static web export\n"
        "==========================\n\n"
        "This folder is a hostable viewer frontend. Keep the Python backend running;\n"
        "the browser connects to it for scene sync, play loop, and WebSocket events.\n\n"
        "Embed on another site with embed.html (iframe) or <sceneify-viewer> — see EMBED.txt.\n"
        "Default embed chrome is none (no grid, gizmos, or editor sidebar).\n\n"
        f"Configured apiBase: {api_base or '(same origin)'}\n"
        f"Packed local assets: {asset_count}\n\n"
        "Example:\n"
        "  1) uv run python your_scene.py   # scene.play() / serve backend\n"
        "  2) serve this folder with any static host\n"
        "  3) open the exported index.html in a browser\n"
    )
