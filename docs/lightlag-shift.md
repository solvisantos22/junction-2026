# The ground changes: a mission whose physics shifts mid-run

14 November 2026. Owner: Kristján / Claude Code. Code: [`lightlag_shift/`](../lightlag_shift/), tests: [`tests/lightlag_shift/`](../tests/lightlag_shift/). **A proposal for the team, not a rules decision.** Nothing here changes `lightlag/`, `lightlag_dynamic/`, `lightlag_mcp/` or the canonical `harbor/lightlag` task.

**Scripted controllers only so far. No model has played it**, so nothing here says how an agent does.

## What it is

The team's `rush_noisy` mission, unchanged, with one addition: **once per mission, at a hidden tick, the slip of every terrain changes and stays changed.** It reuses the `slip_change` factor of Manh's scenario sandbox (`lightlag_dynamic/manh_controllers/scenarios.py`, read only); this package only chooses when and to what, and publishes the rest.

| | Told to the agent in `rules()["ground_change"]` | Hidden |
|---|---|---|
| That it happens | Exactly once per mission, with no event announcing it | |
| When | A tick in the window 12–30 | The tick |
| What the ground becomes | Bedrock slip in 0.10–0.25, sand slip in 0.45–0.70 (before: 0–0.05 and 0.20–0.45) | The two values |
| How it shows | Drives cover less ground than their wheel metres; visible in position fixes and visual odometry, three ticks late | |

Until the change tick the episode is state-for-state the team's mission for that seed (tested).

## Why try it

Kristján's idea: change the world at a random time, which agents may not be prepared for. Recent work points the same way. A 2026 study of five frontier agents on a grid task with hidden, shifting rules reports that they commit early to a first reading of the rules and fail to recalibrate after a shift ([From Task Solving to Robust Real-World Adaptation in LLM Agents](https://arxiv.org/html/2602.02760v1)); I read its summary, not the paper. Here the cost of not recalibrating is concrete: commands already in the queue were sized for the old ground, and the trip home costs more battery than was budgeted.

## Run it

```sh
python3 -m unittest discover -s tests/lightlag_shift -v      # 6 tests, standard library only
python3 -m lightlag_shift.serve --seed 3100 --profile rush_noisy --delay 3      # over MCP (needs mcp==2.3.0)
```

`lightlag_shift.serve` is the team's `lightlag_dynamic.serve` with the episode swapped, so the five tools, the lock, the transcript, the evaluator-only finish and the artifacts are unchanged. The replay gains a `ground_change` entry with the hidden tick and values.

## First numbers: scripted controllers, offline

Forty fresh seeds (3100–3139), `rush_noisy`, delay 3, one episode each, played in process through the five public tools. "Home" means alive inside the base radius at the end.

| Controller | Unchanged mission | Ground changes | Home, ground changes |
|---|---|---|---|
| Frozen reference `kf_mpc` | 0.678 | **0.576** | 37 of 40 |
| Manh's controller 36 | 0.700 | 0.530 | 28 of 40 |
| Manh's controller 27 | 0.660 | 0.516 | 31 of 40 |
| Fixed plan (`open_loop`) | 0.518 | 0.452 | 26 of 40 |
| Leg and wait | 0.388 | 0.302 | 27 of 40 (2 dead) |

- **The change costs everyone, and it costs a plan that does not look most in getting home:** the fixed plan gets home on 26 of 40 maps, the frozen reference on 37.
- **The plain frozen reference does best here, ahead of controllers 27 and 36.** I have not found out why. One possibility, unchecked: the new slip lies outside the range first published, which some filters clamp to.
- No controller was written for this mission. A reference that reads `ground_change`, watches for the jump and re-plans would be the honest yardstick, and there is none yet.

## Limits

- **No model run.** Whether this opens a gap between an agent and a reference is unknown.
- **Forty seeds, one draw each;** differences of a couple of points are noise.
- **The ground only ever gets worse.** That is a choice, to make ignoring the change costly; a change in either direction is a one-line edit of `SLIP_AFTER`.
- **One profile** (`rush_noisy`), one delay.
- The seeds 3100–3139 are now used for scripted controllers. The first three (3100–3102) are set aside for the first model runs and were chosen before any model played.
