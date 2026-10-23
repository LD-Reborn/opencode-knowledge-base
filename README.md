# OpenCode Knowledge Base (ockb)

Local knowledge base exposed to OpenCode as an MCP server. Notes live in a
SQLite database with an FTS5 full-text index; optionally each note is also
embedded via Ollama, and searches merge both rankings (reciprocal rank
fusion). If Ollama is down, the server degrades to full-text only.

## Tools

Tools are exposed under the MCP server name `knowledgeBase` (OpenCode names them `knowledgeBase_<tool>`).

| Tool | Purpose |
| --- | --- |
| `search` | Hybrid search, ranked results with snippets |
| `add` | Add a note (title, content, comma-separated tags) |
| `get` / `list` | Read a note / browse recent notes |
| `update` / `delete` | Maintain notes |
| `stats` | Health: note count, embedding coverage, Ollama status |
| `reindex` | Recompute all embeddings (after model change) |

## Configuration (environment)

| Variable | Default | Meaning |
| --- | --- | --- |
| `KB_DATA_DIR` | `~/.local/share/OpencodeKnowledgeBase` | Where `kb.sqlite3` lives |
| `KB_OLLAMA_URL` | `http://localhost:11434` | Ollama server |
| `KB_EMBED_MODEL` | `bge-m3` | Embedding model |
| `KB_EMBED` | `1` | Set `0` to disable embeddings entirely |

## Layout

- Source (development): your clone of this repository
- Deployment: `~/.config/OpencodeKnowledgeBase/venv` (created by `deploy.sh`)
- Data: `~/.local/share/OpencodeKnowledgeBase/kb.sqlite3`

## Development

Keep the dev venv out of the source tree (or just drop the export to use a local `.venv`):

```sh
export UV_PROJECT_ENVIRONMENT=/tmp/opencode/venvs/ockb
uv sync
uv run pytest
```

## Deploy

```sh
./deploy.sh
```

Then register in `~/.config/opencode/opencode.json`:

```jsonc
"mcp": {
  "servers": {
    "knowledgeBase": {
      "type": "local",
      "command": ["~/.config/OpencodeKnowledgeBase/venv/bin/ockb", "serve"],
      "environment": {
        "KB_DATA_DIR": "~/.local/share/OpencodeKnowledgeBase",
        "KB_EMBED_MODEL": "bge-m3"
      }
    }
  }
}
```

Verify with `opencode mcp list`.

## CLI

The same binary works standalone:

```sh
ockb add "Title" "content" --tags a,b
ockb search "query"
ockb status
```

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).

