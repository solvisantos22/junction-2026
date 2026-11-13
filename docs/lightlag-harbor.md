# Lightlag as a Harbor task

14 November 2026, 02:00 Helsinki. Owner: Kristján / Claude Code. Task: [`harbor/lightlag/`](../harbor/lightlag/), tests: `tests/harbor/`. This is the submission format AfterQuery requires ([their update](afterquery-update-2026-11-14.md)).

**Status:** the task passes Harbor's linter (0.25.0, default rules), and its four runtime steps pass end to end when run as plain processes. **It has not been built or run in containers**, because Docker was not running on this machine, and **no model has played it**. Treat every claim about a real `harbor run` as unverified until one is done.

## Run it

Needs Docker running and Harbor installed (`uv tool install harbor`, Python 3.12+).

```sh
harbor run -p harbor/lightlag -a oracle                      # our reference run
harbor run -p harbor/lightlag -a nop                         # do nothing
harbor run -p harbor/lightlag -a opencode -m <provider/model> # a model; needs that provider's API key in the environment
```

Each run ends with one number between 0 and 1 in `/logs/verifier/reward.txt`.

## What scripted policies score

These went through the task's own copies of the code (simulator command, solution script, collect hook, verifier) as plain processes, seed 7, delay 3, default rules:

| Policy | Reward | Ends |
|---|---|---|
| Reference (`solution/solve.sh`) | 1.000 | all three targets, at base |
| Waits for each command to land | 0.750 | two targets, at base |
| Plans once, never reads telemetry | 0.750 | two targets, at base |
| Forgets commands in transit | 0.000 | battery dead |
| Stops after 5 ticks | 0.000 | alive, away from base, nothing sampled |
| Does nothing | 0.000 | at base, nothing sampled |

One seed, so read it as a wiring check, not a result. The [pilot](lightlag-pilot.md) has the multi-seed numbers.

## How the reward stays out of the agent's reach

```
agent's container (main)            simulator's container (lightlag)         verifier's container
------------------------            --------------------------------         --------------------
plays through 5 MCP tools  ----->   holds the episode, seed, hidden slip
is stopped by Harbor
                                    collect hook: finish + grade,
                                    writes /evaluator/result.json
                                    Harbor copies /evaluator  ------------>  test.sh reads result.json,
                                                                             writes reward.txt
```

1. **The agent's container holds no simulator code and no episode settings.** The seed lives in the simulator container's environment. The agent's image copies nothing from the task.
2. **Harbor stops the agent's container, then runs the collect hook inside the simulator's container.** The hook finishes the episode: remaining ticks pass, the battery keeps draining, and the result is written there. So doing nothing and stopping early are graded at the full episode length.
3. **Finishing needs a token that never leaves the simulator's container.** The server generates it at start-up and writes it to a file only that container can read. No secret is stored in the repository or passed through the agent's container.
4. **Harbor copies `/evaluator` from the simulator's container into a fresh verifier container.** The verifier is a separate image the agent never touched. It reads the simulator's result and writes `raw_score / max_available_value`.
5. **A missing or malformed result fails the verifier** instead of scoring zero, so a broken pipeline cannot pass for a weak agent.

This uses three documented Harbor features: sidecar services in `environment/docker-compose.yaml`, `[[verifier.collect]]` hooks, and artifacts collected from a named service. I read them in Harbor's source as installed; I have not seen them run.

## Layout

```
harbor/
├── sync_task.py                 copies the simulator, MCP server and reference into the task
└── lightlag/
    ├── instruction.md           what the agent is told
    ├── task.toml                MCP server, collect hook, artifact, separate verifier
    ├── environment/
    │   ├── Dockerfile           the agent's container: Python and an MCP client library
    │   ├── docker-compose.yaml  adds the simulator container; episode seed and delay
    │   └── simulator/           the simulator's container (copies of lightlag/ and lightlag_mcp/)
    ├── tests/                   the verifier's container: test.sh and grade.py
    └── solution/                the reference run (copies of lightlag_controllers/ and the MCP client)
```

**The copies are generated.** A Docker build cannot reach files outside the task directory, so the task carries copies. Edit the originals, then run `python3 harbor/sync_task.py`. A test fails when a copy is stale.

## Decisions the team should confirm

- **Reward scale:** `raw_score / max_available_value`, as Sölvi's note suggested. The reference scores 1.0 on this seed, so there is no headroom above it here.
- **One episode per task:** seed 7, delay 3, default map and rules, set in `docker-compose.yaml`. Several maps per run would need several tasks or a multi-episode server.
- **Rules:** unchanged from the simulator's defaults. The pilot's finding that a blind plan does well under these rules still stands (0.750 here).

## Known risks before the first real run

- **OpenCode may not see the tools.** Harbor writes OpenCode's MCP settings directly under `mcp`, while OpenCode's current docs put them under `mcp.servers`. If the tools do not appear, pass a corrected block through Harbor's `--ak opencode_config=...` option or pin an OpenCode version.
- **Nothing has been built.** Image builds, the health check, service-name networking and the collect hook's timing are all untested.
- **Lint findings under all rules:** base images are not pinned to digests, and the agent runs as root. Neither affects the grading path above; both are worth fixing once a run works.
- **Model access:** AfterQuery provides no credits. A run needs a provider key in the environment of whoever runs it.

## Tests

```sh
python3 -m unittest discover -s tests/harbor -v                              # 6 run, 5 skipped without mcp / Python 3.11
uv run --with 'mcp==2.3.0' python -m unittest discover -s tests/harbor -v    # all 11
```

They check the required files, that copies match the originals, that the agent image contains no simulator code, the task configuration, the reward arithmetic and its rejection of malformed results, and the four-step chain for the reference, do-nothing, stop-early and stale-telemetry policies.
