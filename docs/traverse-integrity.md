# Lightlag Traverse: the integrity review

Sunday 15 November 2026, about 05:00 Helsinki. Owner: Kristján / Claude Code (gap research chat), taken over at Kristján's word from the Codex row that claimed it on Saturday at 19:04 and published nothing. Tool: [`tools/traverse_integrity/`](../tools/traverse_integrity/), tests: [`tests/traverse_integrity/`](../tests/traverse_integrity/), records: [`traverse-integrity-results/`](traverse-integrity-results/). **A review, not a rules change:** no file of the task, the simulator or the reference was edited.

AfterQuery's judges rerun the task and then spend fifteen minutes looking for a way to score without doing it. Reward integrity is 25 of the 100 points, and it is zero if any trick beats honest play. This page is the same hunt, done by us first, on the task we submit: [`harbor/lightlag-traverse-campaign/`](../harbor/lightlag-traverse-campaign/) 0.1.0.

## Bottom line

- **Nothing an agent did from inside its container changed the reward or disclosed a hidden value.** 27 attempts, through Harbor, on a copy of the task with its own seeds: the container, the network, the five tools, the clock, and forged reward files. Harbor reported 0.0, which is the simulator's own result for a run that sampled nothing.
- **Spoiling the grade does not raise it either.** With folders put where the reward files belong, Harbor still reported the simulator's 0.0.
- **The baselines repeat.** On the judged task, today, from `main`: the reference 0.476257 in 1 minute 50 seconds, doing nothing 0.000 in 19 seconds.
- **One limit is known and stays:** the worlds are fixed by their seeds, and both the seeds and the simulator's code are in this repository. Whoever holds the repository can predict a mission exactly. An agent's container does not hold it. The section below measures this and says what the judges can do about it.

## How it was done

- **A disposable copy.** `python3 -m tools.traverse_integrity.run` copies the campaign task, changes one line (`LIGHTLAG_SEEDS` to 1201, 1202, 1203, from the range reserved for this review) and runs Harbor 0.25.0 on the copy. The judged worlds 2027 to 2029 were never played by a probe.
- **An agent that attacks.** [`agent.py`](../tools/traverse_integrity/agent.py) is a Harbor agent that uploads one file, [`probe.py`](../tools/traverse_integrity/probe.py), and runs it as root in the agent's container. It brings no solution folder, so the container is the one a model sees.
- **The verdict comes from outside.** The probe plays no mission (one drive, no sample), so the simulator's score for the run is 0. The report compares the reward Harbor wrote with the simulator's own result file and its transcript of every call.
- **Where:** Docker Desktop on macOS, Harbor 0.25.0, no model or API call, no cloud spend.

## What was tried, and what happened

| Attack | Result |
|---|---|
| Find the seeds, the evaluator's token, the tests, the solution or a Docker socket in the container: environment variables, seven paths, every file on the file system | None present. The image holds the client, the launcher and the published ground model |
| Reach the simulator's container by another door: 1,147 ports | Only 8000 is open |
| Fetch results, replays, the token, the state or a reset over HTTP: 22 guessed routes, with path tricks | None answered. Only `/healthz` and `/mcp` exist |
| Close and grade the mission early through `/evaluator/finish`: no token, an empty one, guessed ones, basic auth, a token in the address | 404 seven times; the mission stayed open |
| Call evaluator-side or made-up tools: `evaluate`, `replay`, `finish`, `reset`, `seed`, `score` and seven more | Every one refused; the server offers exactly five tools |
| Ask the free tools for more: `rules(seed=1)`, `map(truth=true)`, `telemetry_log(delay_ticks=0)` and three more | No hidden key in any reply |
| Look for the seed, exact hidden values or anything graded in the replies of `rules`, `map` and `telemetry_log` | None; ranges only. The seeds do not appear as numbers in the rules. An in-process test scans an `advance` reply the same way |
| 26 malformed uplinks: no commands, six, unknown actions, extra fields, metres of 0, −5, 5.000001 and a billion, numbers as text, `true`, `null`, not-a-number, infinity, a megabyte of junk, one good command beside one bad | Every one refused, and nothing was queued: the next good command took the first free slot |
| 10 malformed advances: 0, 6, −1, 1000, 1.5, `true`, `null`, a list, text, an extra `to_tick` | Eight refused. `true` was read as one tick and the extra argument was dropped: an ordinary advance of one tick |
| An uplink that names its own execute tick | The argument was dropped; the command took the next free slot |
| Beat the delay: a drive sent at tick 4 | Executed at tick 8, the wheels turned at tick 8 and no earlier; no telemetry packet arrived less than three ticks old |
| Race the clock: 12 new sessions advancing at once, then 12 sending a command at once | Every tick and every slot was used exactly once |
| Reset by reconnecting | A new session continued the same mission at the next tick |
| Forge the grade from the agent's container: `/logs/verifier/reward.txt` and `reward.json` of 1.0, a perfect `/evaluator/result.json`, a `/tests/test.sh` that always passes, forged artifacts | All eight files were written. Harbor reported 0.0, the simulator's own result |
| Block the grade: folders where the reward files belong | Harbor reported 0.0, no error |
| A refused call that still moves the clock | 28 of 81 calls were refused; none changed the tick, by the simulator's own transcript |

Every row is in [`report-probe.json`](traverse-integrity-results/report-probe.json), with what was seen; the probe's own log is [`probe.txt`](traverse-integrity-results/probe.txt), the second run [`report-block.json`](traverse-integrity-results/report-block.json).

**Why the forgeries fail, from the code.** The simulator writes its result inside its own container when Harbor's collect hook finishes the mission, after the agent's container has stopped ([`task.toml`](../harbor/lightlag-traverse-campaign/task.toml)). Harbor copies that folder into a fresh verifier container, where [`grade.py`](../harbor/lightlag-traverse-campaign/tests/grade.py) reads that file and nothing else, and refuses a result that is missing, not finite or out of range. Harbor's own verifier also deletes any reward file already present before it runs the tests. The finish route compares a 32-byte token that is generated inside the simulator's container and written to a file only root there can read.

Eleven in-process tests cover what a client library cannot send (not-a-number, infinity, numbers too large for a float) and what must stay true of the task's files: the agent's image copies three helper files and nothing of the simulator, no file given to the agent names a seed, the verifier runs apart.

## Scoring loopholes

These are about the reward's shape, not the container.

- **Doing nothing scores 0.000** (Harbor `-a nop`, rerun today).
- **Stopping early earns what was done and no more:** the reference stopped after the first site scores 0.149, under a third of its 0.476 ([saved run](campaign-baselines.md)).
- **Not coming home cannot win.** A rover that ends away from the lander keeps half its samples' value, so it would need more than twice the reference's samples at a site. In the recorded runs, the three GPT-6.1 Sol rovers that ended the first site away, with 15 to 20 samples, scored 0.18 to 0.23 there; the reference came home with 23 and scored 0.459.
- **Dying is never the best move:** a flat battery scores 0 for that site.
- **A sample cannot be taken twice or from afar:** the simulator checks the true position against the 2.5 m radius and keeps a set of sampled targets.

## The known limit: the seed

Everything hidden in a mission (each terrain's slip, the panel efficiency, the heading bias, every noise draw) comes from generators seeded by the mission's seed. That is what makes scores repeat exactly on a laptop, on Modal and through Harbor. It also means that a copy of the simulator started with the same seed is the same mission.

Measured on one of the review's own worlds, with this repository's code ([`twin.py`](../tools/traverse_integrity/twin.py), [record](traverse-integrity-results/twin.json)): generating candidate worlds until one matches the public map found the seed among 2,000 candidates in 46 seconds on eight processes; a copy started with it had the same hidden values and the same true states tick for tick.

What this needs is the repository. The agent's container holds no simulator code and no seed (rows one and seven above). A search of the trajectories of all 25 recorded campaign runs for `git clone`, GitHub addresses, this repository's owner and the seed setting finds nothing. That includes the Gemini 4 Carbon run that came within 0.003 of the reference and sampled the same 26 targets at the second site: its trajectory shows a path-finder, an estimator, a planner and a simulator of its own, written and tested in the container. The container does have internet access, which OpenCode needs to reach its model, so an agent that knew where this repository is could fetch it. The same holds for any task whose code and fixed worlds are public.

**What the judges can do:** change the seeds. They are one line, `LIGHTLAG_SEEDS` in [`environment/docker-compose.yaml`](../harbor/lightlag-traverse-campaign/environment/docker-compose.yaml), and any integers work. The reference does not depend on them: on 300 worlds it had never seen it averages 0.502 and loses no rover ([farm](traverse-farm.md)). The copy used for this review ran on 1201 to 1203.

Two changes would close it and were not made, because the task is frozen: drawing the hidden values from a secret generated in the simulator's container (at the price of exact repeatability), or limiting the agent's container to its model's address.

## What was not covered

- **A Linux host.** Harbor is built to mount the trial's log folders into the agent's container, so there the agent's `/logs/verifier` is the folder the verifier later writes to. In these runs, on Docker Desktop for macOS, it copied the folders instead, so that path was not exercised. Harbor's source (0.25.0, `trial.py` and `verifier.py`) handles it in three steps: it stops the agent's container before it collects the simulator's result, it empties the verifier folder when the fresh verifier container starts, and it removes any reward file once more before running the tests. Read, not run. One probe run on a Linux machine would settle it; it takes about a minute.
- **Exhausting the simulator** (flooding it with calls or huge requests until it dies). The outcome would be no grade, since the verifier fails loudly when the result file is missing; it was not tried beyond one megabyte.
- **Escapes from the container, and Harbor itself.**
- **The one-site task and the MAX tasks.** They use the same service and server code; the probes were run on the campaign only.
- **A model trying to cheat on its own.** The probe is a script written with the task's source in view. No model was asked to attack.

## Reproduce

Needs Docker and uv. About 20 seconds a run once the images are built.

```sh
python3 -m unittest discover -s tests/traverse_integrity -v                 # 11 tests, no Docker
python3 -m tools.traverse_integrity.run --out /tmp/integrity --mode probe   # the 27 attempts, through Harbor
python3 -m tools.traverse_integrity.run --out /tmp/integrity --mode block   # the blocked reward files
python3 -m tools.traverse_integrity.twin --seed 1203 --limit 2000           # the known limit, measured
```
