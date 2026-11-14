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

`replays --policies "pilot,agent:..." --seeds 871 --out <folder>` records whole missions for the demo (see Demo worlds below). Stopping the local `modal run` does not always stop its app: `modal app list` shows it, and `modal app stop --yes <app id>` stops it.

`--mission '{"sun_margin_ticks": 0}'` plays every mission on changed rules (JSON, as `TraverseEnvironment(seed, mission=...)` takes them); each row records them, and missions on other rules stay apart in the same folder.

`evaluate` compares every policy with `--baseline` (default `pilot`) world by world: the mean difference, its 95% paired bootstrap interval, and on how many worlds the policy scored higher, the same, or lower. With `--out`, rows are saved after every 400 missions and a rerun into the same folder plays only missions it has not seen, so policies can be added to a finished comparison.

Agent programs rebuilt from trajectories: Opus agent 3 prepared its autopilot by hand (saved the map to `/tmp/map.json`, built `/tmp/ll/D.pkl` with `route.py`, then started `auto.py` from `/tmp/ll`), so it is replayed through a labelled wrapper, `agent:docs/lightlag-runs/traverse-agent-opus-3/program/farm_prepare.py`. Sonnet agent 1 runs as `agent:docs/lightlag-runs/traverse-agent-sonnet-1/program/auto.py`. Each run's `run.json` says how its program was rebuilt.

`TRAVERSE_SOURCE=<folder>` plays another version of `lightlag_traverse` (for example a commit extracted with `git archive`). Every result row records a hash of the code that played and the machine it ran on.

**Model-written programs run only on Modal**, inside its isolated containers; the local command refuses them. Each program gets the published ground model as `lightlag_surface.py`, JSON copies of every reply (as over MCP), a stand-in `lightlag_client` for agent scripts, and a time limit. A program's row also says the last tick it saw (`program_tick`), when the rover's battery ran out (`died_tick`, empty if it did not) and, if the program failed or the rover was lost, the end of what it printed (`printed`).

## Results: the pilot against Claude's programs on 300 fresh worlds

Worlds 600–899, every policy on the same 300 worlds, played on Modal: the pilot and the first four programs in app `ap-gBRd5446NAlbSopK5sdrI4` (1500 missions in 7 minutes on up to 100 one-core containers), then Opus agent 3 and Sonnet agent 1, rebuilt from their trajectories, added to the same folder in app `ap-758nYv4YvdQRCYPMuSAv1V` (600 missions in 23 minutes; Modal preempted 6 containers and replayed their missions). Rows: [`traverse-farm/programs-1/`](traverse-farm/programs-1/). "Lost": the battery ran out. "Away": alive, but not back at base at the end. "Errors": the program ended with an error.

| Policy | Mean | Lost | Away | Errors | Minus pilot [95% paired interval] | Higher / same / lower than pilot |
|---|---:|---:|---:|---:|---|---|
| Reference pilot | 0.502 | 0 | 0 | 0 | | |
| One-request Opus 1 | 0.321 | 1 | 0 | 0 | −0.180 [−0.193, −0.167] | 2 / 0 / 298 |
| Opus agent 1 (its autopilot) | 0.309 | 0 | 93 | 0 | −0.193 [−0.205, −0.181] | 0 / 0 / 300 |
| Sonnet agent 1 (rebuilt) | 0.265 | 91 | 29 | 300 | −0.237 [−0.260, −0.214] | 8 / 4 / 288 |
| Opus agent 3 (rebuilt) | 0.221 | 157 | 0 | 0 | −0.280 [−0.306, −0.255] | 5 / 1 / 294 |
| One-request Sonnet 1 | 0.094 | 0 | 160 | 0 | −0.407 [−0.414, −0.401] | 0 / 0 / 300 |
| One-request Haiku 1 | 0.039 | 44 | 208 | 226 | −0.463 [−0.469, −0.456] | 0 / 0 / 300 |

The pilot scores higher than every saved Claude program on 288 to 300 of the 300 worlds, and never loses a rover. The two agent programs that came closest to the reference on the task's world lose the most rovers here. Opus agent 3's (0.515 on world 2026, against the reference's 0.565) runs its battery flat on 157 of 300 worlds, between ticks 54 and 395 (median 213); its output shows it still ordering full 5 m drives with the battery at 8.8 of 100 a few ticks before the end. Sonnet agent 1's loses 91 rovers (median tick 139): it checks the battery only at the end of a route, as the Traverse owner found in its code. All of Sonnet agent 1's 300 errors come at tick 417, the same end-of-mission error as in its Harbor run (an uplink that would run past tick 420). Haiku's 226 errors are that error too, at ticks these older rows do not record. The real server rejects that call as well.

Read with care: an agent's program was written during its own mission on world 2026 and is replayed here on worlds it never saw, with no agent watching. This measures the program, not the agent, which in a mission could notice trouble and step in. The one-request programs were written without seeing any world, so for them fresh worlds are a fair test.

## The campaign's worlds, 2027–2029

At the Traverse owner's request, for its three-mission campaign task (`harbor/lightlag-traverse-campaign/` 0.1.0, commit `3bff7b2` on the Traverse branch): the pilot and the six saved programs on exactly the campaign's worlds, each world as a single mission under the unchanged 0.1.0 rules, played with that commit's Traverse code (Modal app `ap-EBzft92juMbdAafja7f7U1`, rows in [`traverse-farm/campaign-worlds/`](traverse-farm/campaign-worlds/)). "Campaign" is the campaign's own score: the value credited in all three missions over the value there was in all three.

| Policy | 2027 | 2028 | 2029 | Campaign |
|---|---|---|---|---:|
| Reference pilot | 0.459 lander | 0.508 lander | 0.460 lander | 0.476 |
| One-request Opus 1 | 0.375 lander | 0.417 lander | 0.292 lander | 0.362 |
| Opus agent 1 | 0.280 lander | 0.216 away | 0.186 away | 0.227 |
| Opus agent 3 | 0.000 lost | 0.457 lander | 0.000 lost | 0.157 |
| One-request Sonnet 1 | 0.099 lander | 0.069 away | 0.151 lander | 0.106 |
| One-request Haiku 1 | 0.030 away | 0.004 away | 0.000 lost | 0.011 |
| Sonnet agent 1 | 0.000 lost | 0.000 lost | 0.000 lost | 0.000 |

The pilot's three missions repeat the campaign's Harbor reference run mission for mission (0.459, 0.508, 0.460; campaign 0.476), a check of the farm against Harbor. Every program scores below the pilot on every one of the three worlds. These are the saved programs, written for one mission on world 2026 and replayed without their agents, one world at a time: a measure of the programs, not of agents playing the campaign. Opus agent 1's score varies from run to run (see Demo worlds).

## Demo worlds: whole missions on fresh ground

Two fresh worlds recorded whole for the demo, on the published 0.1.0 rules (the rules the saved programs were written for): the pilot as the reference, and three agent programs replayed without their agents (Modal app `ap-j4LFeiVghpOyQhGreAsUnH`). Open the page, press Enter, and Tab or click a name to follow that rover.

- [World 871](traverse-farm/replays/world-871.html): at tick 244 Opus agent 3's autopilot is level with the reference (0.39 each, 17 samples against 19) and Sonnet agent 1's is close behind (0.36). Both then run their batteries flat, at ticks 324 and 369, and end with nothing although they hold 19 and 18 samples. The reference brings 25 samples home: 0.524. Opus agent 1 ends at the lander with 0.310.
- [World 610](traverse-farm/replays/world-610.html): both batteries run out early (ticks 166 and 135); the reference brings 28 samples home (0.583), Opus agent 1 0.371.

The run folders beside each page are what `viewer/build_traverse.py --runs <folder>` reads. The pages were built from a copy of `viewer/`, because that builder also rewrites `viewer/traverse/data.json`, which the main demo uses. The reference's and the two lost rovers' missions repeat the comparison's rows exactly. Opus agent 1's program plans with an unseeded random search against the clock, so its score differs from run to run: 0.371 here against 0.354 in the comparison on world 610, 0.310 against 0.354 on 871.

## The pilot under a harsher day (a proposal, not the rules)

At the Traverse owner's request, the pilot alone on the same 300 worlds with the sun rising as the mission starts and setting as it ends: `{"sun_margin_ticks": 0}`, where the published 0.1.0 rules use 56. Modal app `ap-T2EvbsPSpwUE9Jy1mFCOiH`; rows in [`traverse-farm/sun-margin-0/`](traverse-farm/sun-margin-0/).

| Pilot, worlds 600–899 | Mean | Lost | Away |
|---|---:|---:|---:|
| 0.1.0 day (`sun_margin_ticks` 56) | 0.502 | 0 | 0 |
| Harsher day (`sun_margin_ticks` 0) | 0.435 | 0 | 2 |

Paired on the same worlds, the harsher day costs the pilot 0.067 [95%: 0.062 to 0.071]; it scores lower on 292 worlds, the same on 1 and higher on 7. Its battery never ran out; it was stranded away from base on worlds 752 (0.214, against 0.475 on the 0.1.0 day) and 861 (0.225, against 0.507). A mission also takes longer to plan: 65 s against 48 s on a Modal core. The Traverse owner traced both strandings to one end-of-mission flaw and fixed it in task 0.1.1 (a `home_floor` option: on the way home the pilot may spend its reserve down to 2.0), which leaves the 0.1.0 day's scores unchanged.

**Dropped.** The Traverse owner's fresh agent runs under this day scored Opus 0.407 and 0.425 and Sonnet 0.000, against the reference's 0.491 on world 2026, so the best run stayed within 0.07 and the day does not widen the gap at the top. An option search for the 0.1.1 pilot under this day (app `ap-4Je5wVyglx36EqxxsNduKY`, rows in [`traverse-farm/search-sun0-1/`](traverse-farm/search-sun0-1/), including `home_floor`) was stopped after 2 of its 4 generations: the best of 16 settings scored −0.001 and then +0.005 against the defaults on 30 worlds each, and the defaults never lost or stranded a rover. Tuning the options would not have widened the gap either.

## Checked so far

- 31 tests pass (1 skipped without the `modal` package; it passes with it), on `main` with the beam-search pilot (`f90cb6b`, merged into `main` at 18:30).
- Local run of that pilot on fresh worlds 600–601: pilot 0.523, greedy 0.296, straight 0.213, nothing 0.000; about 35 s per pilot mission with eight in parallel on this laptop.
- Modal against this laptop (app `ap-kew5v67eaVvOdeMDDAbtzZ`): pilot and greedy on worlds 600–607 scored the same on all 16 missions (pilot 0.496, greedy 0.282). A pilot mission takes about 52 s on one Modal core, against 33.5 s here; the 16 ran in 76 s.
- The task's world, 2026 (app `ap-GnrGDGApXmzHdabvZmKkJ7`): Opus agent 3's rebuilt program scores 0.515, the same as its Harbor run (0.515). Opus agent 1's program scores 0.203 (its Harbor run: 0.216). Sonnet agent 1's final program, started from tick 0, ran its battery flat at tick 117 with 6 samples taken and scored 0 (rerun with the program diagnostics, app `ap-xv5BaJGa8rfv96Cl9sx7ZQ`); the Traverse owner's sandbox finds the same. In its Harbor run (0.528) an earlier version drove first, and this one's first command ran at tick 30, which carried it past that point.
- A check of the farm, not a result: Opus agent 3's program on the Traverse owner's development worlds 1–8 gives exactly the owner's own eight scores (0.455, 0.443, 0.225 away, 0.487, 0.420, 0.453, 0.519, 0.000 lost). It lost one rover in those 8 worlds and 157 in the 300 fresh ones, so a small set of worlds can hide how often a program fails.
- Modal time: about 39 core-hours of missions across all runs. That is an estimate from mission times, not the bill.

A note on history: the farm's files were committed inside merge commit `b9180ca` ("Merge remote-tracking branch 'origin/main'"), because another session completed a merge in the shared checkout while they were staged. Their content is exactly what was written here; the claim is `e166ff7`.
