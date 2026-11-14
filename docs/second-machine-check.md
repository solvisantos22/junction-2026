# Second-machine check: reproduction, `manh_max` on Kristján's worlds, and can an agent beat our controllers

Saturday 14 November 2026, about 23:20 Helsinki; section 4 added at midnight. Owner: Manh / Claude Code (biomes chat). Checked at commit `c406475` of `main`, from a fresh clone; the MAX comparison in section 3 uses the farm's rows as of `cf144ad`. **A check, not a rules or reference decision.** New files only: [`tools/second_machine_check/`](../tools/second_machine_check/), [`tests/second_machine_check/`](../tests/second_machine_check/test_verify_replays.py), [`docs/second-machine-check/`](second-machine-check/) and this page. No task, rule, controller or teammate's file is changed.

Manh asked four things about Kristján's Lightlag Traverse ([write-up](lightlag-traverse-campaign.md)): what his seeded worlds and Harbor testing show, how Manh's best controller does on them, whether judges can reproduce the scores, and whether a Claude agent will ever beat the controllers we designate as references.

## Bottom line

- **The submission reproduces exactly on a second machine.** From a fresh clone on Manh's Linux laptop, Harbor with local Docker gives the reference **0.476257** on the campaign and **0.564655** on world 2026, and 0 for doing nothing. Every replay file is byte for byte the one Kristján committed from his Mac.
- **Every reported Claude score can be re-derived without a model.** All 24 saved runs play again from their command logs to their saved scores, on Python 3.12 and 3.14.
- **On Kristján's normal map, `manh_max` is the reference:** 0.476257 on the campaign, 0.564655 on world 2026. It is one end-of-day rule behind his newest pilot, which changes 53 ticks on world 2027 and no score.
- **On the normal map the reference still wins nearly every world, but the margin is thinner than our write-ups say.** 0 of 7 agent runs beat it on the campaign, and Claude's programs beat it on at most 0.1% of simulated three-world campaigns. Yet the four newer one-request Opus programs score 0.34 to 0.45 on fresh worlds against its 0.500, where the older program scores 0.326, and one of them scores **0.474 on the campaign's own worlds, against 0.476** ([section 4](#4-why-opus-looks-closer-on-the-max-map)). **The reference is not the ceiling either:** with its battery reserves off, the same planner scores 0.487 there.
- **On the MAX map, Opus already matches `manh_max`.** Two of Opus's three farm-played programs beat it on 45 and 47 of 100 fresh worlds, and on 36% and 38% of simulated three-world campaigns. The MAX Harbor tasks ship Kristján's normal-map pilot as their reference solution (0.103 and 0.036), which Opus's programs beat several times over.

## 1. Can a judge reproduce it?

Machine: Manh's laptop, Ubuntu 24.04, x86-64, 20 cores, Docker 29.1.3, Harbor 0.25.0, host Python 3.14.7. Kristján's runs came from Harbor 0.25.0 with Docker on his Mac.

| Check | Result |
|---|---|
| Fresh clone of `main` from GitHub | Works; 5 minutes on this network, 1.2 GB on disk |
| `python3 -m unittest discover -s tests/lightlag_traverse` | 75 tests pass on Python 3.14 and on 3.12, the containers' version |
| `python3 -m lightlag_traverse.make_task --all --check` | Both task folders match their sources |
| `harbor run -p harbor/lightlag-traverse-campaign -a oracle` | **0.476257**, 4 minutes; `result.json` and all three missions' `replay.json` identical to `docs/lightlag-runs/campaign-reference` |
| `harbor run -p harbor/lightlag-traverse-campaign -a nop` | 0.000000; replays identical to `campaign-do-nothing` |
| `harbor run -p harbor/lightlag-traverse -a oracle` | **0.564655**, 4 minutes; `replay.json` and `result.json` identical to `traverse-reference` |
| `harbor run -p harbor/lightlag-traverse -a nop` | 0.000000; replay identical to `traverse-do-nothing` |
| The reference in this process, no Docker (Python 3.14) | Campaign and world 2026: every file identical to Kristján's Harbor runs |
| All 24 saved runs played again from their command logs | 24 of 24 reproduce: every state, packet, result and verifier reward, on Python 3.12 and 3.14 |
| MAX tasks: `-a oracle` and `-a nop`, fair and superhard | 0.102983 and 0.036232, as measured in process; 0.000000 for doing nothing. The images build and run |

Rows: [`harbor-runs.json`](second-machine-check/harbor-runs.json), [`replays-python-3.12.json`](second-machine-check/replays-python-3.12.json), [`replays-python-3.14.json`](second-machine-check/replays-python-3.14.json).

**What the replay check means.** An agent run cannot be repeated: the model answers differently each time. But each saved run keeps every command with the tick it was sent, and the simulator is deterministic. [`verify_replays.py`](../tools/second_machine_check/verify_replays.py) sends the commands again to a fresh world and compares everything. So the seven Claude campaign scores (0.000 to 0.293) and the eight one-site scores are checked facts about what those agents sent, not only numbers in a table.

**What a judge could trip on.**

- **The first Harbor run failed here, with no score.** Fetching the base image `python:3.12-slim` timed out on a DNS lookup of Docker Hub. Harbor reported an exception and recorded no reward; the next attempt ran. Kristján saw the same on Saturday. Harbor removes the built images after each trial, and each build asks Docker Hub about the base image again, so every run needs the network. Worth one line in the README: if a run ends in seconds with an exception, run it again.
- **The reference takes about four minutes here**, image builds included, not two.
- **The clone is large:** 1.2 GB, five minutes on the venue network.
- **Every OpenCode run ends with `NonZeroAgentExitCodeError`** in the saved runs, with the reward recorded. The README says so already.
- **Not checked here: a run with a model.** No OpenCode agent run was made on this machine, so the OpenCode install, its link to the five tools and the model call are verified only on Kristján's Mac.

## 2. Manh's best controller on Kristján's worlds

`manh_max` and the reference pilot, each through the service its Harbor task uses ([`kristjans_worlds.py`](../tools/second_machine_check/kristjans_worlds.py), rows in [`kristjans-worlds.json`](second-machine-check/kristjans-worlds.json)). The other Manh controllers (`max_navigator`, controllers 36 and 37) plan on the flat 40 m square of the earlier environment and cannot drive the Traverse.

| | World 2026 | Site 2027 | Site 2028 | Site 2029 | Campaign |
|---|---:|---:|---:|---:|---:|
| **Normal map** (Kristján's rules) | | | | | |
| Reference pilot | 0.565 | 0.459 | 0.508 | 0.460 | **0.476** |
| `manh_max` | 0.565 | 0.459 | 0.508 | 0.460 | **0.476** |
| Best Claude agent run | 0.528 | 0.351 | 0.486 | 0.269 | 0.293 |
| **MAX map**, same worlds | | | | | |
| `manh_max` | 0.431 | 0.351 | 0.223, away | 0.134, away | **0.235** |
| Reference pilot | 0, lost | 0.030, away | 0.012, away | 0.042 | 0.028 |
| Opus 5.5 one-request program (Kristján's key) | 0.207 | | | | |

"Best Claude agent run" is the best per column, from different runs; the best single campaign run is the 0.293.

- **Normal map: the same score, because it is the same planner.** `manh_max` is Kristján's pilot with layers that switch on only on the MAX map. On worlds 2026, 2028 and 2029 its replay is byte for byte the reference's.
- **One difference, on world 2027.** At tick 364 the reference drives on, spending its reserve on the way home (the `home_floor` rule Kristján added in task 0.1.1). `manh_max` waits one tick: its copy of that step is from before the rule. The last 53 ticks differ; the samples, the ending and the score do not. So "move for move like the pilot" holds until the way home, and the test for it stops at tick 100.
- **MAX map on his worlds:** `manh_max` scores 0.235 over the three sites where the pilot scores 0.028, but it ends away from the lander at two of the three, which halves those sites. Carrying the pilot's way-home rule into `manh_max` is the obvious thing to try next; it is not done here.

## 3. Will an agent beat our designated controllers?

### Normal map: the reference pilot (the submission)

| Evidence | Result |
|---|---|
| Agent runs on the campaign (4 Opus, 2 Sonnet, 1 Haiku) | 0 of 7 above the reference; the closest is 0.18 below |
| Agent runs on world 2026 | 0 of 8 above; the closest is 0.04 below. Two had beaten the first pilot (0.448) before its beam search |
| Saved Claude programs on 300 fresh worlds, single worlds | Higher than the reference on 0 to 2.7% of worlds |
| The same, as 200,000 random three-world campaigns | Higher on 0.00 to 0.06% of campaigns |
| The best Claude score on each world, in hindsight | Higher on 4.3% of worlds and 0.26% of campaigns |
| The four newer one-request Opus programs (written from the MAX request), 30 fresh worlds | 0.342 to 0.453 against 0.500; higher than the reference on 2 of 120 world-plays and on at most 0.1% of three-world campaigns ([section 4](#4-why-opus-looks-closer-on-the-max-map)) |
| **The same four on the campaign's own worlds** | **0.267, 0.342, 0.409 and 0.474, against 0.476.** The best is 0.75 points of 358 short over the three sites and beats the reference at site 2029 (0.513 against 0.460) |
| **The reference with its reserves off** | **0.487 on the campaign's worlds (0.461, 0.514, 0.483): higher at all three sites.** On fresh worlds higher on 49.7% of worlds and 58.5% of campaigns, mean 0.489 against 0.502, 10 rovers lost in 300 |

From [`outperform.py`](../tools/second_machine_check/outperform.py) on the farm's saved rows ([`outperform.json`](second-machine-check/outperform.json)); the reserves-off scores were played again here and agree with the farm's.

- **A win over the reference on the campaign is still unlikely, but it is not far off.** The older saved programs are about 0.2 short, the worth of whole-route planning with a battery forecast. The four newer Opus programs are 0.05 to 0.16 short on fresh worlds and almost never ahead, and three worlds in a row leave little room for luck. On the campaign's own three worlds the best of them is 0.002 short.
- **It is not impossible.** The reference keeps a battery reserve that costs it about 0.01 on these three worlds. A program that planned as well and gambled the reserve would score 0.487 here. It would also lose a rover on about one world in thirty.
- **Unknowns.** Seven runs do not give a rate. The judges' model is not disclosed, and nothing stronger than Opus 5.5 has played. No upper bound on the achievable score is known.

### MAX map: `manh_max`

| Evidence | Result |
|---|---|
| Opus 5.5 one-request programs (Kristján's key, replies 1 / 3 / 2) on 100 fresh MAX worlds | 0.289 / 0.293 / 0.207 against 0.317; higher than `manh_max` on **47 / 45 / 23 of 100 worlds** and on **37.7% / 35.8% / 10.1% of random three-world campaigns** |
| The best Claude score on each fresh world, in hindsight (nine programs) | Higher than `manh_max` on 62 of 100 worlds and 68% of campaigns |
| Sonnet 5.5 and Haiku 5.5 programs, same worlds | 0.031 to 0.081; higher on 1 to 4 worlds of 100 |
| Fair task (500, 510, 520), campaign score | `manh_max` 0.487; four Opus programs 0.490, 0.479, 0.439 and 0.295 |
| Superhard task (505, 509, 515), campaign score | `manh_max` 0.158; four Opus programs 0.270, 0.178, 0.107 and 0.106 |
| The MAX tasks' own reference solution (Kristján's pilot) | 0.103 fair, 0.036 superhard |

- **Yes, on the MAX map it already happens.** Four Opus replies exist, three from Kristján's key and one from Manh's, all written from the same frozen request. One beats `manh_max` on the fair task and two beat it on the superhard task, one of them by 0.11. Against Sonnet and Haiku the gap is wide.
- **It is not one lucky draw.** Three of the four Opus programs score 0.280 to 0.346 over the seven baseline worlds, against `manh_max`'s 0.338; the fourth scores 0.192.
- **The MAX Harbor tasks are not gap tasks as packaged.** Their reference solution is the normal-map pilot, which most Opus programs beat by a factor of three to seven. To show a gap against Opus the MAX map needs a stronger reference than `manh_max`; `manh_max` as the solution would only tie. Kristján's farm session reached the same conclusion ([his note](max-map-claude-check.md)).

### Two sets of replies for the frozen MAX baseline

Kristján's farm session sent the frozen request with his key on Saturday evening, from 22:24, and committed all nine replies as the baseline's `replies/` ($6.19; [his note](max-map-claude-check.md)). Manh's key had sent the same request at 22:11 to 22:20. Those six replies are kept beside them, unchanged, as [`replies-manh/`](lightlag-runs/max-baseline/replies-manh/), with [`asks-manh.jsonl`](lightlag-runs/max-baseline/asks-manh.jsonl) and their sandbox scores in [`plays-manh.json`](lightlag-runs/max-baseline/plays-manh.json). Both sets follow the frozen protocol; they are independent samples.

| Program, MAX map | Fair (500, 510, 520) | Superhard (505, 509, 515) | World 2026 |
|---|---:|---:|---:|
| `manh_max` | 0.487 | 0.158 | 0.431 |
| Opus 1, Manh's key | 0.490 | 0.107 | 0.168 |
| Opus 1 / 2 / 3, Kristján's key | 0.479 / 0.295 / 0.439 | 0.178 / 0.106 / 0.270 | 0.207 / 0.153 / 0.297 |
| Sonnet 1 / 2 / 3, Manh's key | 0.219 / 0.098 / 0.116 | 0.116 / 0.097 / 0.055 | 0.209 / 0.052 / 0.060 |
| Sonnet 1 / 2 / 3, Kristján's key | 0.043 / 0.082 / 0.148 | 0.070 / 0.061 / 0.011 | 0.078 / 0.055 / 0.000 |
| Haiku 1 / 2, Manh's key | 0.051 / 0.055 | 0.045 / 0.029 | 0.039 / 0.000 |
| Haiku 1 / 2 / 3, Kristján's key | 0.086 / 0.039 / 0.020 | 0.052 / 0.033 / 0.026 | 0.045 / 0.009 / 0.058 |

Campaign scores (value earned over value available in the three worlds). Manh's set was played in the bubblewrap sandbox here, Kristján's on Modal by the farm.

**Spend on Manh's key:** $2.80 recorded for the six replies. Four further calls (Opus 2 and Haiku 3, twice each) were cut off when the run was stopped and left no reply; their cost is not recorded, at most about $5.35 if billed in full. No more calls are planned on this key: the farm session has completed the baseline's nine replies.

## 4. Why Opus looks closer on the MAX map

Manh's follow-up: the MAX map is the same ground with harder rules, so why is Claude level with `manh_max` there when the reference is far ahead of Claude on the normal map?

**Mostly because the two comparisons used different Claude programs.** The normal-map figure (0.321 against 0.502) is one older one-request program. The MAX figures are the four programs written from the frozen MAX request. Those four were played here on the normal map as well, in the sandbox, on 30 fresh worlds the farm had used on both maps ([`opus_on_both_maps.py`](../tools/second_machine_check/opus_on_both_maps.py); rows in [`opus-both-maps.jsonl`](second-machine-check/opus-both-maps.jsonl), table in [`opus-both-maps-table.json`](second-machine-check/opus-both-maps-table.json)). They are much better programs on either map.

| Player, worlds 600 to 629 | Normal map | MAX map | Kept on the MAX map |
|---|---:|---:|---:|
| Reference pilot (normal) / `manh_max` (MAX) | 0.500 | 0.306 | 61% |
| Opus 1, Manh's key | 0.453, 91% of the reference | 0.251, 82% of `manh_max` | 56% |
| Opus 1, Kristján's key | 0.439, 88% | 0.308, 101% | 70% |
| Opus 3, Kristján's key | 0.385, 77% | 0.305, 100% | 79% |
| Opus 2, Kristján's key | 0.342, 68% | 0.211, 69% | 62% |
| The four together | 0.405, 81% | 0.269, 88% | 66% |
| Older Opus one-request program | 0.326, 65% | not played | |

- **The same programs on both maps get 81% of the designated controller on the normal map and 88% on the MAX map.** A small narrowing, and not for every program: two gain, one stays, one loses.
- **The MAX rules cost every player about a third.** `manh_max` keeps 61% of what the reference scores on the same worlds; the four programs keep 56 to 79%. The ground and the targets are the same, but nine more rules make it another game.
- **What changes most is the noise.** On the normal map the reference's lead is steady: its own score varies by 0.046 from world to world, and the four programs are higher on 2 of 120 world-plays. On the MAX map the difference between two players swings by about 0.15 a world, so a level average means each wins about half: the programs are higher on 47 of 120.
- **Each side loses differently on the MAX map.** `manh_max` ends away from the lander on 17 of 100 fresh worlds; the reference never does on the normal map. On world 2028 it stopped 6.8 m from the lander (radius 4 m) with 6.1 battery left, waiting for the sun: the missing `home_floor` rule. Opus 1 (Kristján's key) loops on slip stops instead: 9.1 a mission against 2.0, and on worlds 2028 and 2029 its 24 and 40 stops threw away 137 and 249 queued commands.
- **Why the reference's edge shrinks is only partly shown.** On the normal map Claude's programs drive as far as the reference and take nearly as many samples (18.6 to 23.6 a mission against 24.4), but of less value: on world 600, 20 to 26 samples for 49.5 to 58.2 points, where the reference takes 25 for 65. On the MAX map `manh_max` takes 16.3 samples a mission and the programs 12.6 to 18.1. Which MAX rule costs Claude's programs most was not measured.
- **Why the four are better than the older program is not established.** The instruction text is the same. The MAX request adds one section and one example, and the replies are about half as long again (73,000 to 88,000 output tokens against 50,000). It is one older sample against four.

**The same four programs on Kristján's own worlds**, each world as a single mission ([rows](second-machine-check/opus-judged-worlds.json)):

| | World 2026 | Campaign 2027 to 2029 |
|---|---:|---:|
| **Normal map:** reference pilot | 0.565 | 0.476 |
| Opus 1, Manh's key | 0.539 | **0.474** |
| Opus 1 / 3 / 2, Kristján's key | 0.500 / 0.450 / 0.147 | 0.409 / 0.342 / 0.267 |
| Best live agent run | 0.528 | 0.293 |
| **MAX map:** `manh_max` | 0.431 | 0.235 |
| Opus 3 / 1 / 2, Kristján's key | 0.297 / 0.284 / 0.153 | 0.279 / 0.133 / 0.187 |
| Opus 1, Manh's key | 0.168 | 0.194 |

- **One one-request program all but ties the reference on the judged worlds.** Manh's-key Opus 1 scores 0.418, 0.490 and 0.513 at the three sites: 169.75 points of 358 against the reference's 170.5. Three runs here gave the same score, and each mission plays again from its command log. On 30 fresh worlds the same program is 0.047 behind and ahead on 2, so these three worlds suit it; but a live agent that wrote such a program would be at the reference's level on the task as judged.
- **On the MAX map, Opus 3 beats `manh_max` on these worlds too:** 0.279 against 0.235, home at all three sites.
- **Three of the four programs plan against the wall clock,** so their scores shift with the machine. Opus 1 (Kristján's key) scores 0.284 on world 2026 on the MAX map here and 0.207 on Modal; the other three repeat the farm's or the earlier sandbox scores there. The missions here ran 16 to 20 at a time on 20 cores.

## Limits

- **One second machine.** Linux x86-64 with Docker 29.1. The judges' machines are not known.
- **No model run here.** Everything above the reference and do-nothing runs relies on saved runs and saved programs.
- **The outperformance rates describe saved programs,** replayed without their agents. A live agent can watch and fix its program; on the normal map that did not help (the one-request Opus program, 0.362 on the campaign's worlds, is above every live run).
- **Random three-world groups are drawn from 300 (or 100) worlds,** so they overlap; the percentages are estimates.
- **Section 4 rests on 30 worlds** and on programs whose planning depends on the clock; the farm's 100-world rows are the steadier record for the MAX map.
- **`manh_max` on the MAX map was tuned on development worlds 1 to 24** and picked the baseline worlds by its own score; fresh worlds 600 to 699 are the fair comparison.

## Rerun

```sh
python3 -m unittest discover -s tests/second_machine_check -v           # 7 tests, seconds
python3 tools/second_machine_check/verify_replays.py                    # every saved run from its commands: 20 s
python3 tools/second_machine_check/outperform.py                        # the two tables above, from the farm's rows
python3 tools/second_machine_check/opus_on_both_maps.py table           # section 4's tables, from the saved rows
python3 tools/second_machine_check/kristjans_worlds.py /tmp/kworlds     # manh_max and the pilot on 2026-2029: 6 minutes
harbor run -p harbor/lightlag-traverse-campaign -a oracle -y            # 0.476257 (needs Docker)
```
