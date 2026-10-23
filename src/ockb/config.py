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
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "OpencodeKnowledgeBase"


@dataclass
class Config:
    data_dir: Path
    ollama_url: str
    embed_model: str
    embed_enabled: bool

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            data_dir=Path(
                os.environ.get("KB_DATA_DIR", str(DEFAULT_DATA_DIR))
            ).expanduser(),
            ollama_url=os.environ.get("KB_OLLAMA_URL", "http://localhost:11434").rstrip("/"),
            embed_model=os.environ.get("KB_EMBED_MODEL", "bge-m3"),
            embed_enabled=os.environ.get("KB_EMBED", "1").lower() not in ("0", "false", "no"),
        )
