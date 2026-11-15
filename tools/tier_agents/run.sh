#!/bin/bash
# Run one Gemini agent on a Harbor task, the same way as Kristján's Claude agent
# runs (OpenCode 1.19.5, setup timeout x3), with GOOGLE_API_KEY from .env.
#
#   tools/gemini_agents/run.sh harbor/lightlag-traverse-campaign gemini-4-hydrogen gemini-hydrogen-campaign-1
#
# Harbor forwards a Gemini key to the agent as GOOGLE_API_KEY, but OpenCode
# 1.19.5 reads GOOGLE_GENERATIVE_AI_API_KEY; the opencode_config line points it
# at that name. Retries only when the container's install step fails (the venue
# DNS flakes). Jobs go to jobs/ (untracked; keep one as evidence with
# harbor/save_run.py).
set -u
# Docker group not active in this shell yet: rerun this script under it.
if ! docker info >/dev/null 2>&1 && [ -z "${GEMINI_RUN_SG:-}" ]; then
  exec sg docker -c "GEMINI_RUN_SG=1 bash '$0' '$1' '$2' '$3'"
fi
task=$1; model=$2; job=$3
root=$(cd "$(dirname "$0")/../.." && pwd); cd "$root"
envfile=$(mktemp); trap 'rm -f "$envfile"' EXIT; chmod 600 "$envfile"
key=$(grep -E '^(GOOGLE_API_KEY|GEMINI_API_KEY)=' .env | head -1 | cut -d= -f2-)
[ -n "$key" ] || { echo "no GOOGLE_API_KEY in .env"; exit 1; }
printf 'GOOGLE_GENERATIVE_AI_API_KEY=%s\n' "$key" > "$envfile"
run() {
  harbor run -p "$task" -a opencode -m "gemini/$model" --ak version=1.19.5 \
    --ak 'opencode_config={"provider":{"google":{"options":{"apiKey":"{env:GOOGLE_GENERATIVE_AI_API_KEY}"}}}}' \
    --agent-setup-timeout-multiplier 3 --env-file "$envfile" -o jobs --job-name "$job"
}
for attempt in 1 2 3 4; do
  rm -rf "jobs/$job"
  mkdir -p jobs; run > "jobs/$job.log" 2>&1
  t=$(ls -d "jobs/$job"/*__* 2>/dev/null | head -1)
  if [ -f "$t/exception.txt" ] && [ ! -s "$t/agent/opencode.txt" ] \
     && grep -q -E "Could not resolve host|NVM failed|EAI_AGAIN" "$t/exception.txt"; then
    echo "$job: install failed (attempt $attempt), retrying"; continue
  fi
  echo "$job: reward $(cat "$t/verifier/reward.txt" 2>/dev/null || echo none)"
  grep -o 'Quota exceeded for metric[^\\]*' "$t/agent/opencode.txt" 2>/dev/null | head -1
  exit 0
done
echo "$job: gave up after 4 install failures"
