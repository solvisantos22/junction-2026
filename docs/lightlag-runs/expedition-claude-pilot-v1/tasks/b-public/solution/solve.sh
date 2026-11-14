#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
python3 play_policy.py --policy reference --url "${EXPEDITION_MCP_URL:-http://expedition:8000/mcp}"
