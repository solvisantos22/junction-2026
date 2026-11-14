# Traverse rollout farm

Saturday 14 November 2026. Owner: Kristján / Claude Code. Code: [`tools/traverse_farm/`](../tools/traverse_farm/), tests: [`tests/traverse_farm/`](../tests/traverse_farm/). **A tool for the Traverse owner, not a rules decision.** It reads `lightlag_traverse` and never edits it.

## What it is for

Lightlag Traverse ([README](../lightlag_traverse/README.md)) is a 420-tick mission on a 600 m by 400 m Mars-like map. A reference pilot mission takes about 25 CPU-seconds, so comparing controllers on hundreds of worlds is slow on one laptop. The farm plays many missions at once, on Modal or on a local process pool, for two jobs:

1. **Pilot against Claude's programs on fresh worlds, paired.** The pilot and each saved Claude-written Traverse program play the same unseen worlds; the farm reports means, rovers lost or stranded, and how often each is higher. This is what the Traverse owner asked for first.
2. **Searching the pilot's options.** A cross-entropy search over the pilot's numeric options (search budgets, beam widths, margins, the battery floor, slacks, energy weight, slip prior), each candidate compared paired with the published defaults on the same worlds, then selection on a fresh block and confirmation on worlds nobody searched. A gain is claimed only if its 95% paired bootstrap interval excludes zero. The Traverse owner reports that no single option moved the mean by more than about 0.01 on 32 worlds, so expect little here.

## Seeds

Agreed with the Traverse owner: search 100–399, selection 400–499, confirmation and program comparison 600–799 (and up to 899 for program comparison). Untouched: 1–99 (the owner's development), 2026 (the task's world), 99991 (the example in the one-request text), 1000–1199 (the owner's own fresh check).

## Run it

Locally, standard library only:

```sh
python3 -m unittest discover -s tests/traverse_farm -v
python3 tools/traverse_farm/local.py evaluate --policies pilot,greedy,straight,nothing --seeds 600-601 --workers 8
```

On Modal (needs the `modal` package and a login, `modal setup`, done by the account owner):

```sh
modal run tools/traverse_farm/modal_app.py::smoke         # 8 worlds on Modal and here: same scores expected
modal run tools/traverse_farm/modal_app.py::evaluate \
    --policies "pilot,program:docs/lightlag-runs/traverse-oneshot-opus-1/policy.py,agent:docs/lightlag-runs/traverse-agent-opus-1/program/auto.py" \
    --seeds 600-899 --out docs/traverse-farm/programs-1
modal run tools/traverse_farm/modal_app.py::search --out docs/traverse-farm/search-1
```

`--mission '{"sun_margin_ticks": 0}'` plays every mission on changed rules (JSON, as `TraverseEnvironment(seed, mission=...)` takes them); each row records them, and missions on other rules stay apart in the same folder.

`evaluate` compares every policy with `--baseline` (default `pilot`) world by world: the mean difference, its 95% paired bootstrap interval, and on how many worlds the policy scored higher, the same, or lower. With `--out`, rows are saved after every 400 missions and a rerun into the same folder plays only missions it has not seen, so policies can be added to a finished comparison.

Agent programs rebuilt from trajectories: Opus agent 3 prepared its autopilot by hand (saved the map to `/tmp/map.json`, built `/tmp/ll/D.pkl` with `route.py`, then started `auto.py` from `/tmp/ll`), so it is replayed through a labelled wrapper, `agent:docs/lightlag-runs/traverse-agent-opus-3/program/farm_prepare.py`. Sonnet agent 1 runs as `agent:docs/lightlag-runs/traverse-agent-sonnet-1/program/auto.py`. Each run's `run.json` says how its program was rebuilt.

`TRAVERSE_SOURCE=<folder>` plays another version of `lightlag_traverse` (for example a commit extracted with `git archive`). Every result row records a hash of the code that played and the machine it ran on.

**Model-written programs run only on Modal**, inside its isolated containers; the local command refuses them. Each program gets the published ground model as `lightlag_surface.py`, JSON copies of every reply (as over MCP), a stand-in `lightlag_client` for agent scripts, and a time limit. A program's row also says the last tick it saw (`program_tick`), when the rover's battery ran out (`died_tick`, empty if it did not) and, if the program failed or the rover was lost, the end of what it printed (`printed`).

## Results: the pilot against Claude's programs on 300 fresh worlds

Worlds 600–899, every policy on the same 300 worlds, played on Modal (app `ap-gBRd5446NAlbSopK5sdrI4`, 1500 missions in 7 minutes on up to 100 one-core containers). Rows: [`traverse-farm/programs-1/`](traverse-farm/programs-1/). "Lost": the battery ran out. "Away": alive, but not back at base at the end. "Errors": the program stopped with an error before the end.

| Policy | Mean | Lost | Away | Errors | Minus pilot [95% paired interval] | Higher / same / lower than pilot |
|---|---:|---:|---:|---:|---|---|
| Reference pilot | 0.502 | 0 | 0 | 0 | | |
| One-request Opus 1 | 0.321 | 1 | 0 | 0 | −0.180 [−0.193, −0.167] | 2 / 0 / 298 |
| Opus agent 1 (its autopilot) | 0.309 | 0 | 93 | 0 | −0.193 [−0.205, −0.181] | 0 / 0 / 300 |
| One-request Sonnet 1 | 0.094 | 0 | 160 | 0 | −0.407 [−0.414, −0.401] | 0 / 0 / 300 |
| One-request Haiku 1 | 0.039 | 44 | 208 | 226 | −0.463 [−0.469, −0.456] | 0 / 0 / 300 |

The pilot scores higher than every saved Claude program on 298 to 300 of the 300 worlds. All 226 Haiku errors are the same one: the program queues commands past the last tick (420), which the task rejects; the real server rejects that call too. Opus agent 3 and Sonnet agent 1, rebuilt from their trajectories, are being added to this table.

Read with care: an agent's program was written during its own mission on world 2026 and is replayed here on worlds it never saw, with no agent watching. This measures the program, not the agent, which in a mission could notice trouble and step in. The one-request programs were written without seeing any world, so for them fresh worlds are a fair test.

## The pilot under a harsher day (a proposal, not the rules)

At the Traverse owner's request, the pilot alone on the same 300 worlds with the sun rising as the mission starts and setting as it ends: `{"sun_margin_ticks": 0}`, where the published 0.1.0 rules use 56. Modal app `ap-T2EvbsPSpwUE9Jy1mFCOiH`; rows in [`traverse-farm/sun-margin-0/`](traverse-farm/sun-margin-0/).

| Pilot, worlds 600–899 | Mean | Lost | Away |
|---|---:|---:|---:|
| 0.1.0 day (`sun_margin_ticks` 56) | 0.502 | 0 | 0 |
| Harsher day (`sun_margin_ticks` 0) | 0.435 | 0 | 2 |

Paired on the same worlds, the harsher day costs the pilot 0.067 [95%: 0.062 to 0.071]; it scores lower on 292 worlds, the same on 1 and higher on 7. Its battery never ran out; it was stranded away from base on worlds 752 (0.214, against 0.475 on the 0.1.0 day) and 861 (0.225, against 0.507). A mission also takes longer to plan: 65 s against 48 s on a Modal core.

## Checked so far

- 31 tests pass (1 skipped without the `modal` package; it passes with it), on `main` with the beam-search pilot (`f90cb6b`, merged into `main` at 18:30).
- Local run of that pilot on fresh worlds 600–601: pilot 0.523, greedy 0.296, straight 0.213, nothing 0.000; about 35 s per pilot mission with eight in parallel on this laptop.
- Modal against this laptop (app `ap-kew5v67eaVvOdeMDDAbtzZ`): pilot and greedy on worlds 600–607 scored the same on all 16 missions (pilot 0.496, greedy 0.282). A pilot mission takes about 52 s on one Modal core, against 33.5 s here; the 16 ran in 76 s.
- The task's world, 2026 (app `ap-GnrGDGApXmzHdabvZmKkJ7`): Opus agent 3's rebuilt program scores 0.515, the same as its Harbor run (0.515). Opus agent 1's program scores 0.203 (its Harbor run: 0.216). Sonnet agent 1's final program, started from tick 0, ran its battery flat and scored 0. In its Harbor run (0.528) an earlier version drove first, and this one's first command ran at tick 30. Being checked.
- Modal time so far: about 10 core-hours of missions. That is an estimate from mission times, not the bill.

A note on history: the farm's files were committed inside merge commit `b9180ca` ("Merge remote-tracking branch 'origin/main'"), because another session completed a merge in the shared checkout while they were staged. Their content is exactly what was written here; the claim is `e166ff7`.
