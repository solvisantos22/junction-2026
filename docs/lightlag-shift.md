# The ground changes: a mission whose physics shifts mid-run

14 November 2026. Owner: Kristján / Claude Code. Code: [`lightlag_shift/`](../lightlag_shift/), tests: [`tests/lightlag_shift/`](../tests/lightlag_shift/). **A proposal for the team, not a rules decision.** Nothing here changes `lightlag/`, `lightlag_dynamic/`, `lightlag_mcp/` or the canonical `harbor/lightlag` task.

**Three model runs so far, on the first mission only** (below): Claude copes. The second mission, where one of four rules changes, has four model runs: Claude is behind the reference on average, for mixed reasons.

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

## First model runs: Claude copes, with one weaker map

Saturday evening, with Kristján's approval for the spend. Claude Opus 5.5 through OpenCode 1.19.5 and Harbor, one attempt on each of the three seeds set aside beforehand, against the frozen `kf_mpc` played through Harbor on the same task. Runs: `docs/lightlag-runs/shift-ground-seed310*`. Reported model cost: $1.72.

| Seed | Ground changes at tick | Claude Opus 5.5 | Frozen reference | What happened to Claude |
|---|---|---|---|---|
| 3100 | 13 | **0.46** (6 of 13) | 0.62 (8 of 13) | Three failed samples after the change (ticks 16, 20, 26); home alive |
| 3101 | 27 | **0.69** (9 of 13) | 0.65 (8.5 of 13) | One failed sample; home alive |
| 3102 | 23 | **0.89** (8 of 9) | 0.89 (8 of 9) | One failed sample, right after the change; home alive |
| Mean | | 0.68 | 0.72 | |

- **This is not a gap.** Claude is ahead on one map, level on one and behind on one, and it never lost the rover. Three runs cannot separate 0.68 from 0.72.
- **Claude noticed.** Its closing report on seed 3102 says that wheel slip on bedrock jumped to about 18%.
- **The one clear loss is the map where the change came earliest.** With 37 ticks left to play on the new ground, Claude missed three samples in a row. That suggests, on one run, that an earlier window would bite harder; it is a guess until tested.

## Limits

- **Three model runs, one per seed.** Whether this opens a gap between an agent and a reference is still unknown.
- **Forty seeds, one draw each;** differences of a couple of points are noise.
- **The ground only ever gets worse.** That is a choice, to make ignoring the change costly; a change in either direction is a one-line edit of `SLIP_AFTER`.
- **One profile** (`rush_noisy`), one delay.
- The seeds 3100–3139 are now used for scripted controllers. The first three (3100–3102) are set aside for the first model runs and were chosen before any model played.

## Step two: a rule changes, and nothing says which

Added Saturday evening, also at Kristján's request: he wanted the rules themselves to change, so that the agent has to realise it is no longer playing the game it read about. Code: [`lightlag_shift/rule_change.py`](../lightlag_shift/rule_change.py), reference: [`lightlag_shift/reference.py`](../lightlag_shift/reference.py). **Scripted controllers only; no model has played it.**

Once per mission, at a hidden tick in the same window (12–30), **one** of four changes happens. `rules()["rule_change"]` publishes the whole menu with its ranges, and that entry never changes afterwards, so asking again does not reveal which one it was. Each is an existing factor of Manh's sandbox, switched on at the hidden tick.

| Change | What happens | Published range | How it shows |
|---|---|---|---|
| `ground` | The slip of every terrain changes | Bedrock 0.10–0.25, sand 0.45–0.70 | Drives cover less ground than their wheel metres |
| `turning` | Turning costs energy, per degree of heading change at the start of a drive | 0.02–0.04 per degree, times the drive cost (double on sand) | The battery falls faster than idle, drive and sample costs explain |
| `link` | Each telemetry packet is lost with a fixed probability | 0.25–0.45 | Ticks missing from telemetry |
| `relay` | Uplinks go out only while a relay is overhead | 4 ticks in every 8, counted from tick 0 | An acknowledgement whose `transmit_tick` is later than the tick it was sent |

Each calls for a different response, which is the point: the agent has to diagnose before it can adapt.

```sh
python3 -m unittest discover -s tests/lightlag_shift -v                     # 18 tests for both missions
LIGHTLAG_SHIFT_MISSION=rule python3 -m lightlag_shift.serve --seed 3300 --profile rush_noisy --delay 3
```

### Numbers: scripted controllers, offline

Forty fresh seeds (3200–3239), `rush_noisy`, delay 3, each kind of change forced in turn so every cell has 40 episodes. Mean score, then deaths and episodes ending home, out of 40.

| Controller | No change | `ground` | `turning` | `link` | `relay` |
|---|---|---|---|---|---|
| **Prepared reference** (controller 36, told the worst turning cost on the menu) | 0.745 | **0.626** · 0 dead · 40 home | **0.655** · 0 · 40 | **0.636** · 0 · 38 | **0.662** · 0 · 40 |
| Controller 36 as it is | 0.745 | 0.581 · 0 · 32 | 0.491 · 10 · 23 | 0.659 · 0 · 34 | 0.716 · 0 · 39 |
| Frozen reference `kf_mpc` | 0.729 | 0.608 · 1 · 36 | 0.414 · 17 · 23 | 0.446 · 12 · 21 | 0.717 · 0 · 40 |
| Fixed plan (`open_loop`) | 0.580 | 0.533 · 0 · 32 | 0.566 · 1 · 37 | 0.580 · 0 · 38 | 0.580 · 0 · 38 |

- **The prepared reference never loses the rover in 160 episodes** and ends home in 158. It does not diagnose anything: it reads the published menu and budgets from the first tick for the costliest turning rule on it. That costs it some score when the change is something else (0.662 against 0.716 on `relay`).
- **A controller that is good at the unchanged mission is not safe here.** The frozen reference loses the rover in 17 of 40 episodes when turning starts to cost energy and in 12 of 40 when packets go missing.
- **`relay` barely matters** at 4 ticks in 8. It is on the menu as a decoy that still has to be told apart from the others; a tighter pass would make it bite.
- A reference that works out which change happened and responds only to that one should beat the prepared one. There is none yet.

### First model runs on step two: behind the reference on average, for mixed reasons

Saturday evening, with Kristján's approval for the spend. Claude Opus 5.5 through OpenCode 1.19.5 and Harbor, one attempt per map. The four seeds are the first from 3300 upward to draw each kind of change, fixed before any run. The prepared reference played the same seeds in process (it needs numpy and so plays outside the container). Runs: `docs/lightlag-runs/shift-rule-seed33*`. Reported model cost: $1.77.

| Seed | Hidden change | Claude Opus 5.5 | Prepared reference | Claude's own diagnosis |
|---|---|---|---|---|
| 3300 | Lost telemetry from tick 18 | **0.61** | 0.48 | Correct: "almost certainly lost telemetry", with the missing ticks listed |
| 3301 | Turning cost from tick 20 | **0.78** | 0.78 | Correct, to three decimals: about 0.031 per degree against a hidden 0.0311 |
| 3302 | Ground from tick 20 | **0.56** | 0.78 | **Wrong:** it concluded relay passes, from one uplink that executed three ticks later than it expected |
| 3327 | Relay passes from tick 18 | **0.00**, rover lost | 0.65 | Wrong ("may have been the ground"), but see below |
| Mean | | 0.49 | 0.67 | 2 of 4 right |

- **On average Claude is behind, 0.49 against 0.67, but four single attempts do not make a gap,** and the reasons differ map by map.
- **The lost rover was not caused by the rule change.** On seed 3327 every uplink Claude sent happened to fall inside an open relay pass, so the change never touched it, and it could not have seen it. It lost the rover the way it did on the Deadlines mission: it queued a detour for a late target worth half a point with 33.2 battery when the plan needed 34.4, and says so in its report.
- **One real misdiagnosis.** On seed 3302 the ground changed and Claude decided it was relay passes. It missed a sample after the change and came home with 10.8 battery unspent, 0.22 behind the reference.
- **Two clean diagnoses,** one of them exact, and on the lost-telemetry map Claude beat the prepared reference.
- **A design flaw this exposed:** the relay change can pass unnoticed and without effect if the agent's uplinks happen to land inside passes. As set (4 ticks in 8) it is a weak entry on the menu.

### Limits of step two

- **Four model runs, one per kind of change.** Suggestive at most.
- **Forced kinds for the table.** In a real mission the seed picks the kind; over 400 seeds each came up between 83 and 120 times.
- **Seeds 3200–3239 are used.** The prepared reference's single setting (the top of the published turning range) was chosen before this table was run, from the menu, not tuned on these seeds; I tried no other setting.
- The reference needs numpy, like all of Manh's controllers, so it plays outside the agent's container.
