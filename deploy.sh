#!/usr/bin/env bash
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
# Deploy the knowledge base from this source tree into the deployment dir.
# Usage: ./deploy.sh   (override target with KB_DEPLOY_DIR=...)
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${KB_DEPLOY_DIR:-$HOME/.config/OpencodeKnowledgeBase}"

mkdir -p "$DEST"
uv venv "$DEST/venv" --clear --quiet
uv pip install --python "$DEST/venv/bin/python" "$SRC" --quiet
"$DEST/venv/bin/ockb" status
echo "Deployed to $DEST (venv: $DEST/venv)"
