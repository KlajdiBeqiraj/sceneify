"""Minimal CLI entry points."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sceneify.agent_tools import WorldTools, tool_definition, tool_definitions
from sceneify.catalog import AssetCatalog
from sceneify.demo_assets import download_public_asset, list_public_assets
from sceneify.export_web import export_web
from sceneify.remote_assets import (
    fetch_remote_asset,
    get_remote_asset_info,
    list_remote_assets,
    search_remote_assets,
)
from sceneify.scene import Scene
from sceneify.skills import TARGET_DIRS, bundled_skill_dir, install_skill, open_bundled_skill_dir


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="sceneify", description="sceneify helpers")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch-demo", help="Download a public demo asset into .sceneify_cache")
    fetch.add_argument("name", choices=list_public_assets())
    fetch.add_argument("--force", action="store_true")

    listed = sub.add_parser("list-demos", help="List public demo asset keys")
    listed.set_defaults(command="list-demos")

    tool_spec = sub.add_parser(
        "tool-spec", help="Print the provider independent world action descriptor"
    )
    tool_spec.add_argument(
        "--all",
        action="store_true",
        help="Print the full multi-tool descriptor list used by MCP adapters",
    )

    validate_catalog = sub.add_parser("validate-catalog", help="Validate an asset catalog")
    validate_catalog.add_argument("path")

    export = sub.add_parser(
        "export-web",
        help="Export a static viewer frontend that connects to a sceneify backend",
    )
    export.add_argument("scene", help="Path to a sceneify JSON document")
    export.add_argument(
        "--out",
        default="dist-web",
        help="Output directory for the static viewer (default: dist-web)",
    )
    export.add_argument(
        "--api-base",
        default="http://127.0.0.1:8765",
        help="Backend origin the viewer should call (default: http://127.0.0.1:8765)",
    )
    export.add_argument(
        "--no-copy-assets",
        action="store_true",
        help="Do not pack local assets; keep loading them via the backend API",
    )
    export.add_argument(
        "--optimize-assets",
        action="store_true",
        help="Best-effort GLB rewrite with trimesh when available",
    )
    export.add_argument(
        "--project-root",
        default=None,
        help="Root used to resolve relative asset paths (default: scene file parent)",
    )

    list_remote = sub.add_parser("list-remote", help="List remote assets with pagination")
    list_remote.add_argument("--query")
    list_remote.add_argument("--provider", default="polyhaven")
    list_remote.add_argument("--type", default="models")
    list_remote.add_argument("--offset", type=int, default=0)
    list_remote.add_argument("--limit", type=int, default=25)

    search_remote = sub.add_parser(
        "search-remote", help="Search remote CC0 assets (polyhaven or os3a)"
    )
    search_remote.add_argument("query")
    search_remote.add_argument("--provider", default="polyhaven")
    search_remote.add_argument(
        "--type",
        default="models",
        help="polyhaven: models|hdris; os3a: environments|models",
    )
    search_remote.add_argument("--offset", type=int, default=0)
    search_remote.add_argument("--limit", type=int, default=12)

    info_remote = sub.add_parser("info-remote", help="Show metadata/files for one remote asset")
    info_remote.add_argument("remote_id")
    info_remote.add_argument("--provider", default="polyhaven")
    info_remote.add_argument("--no-files", action="store_true")

    fetch_remote = sub.add_parser(
        "fetch-remote", help="Download a remote asset into .sceneify_cache"
    )
    fetch_remote.add_argument("remote_id")
    fetch_remote.add_argument("--provider", default="polyhaven")
    fetch_remote.add_argument("--id", dest="catalog_id")
    fetch_remote.add_argument("--resolution", default="1k")
    fetch_remote.add_argument(
        "--type",
        default="models",
        help="polyhaven: models|hdris; os3a: environments|models",
    )
    fetch_remote.add_argument("--cache-dir")
    fetch_remote.add_argument("--catalog", help="Optional catalog path to upsert into")
    fetch_remote.add_argument("--force", action="store_true")

    apply_cmd = sub.add_parser("apply", help="Apply one JSON action or a JSON array of actions")
    apply_cmd.add_argument("actions_path", help="Path to a JSON object or array of actions")
    apply_cmd.add_argument("--scene", help="Optional scene path to load first")
    apply_cmd.add_argument("--catalog", help="Optional catalog path to load")
    apply_cmd.add_argument("--save", help="Optional path to save the resulting scene")
    apply_cmd.add_argument("--name", default="cli-world")

    install_skill_cmd = sub.add_parser(
        "install-skill",
        help="Install the bundled sceneify MCP Agent Skill for coding agents",
    )
    install_skill_cmd.add_argument(
        "--target",
        default="agents",
        choices=[*sorted(TARGET_DIRS), "all"],
        help="Skill directory target (default: agents → .agents/skills)",
    )
    install_skill_cmd.add_argument(
        "--user",
        action="store_true",
        help="Install under the home directory instead of the current project",
    )
    install_skill_cmd.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing installed skill directory",
    )
    install_skill_cmd.add_argument(
        "--dir",
        default=".",
        help="Project root used for non --user installs (default: current directory)",
    )

    skill_path = sub.add_parser(
        "skill-path",
        help="Print the path to the bundled sceneify MCP Agent Skill",
    )
    skill_path.set_defaults(command="skill-path")

    args = parser.parse_args(argv)

    if args.command == "list-demos":
        for name in list_public_assets():
            print(name)
        return

    if args.command == "fetch-demo":
        path = download_public_asset(args.name, force=args.force)
        print(path)
        return

    if args.command == "tool-spec":
        payload = tool_definitions() if args.all else tool_definition()
        print(json.dumps(payload, indent=2))
        return

    if args.command == "validate-catalog":
        catalog = AssetCatalog.load(args.path)
        print(f"Valid catalog with {len(catalog.assets)} assets")
        return

    if args.command == "export-web":
        scene_path = Path(args.scene).expanduser().resolve()
        scene = Scene.load(scene_path)
        project_root = (
            Path(args.project_root).expanduser().resolve()
            if args.project_root
            else scene_path.parent
        )
        out = export_web(
            scene,
            args.out,
            api_base=args.api_base,
            copy_assets=not args.no_copy_assets,
            project_root=project_root,
            optimize_assets=args.optimize_assets,
        )
        print(f"Exported static viewer to {out}")
        return

    if args.command == "list-remote":
        page = list_remote_assets(
            provider=args.provider,
            asset_type=args.type,
            query=args.query,
            offset=args.offset,
            limit=args.limit,
        )
        print(json.dumps(page, indent=2))
        return

    if args.command == "search-remote":
        page = search_remote_assets(
            args.query,
            provider=args.provider,
            asset_type=args.type,
            offset=args.offset,
            limit=args.limit,
        )
        print(json.dumps(page, indent=2))
        return

    if args.command == "info-remote":
        info = get_remote_asset_info(
            args.remote_id,
            provider=args.provider,
            include_files=not args.no_files,
        )
        print(json.dumps(info, indent=2))
        return

    if args.command == "fetch-remote":
        catalog = AssetCatalog.load(args.catalog) if args.catalog else AssetCatalog()
        asset = fetch_remote_asset(
            args.remote_id,
            provider=args.provider,
            catalog=catalog,
            catalog_id=args.catalog_id,
            cache_dir=args.cache_dir,
            resolution=args.resolution,
            asset_type=args.type,
            force=args.force,
        )
        if args.catalog:
            catalog.save(args.catalog)
        print(json.dumps(asset.to_document(), indent=2))
        return

    if args.command == "apply":
        scene = Scene.load(args.scene) if args.scene else Scene(args.name)
        catalog = AssetCatalog.load(args.catalog) if args.catalog else AssetCatalog()
        tools = WorldTools(scene, catalog)
        payload = json.loads(Path(args.actions_path).read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            result = tools.apply(payload)
            print(json.dumps(result, indent=2))
        elif isinstance(payload, list):
            result = tools.apply_many(payload)
            print(json.dumps(result, indent=2))
        else:
            raise SystemExit("actions JSON must be an object or an array")
        if args.save:
            tools.scene.save(args.save)
            if args.catalog:
                catalog.save(args.catalog)
        return

    if args.command == "skill-path":
        try:
            print(bundled_skill_dir())
        except FileNotFoundError:
            with open_bundled_skill_dir() as path:
                print(path)
        return

    if args.command == "install-skill":
        try:
            paths = install_skill(
                target=args.target,
                user=args.user,
                force=args.force,
                base_dir=Path(args.dir),
            )
        except (FileExistsError, FileNotFoundError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        for path in paths:
            print(path)
        return


if __name__ == "__main__":
    main()
