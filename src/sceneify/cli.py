"""Minimal CLI entry points."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sceneify.agent_tools import tool_definition
from sceneify.catalog import AssetCatalog
from sceneify.demo_assets import download_public_asset, list_public_assets
from sceneify.export_web import export_web
from sceneify.scene import Scene


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="sceneify", description="sceneify helpers")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch-demo", help="Download a public demo asset into .sceneify_cache")
    fetch.add_argument("name", choices=list_public_assets())
    fetch.add_argument("--force", action="store_true")

    listed = sub.add_parser("list-demos", help="List public demo asset keys")
    listed.set_defaults(command="list-demos")

    sub.add_parser("tool-spec", help="Print the provider independent world action descriptor")

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
        print(json.dumps(tool_definition(), indent=2))
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


if __name__ == "__main__":
    main()
