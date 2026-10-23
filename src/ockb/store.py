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
"""SQLite storage: notes + FTS5 index + embedding vectors, hybrid search."""

from __future__ import annotations

import math
import re
import sqlite3
import struct
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config
    from .embeddings import Embedder

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    title, content, tags,
    content='notes', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, title, content, tags)
    VALUES (new.id, new.title, new.content, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, content, tags)
    VALUES ('delete', old.id, old.title, old.content, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, content, tags)
    VALUES ('delete', old.id, old.title, old.content, old.tags);
    INSERT INTO notes_fts(rowid, title, content, tags)
    VALUES (new.id, new.title, new.content, new.tags);
END;

CREATE TABLE IF NOT EXISTS embeddings (
    note_id INTEGER PRIMARY KEY REFERENCES notes(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vec BLOB NOT NULL
);
"""


def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class Store:
    def __init__(self, cfg: "Config"):
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        self.cfg = cfg
        # mcp 2.x runs sync tool handlers on worker threads; share one
        # connection across them under a lock.
        self.db = sqlite3.connect(cfg.data_dir / "kb.sqlite3", check_same_thread=False)
        self._lock = threading.RLock()
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(_SCHEMA)
        self.db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self.db.commit()

    # -- writes ---------------------------------------------------------

    def add(self, title: str, content: str = "", tags: str = "", embedder: "Embedder | None" = None) -> int:
        with self._lock:
            now = _utcnow()
            cur = self.db.execute(
                "INSERT INTO notes (title, content, tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (title, content, tags, now, now),
            )
            note_id = cur.lastrowid
            self.db.commit()
            self._embed(note_id, title, content, tags, embedder)
            return note_id

    def update(
        self,
        note_id: int,
        title: str | None = None,
        content: str | None = None,
        tags: str | None = None,
        embedder: "Embedder | None" = None,
    ) -> bool:
        with self._lock:
            note = self.get(note_id)
            if note is None:
                return False
            self.db.execute(
                "UPDATE notes SET title = ?, content = ?, tags = ?, updated_at = ? WHERE id = ?",
                (
                    title if title is not None else note["title"],
                    content if content is not None else note["content"],
                    tags if tags is not None else note["tags"],
                    _utcnow(),
                    note_id,
                ),
            )
            self.db.commit()
            new = self.get(note_id)
            assert new is not None
            if (title, content, tags) != (None, None, None):
                self.db.execute("DELETE FROM embeddings WHERE note_id = ?", (note_id,))
                self.db.commit()
                self._embed(note_id, new["title"], new["content"], new["tags"], embedder)
            return True

    def delete(self, note_id: int) -> bool:
        with self._lock:
            self.db.execute("DELETE FROM embeddings WHERE note_id = ?", (note_id,))
            cur = self.db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            self.db.commit()
            return cur.rowcount > 0

    # -- reads ----------------------------------------------------------

    def get(self, note_id: int) -> dict | None:
        with self._lock:
            row = self.db.execute(
                "SELECT id, title, content, tags, created_at, updated_at FROM notes WHERE id = ?",
                (note_id,),
            ).fetchone()
        if row is None:
            return None
        return dict(zip(("id", "title", "content", "tags", "created_at", "updated_at"), row))

    def list(self, tag: str | None = None, limit: int = 50) -> list[dict]:
        with self._lock:
            if tag:
                rows = self.db.execute(
                    "SELECT id, title, tags, updated_at FROM notes WHERE tags LIKE ? "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (f"%{tag}%", limit),
                ).fetchall()
            else:
                rows = self.db.execute(
                    "SELECT id, title, tags, updated_at FROM notes ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(zip(("id", "title", "tags", "updated_at"), r)) for r in rows]

    def stats(self) -> dict:
        with self._lock:
            notes = self.db.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
            embedded = self.db.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        return {"notes": notes, "embedded": embedded, "data_dir": str(self.cfg.data_dir)}

    def reindex(self, embedder: "Embedder | None") -> dict:
        """Recompute embeddings for every note (e.g. after changing the model)."""
        with self._lock:
            self.db.execute("DELETE FROM embeddings")
            self.db.commit()
            done = 0
            for row in self.db.execute("SELECT id, title, content, tags FROM notes").fetchall():
                if self._embed(row[0], row[1], row[2], row[3], embedder):
                    done += 1
            return {"reindexed": done, "embeddings_active": embedder is not None and embedder.enabled}

    # -- search ---------------------------------------------------------

    def _fts_query(self, query: str) -> tuple[str, str] | None:
        terms = re.findall(r"\w+", query, flags=re.UNICODE)
        if not terms:
            return None
        quoted = [f'"{t}"' for t in dict.fromkeys(terms)]
        return " ".join(quoted), " OR ".join(quoted)

    def _fts_search(self, query: str, k: int) -> list[tuple[int, str]]:
        pair = self._fts_query(query)
        if pair is None:
            return []
        for match in pair:
            rows = self.db.execute(
                "SELECT rowid, snippet(notes_fts, 1, '[', ']', ' ... ', 24) "
                "FROM notes_fts WHERE notes_fts MATCH ? ORDER BY bm25(notes_fts) LIMIT ?",
                (match, k),
            ).fetchall()
            if rows:
                return rows
        return []

    def _vector_search(self, query: str, k: int, embedder: "Embedder | None") -> list[int]:
        if embedder is None:
            return []
        emb = embedder.embed([query])
        if not emb:
            return []
        qvec = tuple(float(x) for x in emb[0])
        scored = []
        for note_id, model, dim, blob in self.db.execute(
            "SELECT note_id, model, dim, vec FROM embeddings"
        ):
            if model != embedder.model or dim != len(qvec):
                continue
            scored.append((_cosine(qvec, struct.unpack(f"{dim}f", blob)), note_id))
        scored.sort(reverse=True)
        return [note_id for score, note_id in scored[:k] if score > 0.05]

    def search(self, query: str, limit: int = 5, embedder: "Embedder | None" = None) -> dict:
        with self._lock:
            k = max(limit * 3, 10)
            fts = self._fts_search(query, k)
            snippets = {rowid: snip for rowid, snip in fts}
            fts_ids = [rowid for rowid, _ in fts]
            vec_ids = self._vector_search(query, k, embedder)

        # Reciprocal rank fusion.
        fused: dict[int, float] = {}
        for rank, note_id in enumerate(fts_ids):
            fused[note_id] = fused.get(note_id, 0.0) + 1.0 / (60 + rank + 1)
        for rank, note_id in enumerate(vec_ids):
            fused[note_id] = fused.get(note_id, 0.0) + 1.0 / (60 + rank + 1)

        results = []
        for note_id, score in sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:limit]:
            note = self.get(note_id)
            if note is None:
                continue
            matched = []
            if note_id in fts_ids:
                matched.append("fts")
            if note_id in vec_ids:
                matched.append("vector")
            snippet = snippets.get(note_id) or note["content"][:200]
            results.append(
                {
                    "id": note["id"],
                    "title": note["title"],
                    "tags": note["tags"],
                    "snippet": snippet,
                    "score": round(score, 5),
                    "matched_by": "+".join(matched),
                }
            )
        return {
            "query": query,
            "mode": "hybrid" if vec_ids else "full-text",
            "results": results,
        }

    # -- embeddings ------------------------------------------------------

    def _embed(self, note_id: int, title: str, content: str, tags: str, embedder: "Embedder | None") -> bool:
        if embedder is None:
            return False
        emb = embedder.embed([f"{title}\n{tags}\n{content}"])
        if not emb:
            return False
        vec = tuple(float(x) for x in emb[0])
        self.db.execute(
            "INSERT OR REPLACE INTO embeddings (note_id, model, dim, vec) VALUES (?, ?, ?, ?)",
            (note_id, embedder.model, len(vec), struct.pack(f"{len(vec)}f", *vec)),
        )
        self.db.commit()
        return True
