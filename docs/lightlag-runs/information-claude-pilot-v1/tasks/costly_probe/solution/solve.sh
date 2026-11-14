#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
python3 play_policy.py --policy selective --url "${INFORMATION_MCP_URL:-http://information:8000/mcp}"
