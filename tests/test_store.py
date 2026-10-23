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
import pytest

from ockb.config import Config
from ockb.store import Store


@pytest.fixture
def store(tmp_path):
    cfg = Config(
        data_dir=tmp_path,
        ollama_url="http://localhost:1",
        embed_model="none",
        embed_enabled=False,
    )
    return Store(cfg)


def test_add_get_update_delete(store):
    note_id = store.add("OpenCode MCP config", "mcp.servers lives in opencode.json", tags="opencode,mcp")
    note = store.get(note_id)
    assert note["title"] == "OpenCode MCP config"
    assert "opencode.json" in note["content"]

    assert store.update(note_id, content="mcp.servers is the V2 shape")
    assert "V2 shape" in store.get(note_id)["content"]

    assert store.delete(note_id)
    assert store.get(note_id) is None
    assert not store.delete(note_id)


def test_full_text_search(store):
    a = store.add("Sync client conflicts", "SQLite files conflict with sync clients", tags="sqlite")
    b = store.add("Favorite pasta", "Cacio e pepe: pecorino and pepper", tags="food")

    res = store.search("sqlite sync conflict")
    assert res["mode"] == "full-text"
    assert [r["id"] for r in res["results"]] == [a]

    res = store.search("pasta")
    assert res["results"][0]["id"] == b


def test_search_and_fallback(store):
    store.add("alpha beta", "gamma delta")
    # AND finds nothing here, OR fallback should.
    res = store.search("alpha zzz")
    assert res["results"] and res["results"][0]["title"] == "alpha beta"
    assert store.search("")["results"] == []


def test_list_and_stats(store):
    store.add("one", "x", tags="a,b")
    store.add("two", "y", tags="b")
    assert len(store.list()) == 2
    assert [n["title"] for n in store.list(tag="a")] == ["one"]
    assert store.stats()["notes"] == 2
