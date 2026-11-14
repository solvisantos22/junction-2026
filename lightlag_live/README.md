# Lightlag Live

Several unchanged Lightlag missions in a row, on a real-time clock, with the published noise dial at 2. A proposal for the team, not a rules decision. Owner: Kristján / Claude Code. Results and the reasoning behind each choice: [docs/lightlag-live.md](../docs/lightlag-live.md).

It adds a way to *serve* the team's missions. It changes no file of `lightlag/`, `lightlag_dynamic/` or `lightlag_mcp/`: every mission is an unchanged `DynamicEnvironment` episode, and the reference is the unchanged `kf_mpc`, started fresh for each mission.

## Run

From the repository root. The tests and the sandbox need Python 3.9+ and nothing else; the MCP server needs `mcp==2.3.0`; Harbor needs Docker.

```sh
python3 -m unittest discover -s tests/lightlag_live -v                        # 25 tests; 3 need the mcp package
uv run --with 'mcp==2.3.0' python -m unittest discover -s tests/lightlag_live -v   # all of them

harbor run -p harbor/lightlag-live -a oracle                                   # the reference, about 5.5 minutes
harbor run -p harbor/lightlag-live -a nop                                      # do nothing: 0.000
harbor run -p harbor/lightlag-live -a oracle --agent-timeout-multiplier 0.05   # stop early: cut off after 90 s
harbor run -p harbor/lightlag-live -a opencode -m anthropic/claude-opus-5-5 --ak version=1.19.5 --env-file .env

python3 -m lightlag_live.make_task --check                                     # are the task's copies fresh?
python3 -m lightlag_live.sandbox --reference /tmp/ref                          # the reference on a simulated clock
python3 viewer/build_ghosts.py                                                 # rebuild viewer/ghosts-demo.html
```

## What is different from one turn-based episode

| | Turn-based episode | Lightlag Live |
|---|---|---|
| Missions | one | six in a row; the score is their mean |
| Clock | moves only on `advance` | one tick per second of real time, from the agent's first `uplink` or `advance` |
| Before the start | nothing is free of consequence | `rules`, `map` and `telemetry_log` are free: read and prepare for as long as you like |
| `advance(n)` | lets n ticks pass | waits until n more ticks have passed, never past the end of the mission |
| Next mission | none | starts the moment the last one ends, on a new map; its map cannot be seen earlier |
| Sensing noise | level 1 | level 2: the same published dial (`noise_level`), doubled |
| Tools, physics, scoring per mission | | unchanged |

Nobody can keep up with one tick per second by calling tools by hand, so the agent has to write a program that drives. The agent's container holds a helper, `/app/lightlag_client.py`, that gives a program the five tools as plain function calls.

## Files

| File | Contents |
|---|---|
| `campaign.py` | `CampaignService`: the missions, the clock, mission hand-over, grading and artifacts. Standard library only, tested with a fake clock |
| `server.py` | The MCP server: exactly the five tools, with wording for the campaign and the clock, and the evaluator-only finish route |
| `__main__.py` | `python -m lightlag_live`: starts the server from `LIGHTLAG_MISSIONS` and friends |
| `finish.py` | The collect hook: closes and grades the campaign from inside the simulator's container |
| `reference.py` | `play_campaign(tools, policy)`: runs a single-mission controller once per mission |
| `make_task.py` | Writes `harbor/lightlag-live/` from the sources; `--check` reports stale copies |
| `sandbox.py`, `sandbox_worker.py` | Run a model-written `play(tools)` through the campaign in a locked-down container |
| `oneshot.py` | One request, one autopilot: build the request text, send it once, keep the reply and its score |

## How it connects

- **Simulator:** `CampaignService` builds one `DynamicEnvironment` per mission and calls only its public methods plus `evaluate()` and `replay()`.
- **Reference:** `lightlag_dynamic.controllers.POLICIES["kf_mpc"]`, unchanged. With a fake clock it scores exactly its turn-based score on every mission (tested); through Harbor on the real clock it scored the same to six decimals.
- **Artifacts:** `/evaluator/result.json` holds the campaign's reward and every mission's result; `/evaluator/missions/NN/` holds that mission's `replay.json` (the team's `lightlag-replay-v1`) and `transcript.jsonl`. Each record carries the mission, the tick and the wall-clock second.
- **Grading:** `tests/grade.py` recomputes the mean from the per-mission numbers and refuses a result that does not add up.
