# Three labs, three tiers on Lightlag Traverse

15 November 2026. Owner: Manh / Claude Code (tier comparison chat). Tools: [`tools/tier_agents/`](../tools/tier_agents/). Tables: [`tier-comparison/tables.md`](tier-comparison/tables.md), generated from the saved runs by `python3 tools/tier_agents/report.py`. Ledger of every agent run with tokens and cost: [`tier-comparison/runs.jsonl`](tier-comparison/runs.jsonl).

Kristján measured Anthropic's models on his Traverse tasks ([`lightlag-traverse-campaign.md`](lightlag-traverse-campaign.md)). This page repeats his measurements, unchanged, with the matching models of OpenAI and Google DeepMind, so the reference can be judged against today's models across labs rather than one lab. Claude was not rerun: Claude's numbers are Kristján's runs.

**Status: complete.** All 36 GPT and Gemini agent runs, the six one-request runs and the farm replays are saved. Final API cost: about $30.40 Google, $3.60 OpenAI (OpenCode's own count).

## The lineup

Chosen by each lab's own naming of its tiers, not by price.

| Tier | Anthropic (Kristján's runs) | OpenAI | Google DeepMind |
|---|---|---|---|
| Top | Opus 5.5 | GPT-6.1 Sol | Gemini 4 Carbon |
| Middle | Sonnet 5.5 | GPT-6.1 Terra | Gemini 4 Argon |
| Bottom | Haiku 5.5 | GPT-6 Luna | Gemini 4 Hydrogen |

## What was run: a copy of Kristján's method

Three measurements, each exactly as Kristján made it for Claude.

1. **Agent runs.** Harbor 0.25.0, agent OpenCode 1.19.5, on the campaign task (`harbor/lightlag-traverse-campaign`, worlds 2027–2029, 45-minute session) and the one-site task (`harbor/lightlag-traverse`, world 2026). Three runs per model per task (Kristján: 4 Opus, 2–3 Sonnet, 1 Haiku). Nothing in the tasks was changed.
2. **One request, one program.** The exact request text Kristján sent (`python3 -m lightlag_traverse.oneshot request`; sha256 `5763295bb02991cb…`, identical to his), sent once, no retries, no fallback. Each tier is asked the way Kristján asked his model of that tier: top as Opus (effort medium, up to 100,000 output tokens), middle as Sonnet (medium, 64,000), bottom as Haiku (low, 64,000). The reply's program is played once in the sandbox on world 2026 by Kristján's `play`.
3. **Replays on many worlds.** The programs from (2), and the agents' own programs rebuilt from the world-2026 runs, are replayed on the farm on worlds 600–899 and on the campaign's worlds, beside the reference, with the Traverse code of commit `3bff7b2` that Kristján used (row hash `c5f64ae99570`, the same as his).

## Results

Full tables: [`tier-comparison/tables.md`](tier-comparison/tables.md). The reference scores 0.476 on the campaign, 0.565 on world 2026 and 0.502 over worlds 600–899.

- **No model beats the reference on average, on any measure.** The closest single runs: Gemini 4 Carbon's campaign runs 0.449 and 0.473 (reference 0.476), and its one world-2026 run that drove, 0.567 (reference 0.565).
- **GPT-6.1 Sol is the steadiest.** Every agent run 0.35 to 0.55 (campaign mean 0.361, world 2026 0.523); its one-request program scores 0.433 over 300 unseen worlds, the best of any one-request program, Claude's included (Opus 0.321).
- **Gemini is all or nothing.** Carbon, Argon and Hydrogen each have runs that score 0, mostly agents that ran out of session time before starting a mission (all three Argon runs on world 2026). When a Gemini agent did drive, its program held up best on unseen worlds: Hydrogen agent 2 scores 0.454 over 300 worlds, Carbon agent 2 0.410, against GPT-6.1 Sol's agents 0.421, 0.380, 0.446 and Opus's best 0.309.
- **Tier names do not order the results.** Gemini's bottom tier, Hydrogen, scores above Anthropic's Opus and Sonnet on the campaign (0.369 against 0.220 and 0.253). GPT-6.1's middle tier, Terra, scores above Opus on world 2026 (0.403 against 0.268).
- **Every agent program that scored well on world 2026 lost ground on worlds it had not seen**, as Kristján found for Claude: the best fell from 0.56–0.57 live to 0.41–0.45 over 300 worlds, against the reference's 0.502.

## Reproducing it

Keys go in `.env` at the repository root (`OPENAI_API_KEY`, `GOOGLE_API_KEY`); they are passed to the agent's container through a temporary file and never saved. Docker and Harbor 0.25.0 locally; Modal for the `--env modal` runs and the farm.

```bash
# 1. Agent runs: every planned run not yet saved, cheapest tier first, labs interleaved.
python3 tools/tier_agents/run_tiers.py --dry-run
python3 tools/tier_agents/run_tiers.py --parallel 8                 # local Docker, as Kristján ran
python3 tools/tier_agents/run_tiers.py --parallel 8 --env modal     # the same on Modal
# one run by hand:
tools/tier_agents/run.sh harbor/lightlag-traverse openai/gpt-6.1-sol traverse-agent-gpt-6.1-sol-1

# 2. One request, one program (per model):
python3 -m lightlag_traverse.oneshot request /tmp/request.md
python3 tools/tier_agents/oneshot_ask.py /tmp/request.md /tmp/sol --model gpt-6.1-sol
python3 -m lightlag_traverse.oneshot play /tmp/sol traverse-oneshot-gpt-6.1-sol-1 --label "GPT-6.1 Sol · one shot"

# 3. The agents' programs, rebuilt from their trajectories, then replayed:
python3 tools/tier_agents/rebuild_program.py docs/lightlag-runs/traverse-agent-gpt-6.1-sol-1
python3 -m lightlag_traverse.sandbox --program docs/lightlag-runs/traverse-agent-gpt-6.1-sol-1/program \
    --entry farm_prepare.py /tmp/check-sol-1                         # world 2026, local Docker
git archive 3bff7b2 | tar -x -C /tmp/traverse-3bff7b2               # Kristján's Traverse code
TRAVERSE_SOURCE=/tmp/traverse-3bff7b2 TRAVERSE_FARM_PIP="numpy==2.5.4 scipy==1.18.1 matplotlib==3.11.2" \
    modal run tools/traverse_farm/modal_app.py::evaluate --policies "$(cat jobs/farm_agents_policies.txt)" \
    --seeds 600-899 --out docs/traverse-farm/programs-agents-tiers

# 4. The tables:
python3 tools/tier_agents/report.py > docs/tier-comparison/tables.md
```

Every saved run has its full trajectory (`agent/trajectory.json`), Harbor's logs and the grader's output under `docs/lightlag-runs/<run>/`; a one-request run has the request, the reply and the program.

## Where this differs from Kristján's runs, and why

- **Gemini's key.** Harbor passes `GOOGLE_API_KEY`; OpenCode 1.19.5 reads `GOOGLE_GENERATIVE_AI_API_KEY`. `run.sh` writes the key under that name and sets OpenCode's Google provider to read it. No other agent setting differs.
- **Some runs on Modal.** To finish in time, part of the agent runs used Harbor's Modal environment (`--env modal`) instead of local Docker. Same task images, same agent. The reference through Harbor on Modal scores 0.476257 on the campaign, the same as local Docker.
- **The one-site task is version 0.1.2**, Kristján's Claude runs 0.1.0. Only the reference changed between them; the agent's instruction, tools and grader did not.
- **The sandbox.** `lightlag_traverse/sandbox.py` now makes its shared folder readable (`chmod 755`): on Linux the container's user could not read it, so every program "died" (Docker Desktop on macOS ignores this, which is where Kristján ran it). With the fix, his Haiku program reproduces his 0.0905.
- **`play` labels.** `lightlag_traverse.oneshot play` writes `gpt` or `gemini` as the kind for those models, and the API used; a Claude run's `run.json` is byte-identical to before.
- **Saving runs.** GPT's encrypted reasoning blobs can look like an `sk-…` key. `harbor/save_run.py --check-env .env` copies a run only when no actual key from `.env` appears in it.
- **Gemini 4 Carbon's one request.** Google caps a reply at 32,768 tokens; Carbon spent it thinking and its reply has no program. Recorded as it is, 0, under the no-retry rule.
- **Rebuilding agents' programs.** Kristján rebuilt his by hand; `rebuild_program.py` does the same from the trajectory (writes, edits, OpenAI patches and `cat << EOF` blocks, nothing executed), and reproduces his Opus agent 1 program byte for byte. An edit OpenCode applied by loose matching is applied the same way and listed in `run.json`. Where an agent prepared files by hand before starting its autopilot, a `farm_prepare.py` repeats those steps, as Kristján did for Opus agent 3. On world 2026, 10 of the 11 rebuilt programs replay to their live score exactly; GPT-6.1 Sol agent 3 replays to 0.545 against 0.526 live.
- **Installed packages.** GPT-6.1 Sol agent 2 installed numpy, scipy and matplotlib in its container; its replay uses those versions (`--image` in the sandbox, `TRAVERSE_FARM_PIP` on the farm). The farm now keeps installed packages loaded between missions (numpy cannot be loaded twice in one process); a program's own modules are still unloaded.

## Cost

OpenCode's own count, in [`runs.jsonl`](tier-comparison/runs.jsonl) as `cost_usd_reported_by_opencode`. It is higher than a count from the token totals Harbor records (`cost_usd_from_prices`), by about 2× for GPT and 1.25× for Gemini, most likely because those totals leave out reasoning tokens. Where OpenCode recorded no cost (some Gemini runs), the price-based count is the floor.
