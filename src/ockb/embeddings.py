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
"""Ollama embedding client with graceful degradation.

If Ollama is unreachable or the model is missing, embedding is disabled for
the rest of the process run and the knowledge base keeps working with
full-text search only.
"""

import sys

import httpx


class Embedder:
    def __init__(self, base_url: str, model: str, enabled: bool = True, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.enabled = enabled
        self.timeout = timeout
        self.last_error: str | None = None

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        """Return one embedding vector per text, or None if unavailable."""
        if not self.enabled or not texts:
            return None
        try:
            resp = httpx.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json().get("embeddings") or []
            if len(data) != len(texts):
                raise ValueError("Ollama returned an unexpected number of embeddings")
            return data
        except Exception as exc:  # noqa: BLE001 - degrade, never crash the server
            self.last_error = str(exc)
            self.enabled = False
            print(f"[kb] embeddings disabled for this run: {exc}", file=sys.stderr)
            return None

    def available_models(self) -> list[str]:
        """Model names known to the Ollama server ([] when unreachable)."""
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            resp.raise_for_status()
            return [m.get("name", "") for m in resp.json().get("models", [])]
        except Exception:  # noqa: BLE001
            return []

    def ready(self) -> bool:
        return self.enabled and any(
            name == self.model or name.split(":", 1)[0] == self.model
            for name in self.available_models()
        )
