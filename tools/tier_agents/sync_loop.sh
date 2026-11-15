#!/usr/bin/env bash
# Every few minutes while tier runs are going: record finished runs whose driver is gone, then pull main
# and commit + push only the tier results (run folders and the ledger). Never stages anything else.
# Stops after a final pass once no driver and no harbor run is left.
set -u
cd "$(dirname "$0")/../.."
INTERVAL=${INTERVAL:-300}
paths=(docs/tier-comparison ':(glob)docs/lightlag-runs/*-gpt-*/**' ':(glob)docs/lightlag-runs/*-gemini-*/**')
pass() {
  python3 tools/tier_agents/run_tiers.py --collect
  python3 tools/tier_agents/run_tiers.py --resave >/dev/null
  git add -- "${paths[@]}" 2>/dev/null
  if ! git diff --cached --quiet -- "${paths[@]}"; then
    names=$(git diff --cached --name-only -- docs/lightlag-runs | cut -d/ -f3 | sort -u | tr '\n' ' ')
    git commit -q -m "runs: tier comparison results ${names:-(ledger)}" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- "${paths[@]}" \
      && echo "$(TZ=Europe/Helsinki date +%H:%M) committed: ${names:-ledger}"
  fi
  for try in 1 2 3; do
    git pull -q --no-rebase --no-edit && git push -q && { echo "$(TZ=Europe/Helsinki date +%H:%M) pushed $(git rev-parse --short HEAD)"; break; }
    sleep 20
  done
}
while true; do
  pass
  if ! pgrep -f "run_tiers.py --env" >/dev/null && ! pgrep -f "harbor run" >/dev/null; then
    pass; echo "all runs finished; sync loop done"; break
  fi
  sleep "$INTERVAL"
done
