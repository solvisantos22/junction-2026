# Lightlag Traverse: normal map and MAX map

Saturday 14 November 2026. Owner: Manh / Claude Code. Code: [`lightlag_traverse_max/`](../lightlag_traverse_max/), tests: [`tests/lightlag_traverse_max/`](../tests/lightlag_traverse_max/test_max_map.py).

Manh asked to carry the max env's mechanics over to Kristján's new Lightlag Traverse, as a choice between the normal map and a MAX map. He also asked to measure four controllers on both maps: his best controller, the frozen reference the team uses, the greedy controller and the straight-line driver.

**A sandbox option, not a rules decision.** Everything is in new files. No file of `lightlag_traverse/`, its tests, its Harbor task or its demo is changed; the MAX map is a subclass of Kristján's `TraverseEnvironment`. Scripted controllers, and Kristján's saved model programs played unchanged; a [frozen model baseline](#a-frozen-model-baseline) waits for its paid step. No API spend so far.

## Run

From the repository root. Python 3.9+, standard library only.

```sh
python3 -m unittest discover -s tests/lightlag_traverse_max -v        # 31 tests, under a minute
python3 -m lightlag_traverse_max.play --seeds 1-8 --maps normal,max --policies manh_max,pilot,greedy,straight
```

```python
from lightlag_traverse_max.environment import make_env
env = make_env(seed=7, option="max")      # option="normal" is Kristján's TraverseEnvironment, unchanged
```

### Watch it

`viewer/build_traverse_max.py` feeds Kristján's Traverse demo page, unchanged, with the four players on one world, one page per map. It plays the missions itself, in about 2 minutes. The pages are about 3 MB each and are not committed.

```sh
python3 viewer/build_traverse_max.py               # world 2026, the task's world: viewer/traverse-players-normal.html and -max.html
python3 viewer/build_traverse_max.py --seed 500    # another world
xdg-open viewer/traverse-players-max.html
```

On world 2026:
- **Normal map:** the pilot and `manh_max` both score 0.565 (the same commands, so one track); greedy 0.250, straight 0.103.
- **MAX map:** `manh_max` scores 0.431 and gets home. The pilot and greedy run out of battery (0.000); straight scores 0.030.

The page was drawn for the normal map, so on the MAX map it lists a slip-check stop as "ground too steep", and after a lost packet it keeps the last position fix.

The same five tools as the normal map (`rules`, `map`, `telemetry_log`, `uplink`, `advance`) and the same scoring. **A seed is the same mission on both maps:** the same ground, targets, deadlines, sun and hidden slip, panel and heading draws. The MAX map draws its own hidden values from separate random streams.

## What the MAX map adds

Every rule is published in `rules()` (and the crust regions in `map()`); only the drawn values are hidden.

| Mechanic | From | On the MAX map | On the normal map |
|---|---|---|---|
| Relay passes | Relay Pass biome | The link is open 4 ticks of every 8. An uplink sent between passes leaves when the next pass opens; a packet due between passes arrives when the next one opens | Always open |
| Onboard slip check | Hidden Valley biome | A drive step that slips more than 0.45 is the last of its drive, and every queued command is discarded (`safety_stop`, reason `slip_limit`) | None |
| Dune slopes | Bagnold Dunes biome | How fast sand slip grows with the slope is hidden in [2.5, 4.5] | 3.5, published |
| Crust | Troy Crust biome | Three regions of 40–80 m, at least 25 m from the lander, mapped as bedrock. Under them, each gentle cell (slope ≤ 0.10) is soft sand with probability 0.10, not listed | None |
| Ripples | Meridiani Ripples biome | Visual odometry noise by terrain: 0.03 on bedrock, 0.05 on regolith and rocks, 0.20 on sand | 0.05 everywhere |
| Weak position fix | Many weak sensors | 2 m per axis | 1 m |
| Hidden wheel size | Many weak sensors | ±20%: a drive of M metres turns the wheels M × scale and pays for that; wheel odometry still reads M | Exact |
| Turn cost | Lab factor | 0.01 × degrees turned × the terrain's drive cost per metre, before the drive | Free |
| Lost packets | Lab factor | 10% of telemetry packets never arrive | None |
| Wild fixes | Lab factor | 5% of position fixes are off by a further 3 m per axis | None |

**Kept from the normal map:** the 5 m drive limit (the max env's 2 m cap was for a 40 m map), the ±5° heading bias, and everything about the world and the mission. **Not carried over:** the max env's beacons and gyroscope (the Traverse telemetry has no such fields) and its wider ±15° heading bias. With every MAX setting off (`NOTHING_ON`), the MAX class plays exactly like Kristján's environment; a test checks the replays, telemetry and maps are identical.

## The players

| Player | What it is |
|---|---|
| **`manh_max`** | **Manh's best.** Kristján's reference pilot, with the layers of the max-env controller `max_navigator` carried over and fixes found on the Traverse (below). **On the normal map it sends exactly the pilot's commands** (a test checks it), so it scores the same there |
| `pilot` | **The frozen reference** on the Traverse: Kristján's `lightlag_traverse/pilot.py`, unchanged, as of his beam search (`f90cb6b`) |
| `greedy` | The pilot without route optimisation: always the best next target by value per tick |
| `straight` | Drives straight at the next target and ignores the ground. **It is not random:** it is deterministic, so a seed always gives the same run |
| `nothing` | Never sends a command |
| `*_fast` | The same with Kristján's smaller search budget, for sweeps |

**Why `kf_mpc` and `max_navigator` are not in the table.** Both were written for the dynamic environment: a flat 40 m square with its own rules. `kf_mpc` stops on the Traverse's first call, because it reads a `drive_cost` rule the Traverse does not publish. `max_navigator` plans on the 40 m square and needs numpy. So the reference here is Kristján's pilot, and Manh's best controller comes over as layers on top of it.

## Results

### Final table: fresh worlds 500–523, full search budgets

Run once, after rebasing onto Kristján's beam search (`f90cb6b`). No player was changed afterwards.

```sh
python3 -m lightlag_traverse_max.play --seeds 500-523 --maps normal,max --policies manh_max,pilot,greedy,straight --workers 12
```

| Map | Player | Mean | Min | Max | Dead | Away | Slip trips | Samples |
|---|---|---|---|---|---|---|---|---|
| normal | **`manh_max`** | **0.498** | 0.373 | 0.554 | 0 | 0 | – | 23.4 |
| normal | `pilot` (reference) | 0.498 | 0.373 | 0.554 | 0 | 0 | – | 23.4 |
| normal | `greedy` | 0.281 | 0.159 | 0.506 | 0 | 13 | – | 19.6 |
| normal | `straight` | 0.173 | 0.011 | 0.485 | 0 | 19 | – | 14.8 |
| MAX | **`manh_max`** | **0.313** | 0.094 | 0.529 | 0 | 7 | 1.9 | 16.9 |
| MAX | `pilot` (reference) | 0.072 | 0.000 | 0.254 | 1 | 15 | 14.4 | 4.1 |
| MAX | `greedy` | 0.058 | 0.000 | 0.174 | 1 | 17 | 13.5 | 5.0 |
| MAX | `straight` | 0.044 | 0.000 | 0.146 | 0 | 19 | 18.5 | 3.9 |

Mean is the share of all the mission's value, as Kristján's runner reports it. Dead: the battery ran out (score 0). Away: alive but not at the lander at the end (half score). Slip trips and samples are means per mission.

Paired on the same worlds, with 95% bootstrap intervals:

| Map | Difference | Mean | 95% interval | Higher on |
|---|---|---|---|---|
| MAX | `manh_max` − `pilot` | **+0.241** | +0.197 to +0.285 | 23 of 24 |
| MAX | `manh_max` − `greedy` | +0.255 | +0.214 to +0.296 | 24 of 24 |
| MAX | `manh_max` − `straight` | +0.269 | +0.225 to +0.318 | 24 of 24 |
| normal | `manh_max` − `pilot` | 0 | exactly 0: the same commands | 0 of 24 |
| normal | `manh_max` − `greedy` | +0.217 | +0.178 to +0.256 | 24 of 24 |
| normal | `manh_max` − `straight` | +0.325 | +0.280 to +0.366 | 24 of 24 |

**What it says:**
- **The MAX map is much harder for every player.** The reference pilot keeps 14% of its normal-map score. Its drives trip the slip check 14 times a mission, every trip throws its queued commands away, and it ends away from the lander on 15 of 24 worlds.
- **`manh_max` keeps 63%**, trips the check about twice a mission, and never ran out of battery.
- **Its weak spot is getting home.** It ended away from the lander on 7 of 24 worlds (503–505 and 515–518), each after one to eight trips, and that halves the score. Its home margins were tuned before Kristján's beam search, which plans more ambitious routes. Re-tuning them on the development worlds is the obvious next step; it is not done.
- On world 516 it ties the pilot (0.194 each); on every other world it is higher.
- Greedy and straight lose most of their score on both maps by ending away from the lander.

### A second sample: worlds 101–124, before the beam search

The first full run, with Kristján's pilot before his beam search:
- MAX map: `manh_max` 0.307 against 0.085 for the pilot (+0.222, 95% +0.168 to +0.272), higher on 23 of 24 worlds; `manh_max` ended away on 2.
- Normal map: both 0.472; greedy 0.300; straight 0.164.

These worlds lie in the farm's search range (100–399), so the claim rests on 500–523.

### Development: worlds 1–24, the fast budget

After the rebase:
- MAX map: `manh_max_fast` 0.362 against 0.091 for `pilot_fast`, higher on 24 of 24.
- Normal map: 0.502 each.

Before the rebase, `manh_max_fast` scored 0.336 on the MAX map.

**Time.** The final run shared this laptop (20 threads) with other jobs. A MAX mission of `manh_max` took 104–321 s (mean 186 s), against 75 s for a normal-map mission of either player. In the first run, with less load, the same comparison was 39 s against 25 s.

## How `manh_max` plays the MAX map

`MaxPilot` in [`players.py`](../lightlag_traverse_max/players.py) subclasses Kristján's `Pilot`. Every addition switches on only when its rule is in `rules()`, which is why the normal map is untouched.

**From the max-env controller:**
- **Lost packets:** the drives in a lost packet are replayed on the model, with extra uncertainty. A stop hidden in a lost packet shows up when the next packet says a scheduled command did not run. Every packet lists the sampled targets, which settles samples whose own packet was lost.
- **Wild fixes:** each fix is weighted by the chance that it is an ordinary one.
- **Wheel size:** read off the exact battery. The first two downhill drives on one terrain whose energy per wheel metre agrees within 0.2% give the scale. Until then, a rough scale from visual odometry.
- **Slip check:** the ground graph drops edges and straight lines whose predicted slip would trip the check, with margins (the hidden sand gain is taken high). A trip lowers that terrain's trip grade.
- **Crust:** an uphill edge through a crust region carries the expected cost of a hidden soft cell tripping the check. A cell the rover reports as sand inside the crust becomes sand on its map.
- **Relay passes:** each command is planned for the tick it will really run.

**New, found by tracing failed missions on development seeds 1–24:**
- **Stale commands.** A command sent before the news of a trip arrives was planned for a place the rover never reached, and trips again, every relay pass. Now the prediction stops a queued drive where the best estimate says it trips, and nothing is sent until it has run.
- **A tube, not a line:** the trip check also looks one predicted position sigma to either side of a drive.
- **Visual odometry** is weighed against the drive model by its published noise per terrain.
- **Turn cost** is in the battery forecast and the energy floor.
- **Edges and lines agree:** an edge is judged by its cells' steepest slope along it, as a line is checked every 1.25 m. When they disagreed, the rover drove back and forth.
- **Getting unstuck:** an aim point is kept while it is still ahead and safe. A target that 12 drives have not brought 1 m closer is given up. A stalled way home follows the cost-to-go field vertex by vertex; if the margins leave no way home, they are dropped.
- **Home earlier:** on the MAX map the way home is counted 1.25 times longer than the model says, with 8 ticks to spare (the pilot: 1.08 and 4). Over seeds 1–24 this was the best of three settings tried.

### What each mechanic costs

Each MAX mechanic switched on alone, and each switched off with all the others on. Development worlds 1–6, the fast budgets, the code as pushed. Six worlds only, so differences under about 0.04 are noise.

| Mechanic | Pilot: only this on | `manh_max`: only this on | Pilot: all but this | `manh_max`: all but this |
|---|---|---|---|---|
| **None on** | 0.493 | 0.473 | – | – |
| **All on** | 0.069 | 0.357 | – | – |
| Slip check | **0.346** | 0.449 | 0.089 | **0.421** |
| Hidden wheel size | **0.323** | 0.464 | **0.162** | 0.327 |
| Lost packets | **0.336** | 0.470 | 0.097 | 0.355 |
| Relay passes | 0.477 | 0.457 | 0.111 | 0.379 |
| Wild fixes | 0.495 | 0.469 | 0.056 | 0.388 |
| Weak position fix | 0.490 | 0.464 | 0.073 | 0.373 |
| Dune slopes | 0.494 | 0.473 | 0.049 | 0.338 |
| Turn cost | 0.496 | 0.474 | 0.074 | 0.324 |
| Ripples | 0.491 | 0.467 | 0.063 | 0.309 |
| Crust | 0.505 | 0.491 | 0.045 | 0.331 |

- **For the pilot, three mechanics do most of the damage on their own: the slip check, the hidden wheel size and lost packets.** Together they compound: with any single one switched off, the pilot still scores at most 0.162.
- **`manh_max` loses at most 0.024 to any one mechanic.** With all of them on it loses 0.116, and the slip check is the biggest part of that: switching it off gives back 0.064.
- With every mechanic off, `manh_max` scores a little below the pilot (0.473 against 0.493). It still reads `map_option: "max"` in `rules()` and keeps the MAX map's wider home margins. On Kristján's own environment it plays exactly like the pilot.

## A frozen model baseline

Manh asked for superhard and fair MAX worlds as a fixed point to measure Claude Opus 5.5, Sonnet 5.5 and Haiku 5.5 against. Everything below was frozen in [`docs/lightlag-runs/max-baseline/`](lightlag-runs/max-baseline/README.md) before any paid call. Code: [`lightlag_traverse_max/oneshot.py`](../lightlag_traverse_max/oneshot.py) and [`sandbox.py`](../lightlag_traverse_max/sandbox.py); tests: [`test_oneshot.py`](../tests/lightlag_traverse_max/test_oneshot.py).

- **The worlds, picked by Manh from the 24 fresh worlds 500–523 by `manh_max`'s MAX-map score.** *Superhard:* 505, 509 and 515, where it scores 0.199, 0.180 and 0.094 (515 is the hardest of the 24; 509 is the only very hard one where it still gets home). *Fair:* 500, 510 and 520, where it scores 0.455, 0.481 and 0.529 and gets home, keeping 82–99% of its normal-map score. On the normal map all six are ordinary (0.44–0.55), so the MAX map is what makes the superhard ones hard. World 2026, the task's world, sits beside them as an anchor next to Kristján's normal-map baseline. First frozen at 21:07 with the 8 worlds under 0.2 (503, 504, 505, 509, 515, 516, 517, 518); re-frozen at 21:34 with Manh's six, before any request was sent (`freeze.json` keeps the first). **Caveat:** the worlds were picked by how `manh_max` did there, so its own scores on them are biased (low on superhard, high on fair). A model's are not.
- **The request.** Kristján's one-request text (`lightlag_traverse/oneshot.py`, unchanged), filled from the MAX map's example world 99991, plus one section on what the MAX map changes. The rules shown are the MAX map's public rules. No hidden value appears in the request (tested).
- **The models.** Each model writes 3 programs, from 3 separate requests: effort `medium`, adaptive thinking, up to 128,000 output tokens, no retries and no fallback model. Kristján's Opus reply used 50,450 of his 64,000, so the limit is higher here. A reply counts as it came.
- **Playing.** Docker is not installed on this machine, so [`sandbox.py`](../lightlag_traverse_max/sandbox.py) runs Kristján's worker, unchanged, under bubblewrap: no network, read-only files, user nobody, Python 3.12, his timeouts and call cap. It replays his Docker run of his normal-map Opus program byte for byte (tested).

Free results so far on the MAX map, mean over each group (per-world tables in the [baseline's README](lightlag-runs/max-baseline/README.md)):

| Player | Superhard (505, 509, 515) | Fair (500, 510, 520) | World 2026 |
|---|---|---|---|
| `manh_max` | 0.157 | 0.488 | 0.431 |
| Reference pilot | 0.036 | 0.102 | 0.000, lost |
| Greedy | 0.013 | 0.058 | 0.000, lost |
| Straight line | 0.036 | 0.031 | 0.030 |
| Kristján's Opus 5.5 program, written for the normal map | 0.038 | 0.049 | 0.078 |
| Kristján's Sonnet 5.5 program, written for the normal map | 0.029 | 0.020 | 0.039 |
| Kristján's Haiku 5.5 program, written for the normal map | 0.014 | 0.003 | 0.013 |

Even on the fair worlds, players that ignore the MAX rules score 0.003–0.10; only a MAX-aware player reaches about 0.5 there.

The paid step sends 9 requests. At Kristján's measured usage that is about $1 per Opus reply, $0.25 per Sonnet reply and $0.02 per Haiku reply: about $5 in all. If every reply used all 128,000 tokens it would be $12. `ask` refuses any call whose worst case would take the total past the budget given. The key goes in the gitignored `.env`; it is never printed or stored.

```sh
python3 -m lightlag_traverse_max.oneshot ask --budget-usd 10 --env-file .env   # paid: 9 requests
python3 -m lightlag_traverse_max.oneshot play                                  # free: every program on every world
python3 -m lightlag_traverse_max.oneshot report                                # rewrites the baseline's README
```

## Held-out evaluation worlds

Manh decided on Saturday 14 November that the six baseline worlds are the team's test worlds on the MAX map, held out for everyone. The rule is in [`AGENTS.md`](../AGENTS.md#held-out-evaluation-worlds-traverse-max-map), so every chat reads it after pulling.

- **Test on:** fair 500, 510, 520 and superhard 505, 509, 515, MAX map. Report the mean on each group of three beside `manh_max` (0.488 fair, 0.157 superhard) and the reference pilot (0.102, 0.036).
- **Never train, tune or select on them**, on either map: a seed is the same ground on both. The whole pool 500–523 is off limits, because the six were picked by looking at it. Kristján's 2026–2029 and 99991 stay reserved as he set them.
- **In code:** [`lightlag_traverse_max/heldout.py`](../lightlag_traverse_max/heldout.py) holds the list. `check_training_seeds(seeds)` raises an error on any reserved world; the baseline in `oneshot.py` reads its worlds from there (tested).
- **The page:** [`viewer/traverse-evaluation-max.html`](../viewer/traverse-evaluation-max.html), committed, opens from disk. Kristján's Traverse page (`viewer/traverse/`, unchanged) shows each world as one site, keys 1–6, with the reference pilot, `manh_max`, greedy and straight line. Rebuild it (about 2 minutes) with `python3 viewer/build_traverse_max.py --evaluation`. Checked in headless Firefox, not Chrome.
- **Kristján's pages are untouched.** `traverse-demo.html` (world 2026) and `traverse-campaign.html` (2027–2029) are the normal-map submission demo, and those worlds stay their reference.

## Harbor tasks

Kristján approved (through Manh) a Harbor task for the MAX map. There are two, one per group of held-out worlds:

| Task | Worlds | Reference pilot (campaign score) | Doing nothing |
|---|---|---|---|
| [`harbor/lightlag-traverse-max-fair/`](../harbor/lightlag-traverse-max-fair/instruction.md) | 500, 510, 520 | 0.103 (36.25 of 352) | 0.000 |
| [`harbor/lightlag-traverse-max-superhard/`](../harbor/lightlag-traverse-max-superhard/instruction.md) | 505, 509, 515 | 0.036 (12.5 of 345) | 0.000 |

- **Each is Kristján's campaign task with the MAX map behind it.** Three missions in a row, scored together (value earned over value available), 45 minutes. The agent image, client, ground model, verifier, grader and reference solution (his pilot) are his, byte for byte (tested). His generator, `lightlag_traverse/make_task.py`, is imported, not changed; his two tasks are unchanged (tested).
- **What differs:** the simulator's container also holds `lightlag_traverse_max/` and starts [`lightlag_traverse_max/server.py`](../lightlag_traverse_max/server.py): his server and campaign, with every mission on the MAX map. The seeds sit only in the simulator's `docker-compose.yaml`. The instruction is his campaign text plus the MAX section from the one-request baseline, and the server's instructions gain one paragraph on the MAX map.
- **Regenerate** with `python3 -m lightlag_traverse_max.make_task` (`--check` reports stale copies). [`test_task.py`](../tests/lightlag_traverse_max/test_task.py) also serves a task's own simulator folder over HTTP, reaches it with the agent's own client, finishes it through the evaluator route and grades it with the task's grader.
- **Built and run in Docker** (Saturday about 23:15, Harbor 0.25.0, Docker 29.1.3, from a fresh clone of `main`): `-a oracle` gives 0.102983 on the fair task and 0.036232 on the superhard one, the scores measured in process, and `-a nop` gives 0.000000 on both ([rows](second-machine-check/harbor-runs.json)). No agent has played these tasks yet.
- **The reference solution is too weak for a gap task.** It is Kristján's normal-map pilot. Claude Opus 5.5's four one-request programs score 0.30 to 0.49 on the fair worlds and 0.11 to 0.27 on the superhard ones, around `manh_max` (0.487 and 0.158) and far above the pilot. See [the second-machine check](second-machine-check.md#max-map-manh_max).

## Limits

- **Against Opus the MAX map has no gap yet.** Of four Opus replies to the frozen request, one beats `manh_max` on the fair task and two beat it on the superhard task; on 100 fresh MAX worlds two of Opus's programs are higher on 45 and 47 ([Kristján's check](max-map-claude-check.md), [the second-machine check](second-machine-check.md)). Sonnet and Haiku are far behind.
- **The frozen one-request baseline has two sets of replies:** Kristján's key in `replies/` (all nine) and Manh's key in `replies-manh/` (six). The Harbor tasks above have not been run with an agent.
- **`manh_max` is one end-of-day rule behind the pilot.** Kristján's `home_floor` (task 0.1.1: spend the reserve on the way home) is not carried over. On his normal-map worlds 2026 to 2029 the scores are identical and only the last 53 ticks of world 2027 differ. On the MAX map `manh_max` ends away from the lander on 17 of 100 fresh worlds, so that rule is the first thing to try.
- **24 fresh worlds, one run each.** Scores vary a lot from world to world, so differences under about 0.03 are noise.
- **The MAX settings are the max env's values, carried over, not tuned for the Traverse.** The slip check is 0.45, the catalog's value for long missions (the 50-tick max env uses 0.40).
- **`manh_max` is slower on the MAX map.** Each time its ground costs are rebuilt (a trip, a soft cell, the wheel size), Kristján's pilot runs its full route search again. See **Time** above.
- `manh_max` was tuned on development seeds 1–24 only: the home margins, the stall limit and the tube width.

## Seeds

- **Development: 1–24**, part of Kristján's development range 1–99, used read-only as he does.
- **101–124:** a first full run, before rebasing onto Kristján's beam search. They lie inside the farm's search range 100–399, so they are reported above but not used for the claim.
- **Final: 500–523.** Unclaimed in `TEAM_STATUS.md` before this run; now used.
- **Model baseline: superhard 505, 509, 515; fair 500, 510, 520** (chosen from 500–523 as above), **and 2026**, the task's world. Example world in the request: 99991, Kristján's, never evaluated. The six are the team's [held-out evaluation worlds](#held-out-evaluation-worlds).

## Suggested next steps (not done)

1. Re-tune `manh_max`'s MAX home margins on the development worlds now that the pilot plans with a beam search: 7 of 24 fresh MAX missions ended away from the lander.
2. A Harbor task or MCP entry for the MAX map, so that a model can play it. API spend: a team decision.
3. Skip the full route search after a small rebuild, to make `manh_max` faster on the MAX map.
4. A MAX row in the Traverse demo.
