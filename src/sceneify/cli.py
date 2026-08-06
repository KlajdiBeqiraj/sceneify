"""Minimal CLI entry points."""

from __future__ import annotations

import argparse
import json

from sceneify.agent_tools import tool_definition
from sceneify.catalog import AssetCatalog
from sceneify.demo_assets import download_public_asset, list_public_assets


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


if __name__ == "__main__":
    main()
