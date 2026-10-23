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
"""FastMCP stdio server exposing the knowledge base to OpenCode."""

from mcp.server.mcpserver import MCPServer

from .config import Config
from .embeddings import Embedder
from .store import Store

INSTRUCTIONS = """Personal knowledge base (local SQLite; hybrid full-text + Ollama embedding search).
- search(query) before answering questions about the user's own notes, decisions, or past projects.
- add(title, content, tags) to store durable facts worth remembering across sessions.
- get(id) for a full note; list to browse; update/delete to maintain.
- reindex after changing KB_EMBED_MODEL; stats to check health."""

_cfg = Config.from_env()
_store = Store(_cfg)
_embedder = Embedder(_cfg.ollama_url, _cfg.embed_model, _cfg.embed_enabled)

mcp = MCPServer("knowledgeBase", instructions=INSTRUCTIONS)


@mcp.tool()
def search(query: str, limit: int = 5) -> dict:
    """Hybrid search (full-text + semantic) over the knowledge base.

    Returns ranked results with id, title, tags, snippet, score and matched_by.
    """
    return _store.search(query, limit=limit, embedder=_embedder)


@mcp.tool()
def add(title: str, content: str = "", tags: str = "") -> dict:
    """Add a note to the knowledge base. tags is a comma-separated string.

    Returns the new note id and whether an embedding was stored.
    """
    note_id = _store.add(title, content, tags, embedder=_embedder)
    return {"id": note_id, "embedded": _embedder.enabled}


@mcp.tool()
def get(id: int) -> dict | None:
    """Get one note in full by id."""
    return _store.get(id)


@mcp.tool()
def list(tag: str = "", limit: int = 50) -> dict:
    """List recent notes, optionally filtered by a tag substring."""
    return {"notes": _store.list(tag=tag or None, limit=limit)}


@mcp.tool()
def update(id: int, title: str = "", content: str = "", tags: str = "") -> dict:
    """Update a note. Empty strings leave the field unchanged."""
    ok = _store.update(
        id,
        title=title or None,
        content=content or None,
        tags=tags or None,
        embedder=_embedder,
    )
    return {"updated": ok}


@mcp.tool()
def delete(id: int) -> dict:
    """Delete a note by id."""
    return {"deleted": _store.delete(id)}


@mcp.tool()
def stats() -> dict:
    """Note count, embedding coverage, data dir, and embedding availability."""
    stats = _store.stats()
    stats["embed_model"] = _embedder.model
    stats["embed_ready"] = _embedder.ready()
    if not stats["embed_ready"] and _embedder.last_error:
        stats["embed_error"] = _embedder.last_error
    return stats


@mcp.tool()
def reindex() -> dict:
    """Recompute embeddings for all notes (run after changing KB_EMBED_MODEL)."""
    return _store.reindex(_embedder)


def serve() -> None:
    mcp.run()  # stdio transport
