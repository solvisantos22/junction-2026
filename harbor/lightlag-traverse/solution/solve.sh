#!/bin/bash
# The reference run. It plays through the same MCP service an agent uses, with the
# same five tools and nothing else: no simulator code, no seed, no hidden values.
set -euo pipefail

cd "$(dirname "$0")"
python3 play_reference.py --url "${LIGHTLAG_MCP_URL:-http://lightlag:8000/mcp}"
