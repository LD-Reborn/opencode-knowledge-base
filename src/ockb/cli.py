# OpenCode Knowledge Base (ockb) - local hybrid knowledge base MCP server
# Copyright (C) 2026 LD-Reborn
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Command line interface: `ockb serve` for MCP, subcommands for maintenance."""

import argparse
import json
import sys

from . import __version__
from .config import Config
from .embeddings import Embedder
from .store import Store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ockb", description="OpenCode Knowledge Base")
    parser.add_argument("--version", action="version", version=f"ockb {__version__}")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("serve", help="run the MCP stdio server (default)")

    p_add = sub.add_parser("add", help="add a note")
    p_add.add_argument("title")
    p_add.add_argument("content", nargs="?", default="")
    p_add.add_argument("--tags", default="")

    p_search = sub.add_parser("search", help="search notes")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=5)

    p_get = sub.add_parser("get", help="show one note")
    p_get.add_argument("id", type=int)

    p_list = sub.add_parser("list", help="list recent notes")
    p_list.add_argument("--tag", default=None)
    p_list.add_argument("--limit", type=int, default=50)

    p_delete = sub.add_parser("delete", help="delete a note")
    p_delete.add_argument("id", type=int)

    sub.add_parser("reindex", help="recompute all embeddings")
    sub.add_parser("status", help="show storage and embedding status")

    args = parser.parse_args(argv)
    if args.cmd in (None, "serve"):
        from .server import serve

        serve()
        return 0

    cfg = Config.from_env()
    store = Store(cfg)
    embedder = Embedder(cfg.ollama_url, cfg.embed_model, cfg.embed_enabled)

    if args.cmd == "add":
        note_id = store.add(args.title, args.content, args.tags, embedder=embedder)
        print(json.dumps({"id": note_id, "embedded": embedder.enabled}))
    elif args.cmd == "search":
        print(json.dumps(store.search(args.query, limit=args.limit, embedder=embedder), indent=2))
    elif args.cmd == "get":
        print(json.dumps(store.get(args.id), indent=2))
    elif args.cmd == "list":
        print(json.dumps(store.list(tag=args.tag, limit=args.limit), indent=2))
    elif args.cmd == "delete":
        print(json.dumps({"deleted": store.delete(args.id)}))
    elif args.cmd == "reindex":
        print(json.dumps(store.reindex(embedder)))
    elif args.cmd == "status":
        stats = store.stats()
        stats["ollama_url"] = cfg.ollama_url
        stats["embed_model"] = cfg.embed_model
        stats["embed_ready"] = embedder.ready()
        print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
