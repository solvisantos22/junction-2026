#!/bin/bash
# Run one Anthropic, OpenAI or Google agent on a Harbor task, the same way as
# Kristján's Claude agent runs (OpenCode 1.19.5, setup timeout x3), with the
# lab's key from .env:
#
#   tools/tier_agents/run.sh harbor/lightlag-traverse-campaign anthropic/claude-haiku-5-5 campaign-agent-haiku-2
#   tools/tier_agents/run.sh harbor/lightlag-traverse-campaign openai/gpt-6.1-sol campaign-agent-gpt-6.1-sol-1
#   tools/tier_agents/run.sh harbor/lightlag-traverse-campaign gemini/gemini-4-carbon campaign-agent-gemini-4-carbon-1
#
# Keys: ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY. Harbor forwards a Gemini key to the agent as GOOGLE_API_KEY, but OpenCode
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
keyof() { grep -E "^$1=" .env | head -1 | cut -d= -f2-; }
extra=()
case "$model" in
  anthropic/*) key=$(keyof ANTHROPIC_API_KEY); name=ANTHROPIC_API_KEY ;;
  openai/*)    key=$(keyof OPENAI_API_KEY);    name=OPENAI_API_KEY ;;
  gemini/*)    key=$(keyof GOOGLE_API_KEY);    name=GOOGLE_GENERATIVE_AI_API_KEY
    extra=(--ak 'opencode_config={"provider":{"google":{"options":{"apiKey":"{env:GOOGLE_GENERATIVE_AI_API_KEY}"}}}}') ;;
  *) echo "model must start with anthropic/, openai/ or gemini/"; exit 1 ;;
esac
[ -n "$key" ] || { echo "no key for $model in .env"; exit 1; }
printf '%s=%s\n' "$name" "$key" > "$envfile"
run() {
  harbor run -p "$task" -a opencode -m "$model" --ak version=1.19.5 "${extra[@]}" \
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
  grep -o -E 'Quota exceeded for metric[^\\]*|"name":"[A-Za-z]*Error"' "$t/agent/opencode.txt" 2>/dev/null | head -1
  exit 0
done
echo "$job: gave up after 4 install failures"
