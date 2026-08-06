"""Minimal CLI entry points."""

from __future__ import annotations

import argparse

from sceneify.demo_assets import download_public_asset, list_public_assets


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="sceneify", description="sceneify helpers")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch-demo", help="Download a public demo asset into .sceneify_cache")
    fetch.add_argument("name", choices=list_public_assets())
    fetch.add_argument("--force", action="store_true")

    listed = sub.add_parser("list-demos", help="List public demo asset keys")
    listed.set_defaults(command="list-demos")

    args = parser.parse_args(argv)

    if args.command == "list-demos":
        for name in list_public_assets():
            print(name)
        return

    if args.command == "fetch-demo":
        path = download_public_asset(args.name, force=args.force)
        print(path)
        return


if __name__ == "__main__":
    main()
