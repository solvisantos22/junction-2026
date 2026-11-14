# Lightlag biomes: choose where on Mars the mission runs

**Status: a sandbox option, not a rules decision.** Nothing in the frozen task, the reference, the Harbor package or the main demo changes. Owner: Manh / Claude Code (see `TEAM_STATUS.md`). Built Saturday 14 November, about 12:20–13:10 Helsinki.

**Scripted controllers only. No model has played any biome**, so nothing here says how an agent would do in one.

## What it is

A biome is a named setting of the dynamic environment. You choose one; the mission profile (`rush`, `rush_noisy`, ...), seed and delay work as before.

- **`main_mars` is today's environment, unchanged, and the default.** A test checks that its rules, map, telemetry and replay are identical to `DynamicEnvironment` for the same seed, profile and delay.
- **Six more biomes**, each named after a place or routine where a real Mars rover got stuck, damaged or slowed. They come from the terrain-unit brainstorm (Manh's notes, 14 November) and from the Mars-operations sandbox already in `manh_controllers/`.
- Every biome follows the same three rules as that brainstorm:
  1. It changes published parameters only. It adds no new physical system; the delay, battery, slip and safety-stop rules stay the team's.
  2. Its rule is in `rules()["biome"]`, its numbers are in `rules()`, and its areas are in `map()`.
  3. Whatever the seed hides inside the published ranges shows up in telemetry.

```sh
python3 -m lightlag_dynamic.biomes --list                                     # the biomes, their rules and settings
python3 -m lightlag_dynamic.biomes --biome troy_crust --profile rush_noisy --seed 7 --delay 3 < script.jsonl
python3 -m lightlag_dynamic.biomes.serve --biome relay_pass --profile rush --seed 7 --delay 3   # over MCP
python3 -m lightlag_dynamic.biomes.trial --seeds 2000-2039                    # the early test below (needs numpy)
python3 -m unittest tests.lightlag_dynamic.test_biomes                        # 24 tests, about 6 seconds
```

In Python: `make_biome_env("troy_crust", seed=7, delay=3, profile="rush_noisy")`. Biomes mix with `+`, for example `troy_crust+relay_pass`. `gale_rock_field+hidden_valley` is refused, because the rough-ground drive loop does not run the onboard slip check.

The JSON-lines runner and the MCP entry take the same options as `python3 -m lightlag_dynamic` and `python3 -m lightlag_dynamic.serve`, plus `--biome` (or `LIGHTLAG_BIOME`). They are separate modules, so the files the Harbor experiments copy and hash are untouched, and nothing under `harbor/` uses them.

## The biomes

| Biome | Kind | Modelled on | What changes | The decision it creates | Default settings |
|---|---|---|---|---|---|
| `main_mars` **Main Mars** | main | The team's current environment | Nothing | The mission itself | none |
| `relay_pass` **Relay Pass Schedule** | situation | Orbiter relay passes: rovers exchange most data through orbiters a few times per sol | The link is open 4 ticks in every 8. An uplink sent between passes is stored and transmitted when the next pass opens. Telemetry that would arrive between passes arrives when the next pass opens, and `map()` lists a discovery from then | What to queue before the pass closes | period 8, open 4 |
| `hidden_valley` **Hidden Valley** | situation | Curiosity backing out of the sand of Hidden Valley (2014) after slipping more than planned | Onboard fault protection: a drive step that slips more than the limit stops the drive and discards every queued command | Cross the sand and risk a stop, or go around | limit 0.40 on missions under 60 ticks, 0.45 on longer ones |
| `bagnold_dunes` **Bagnold Dunes** | terrain | Curiosity at the Bagnold Dunes (2015–16); Opportunity stuck about five weeks in Purgatory Dune (2005) | Every sand patch is cut into dune faces about 2 m wide, each with a slope in `map()`. On a face, slip = sand coefficient + slip per degree × slope. The slip per degree is a second hidden value per seed | Measure slip at two slopes before trusting a steep face | slopes 0–20°, slip per degree 0.01–0.03, no extra dune fields |
| `troy_crust` **Troy Crust** | terrain | Spirit breaking through a crust into soft sand at Troy (2009), where its mission ended | `map()` lists crust regions, mapped as bedrock. Each 1 m cell inside is soft sand underneath with the published probability. A soft cell behaves like sand, and the telemetry terrain field reads sand while the rover is on one | Probe the edge of a crust region, or route around it | 2 regions of 5–8 m, 10% of cells soft |
| `gale_rock_field` **Gale Rock Field** | terrain | The punctures sharp rocks tore in Curiosity's wheels (2013) | `map()` lists rock fields and their rough cells. A rough cell jolts the rover and can spin its wheels (the existing bumpy-ground rule), and adds one to `wheel_wear`, reported in every packet. Past the wear budget a drive covers at most 2.5 m | Straight across the rocks, or a longer smooth route | 2 fields of 5–8 m, 30% of cells rough, budget 4 cells |
| `meridiani_ripples` **Meridiani Ripple Plains** | terrain | Opportunity's long drives across the sand ripples of Meridiani Planum | Visual odometry is noisier on sand, published per terrain. The sensing model of the noisy profiles is on, also on `rush` | Take extra measurements where the sensor is weak | odometry noise 3% on bedrock, 20% on sand |

**Where each mechanic comes from in the code:**
- Relay Pass, Hidden Valley and Meridiani are the existing `windows`, `slip_check` and `vo_by_terrain` factors of `manh_controllers/scenarios.py` and `mars.py`. Relay Pass also holds telemetry back to the next pass.
- Gale Rock Field is the existing bumpy-ground option, with the rough cells placed inside rock fields instead of scattered over the whole map, plus the wear rule.
- Troy Crust and Bagnold Dunes are new. Troy Crust is the published version of the lab's unpublished `hidden_patches` factor: the regions and the rate are now in `map()` and `rules()`.
- Crust regions and rock fields are placed across the straight line from the base to a target known at launch (35–65% of the way), at least 1.5 m from the base. That placement rule is published too.

**A name to keep apart:** the main demo's "Rocks" mission calls the map's hazards rock fields: drive into one and the rover stops. The rock fields of `gale_rock_field` are different ground. The rover can drive through them, at the price of jolts, spins and wheel wear.

## How the settings were chosen

On development seeds 0–19, delay 3, `rush` and `rush_noisy`, with ten controllers (1, 19, 24, 26, 27, 28, 33, `blind`, `cautious`, `solvi_reference`). On Main Mars the best of them scored 75.2%.

**Keep rule, written down before the sweep:** candidates are ordered mild to strong. Keep the strongest one at which the best controller still scores at least 85% of its own Main Mars share and gets home in at least 95% of episodes. If none passes, keep the mildest and say so. Hidden Valley and Meridiani keep the values the lab had already tested.

| Biome | Candidates, mild to strong: best controller's share (share of its Main Mars score) | Kept |
|---|---|---|
| Relay Pass (period / open) | 4/2: 72.2% (96%) · 6/3: 63.0% (84%, fail) · 8/4: 68.7% (91%) · 6/2 and 10/3: the fixed plan is the best controller · 8/3: 58.7% (78%, fail) | **8 / 4** |
| Troy Crust (regions / soft rate) | 1 / 10%: 72.9% (98%) · 2 / 10%: 64.4% (87%) · 1 / 20%: 62.0% (83%, fail) · 2 / 20%: 52.7% (fail) · 2 / 35%: 41.9% (fail) | **2 / 10%** |
| Gale Rock Field (rough share / wear budget) | 30% / 8: 67.5% (90%) · 30% / 4: 66.4% (89%) · 50% / 8: 62.4% (83%, fail) · 50% / 4: 59.3% (fail) | **30% / 4** |
| Bagnold Dunes | With one or two extra dune fields of 5–8 m across the routes, at slopes up to 12° or 20°: 39.9–52.1%, all fail | see below |

Two things did not go as planned, and both are stated here rather than hidden:

- **Relay Pass: the rule needed one addition after the sweep.** At 6/2 and 10/3 the best "controller" is `blind`, the fixed plan, which the link does not touch. It passes the rule as written, but a biome in which a fixed plan beats every feedback controller defeats its purpose. Those two candidates were set aside, which leaves 8/4 as the strongest that passes.
- **Bagnold Dunes: none of the four candidates passed, so milder ones were added.**
  - An ablation showed why: a plain sand field of the same size, with no slope rule at all, already brings the best controller to 56.5% (79% of Main Mars). The cost is the extra sand, not the dunes.
  - A smaller extra field (3–5 m) with slopes up to 12° scored 62.2% (84%), one point short.
  - With no extra field, the slope rule on the map's own sand passes: 74.9% at slopes up to 12°, and 72.2% (96%) at slopes up to 20° with a steeper slip per degree. That last one is the default.
  - An extra dune field is still available as a setting (`fields`, `field_size_m`).

**A limit of this keep rule:** it compares with the Main Mars score, so it also counts against a biome that merely lowers what any player can reach, such as more sand on the map. The honest yardstick would be a bound that knows the biome, and there is none yet.

**The defaults are mild on purpose.** Stronger settings break today's controllers: at a 35% soft rate, the controllers that trust the map die in 35–40% of episodes.

## Early test: which controller does best

**Setup:**
- Seeds 2000–2039, which nobody had used; `rush` and `rush_noisy`; delays 0, 3 and 5.
- Every registered Manh controller (1–36), bound 16, and the team's `solvi_reference`, `kristjan_reference`, `blind` (a fixed plan) and `cautious` (leg-and-wait), all unchanged: 33 players, 55,440 episodes.
- Share = score / maximum available. A biome's number is the mean over both profiles, the three delays and the 40 seeds (240 episodes). "Overall" weighs every biome equally.
- Full tables per biome, profile and delay: [trial report](lightlag-biomes/trial-report.md). Numbers per controller: [trial summary](lightlag-biomes/trial-summary.json). Result rows are not committed; the command above reproduces them in about 20 minutes on 10 workers.
- **Run in two parts.** Controllers 1–34 were played on Saturday about 12:40 Helsinki; 35 and 36 were registered afterwards and were played on the same seeds about 14:00. The whole trial was then replayed on the final code (`0854b48`): all 55,440 episodes came out identical.

### Best overall: controller 36, narrowly ahead of 33

| Rank | Controller | All biomes | Main Mars | Relay Pass | Hidden Valley | Bagnold Dunes | Troy Crust | Gale Rock Field | Meridiani |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **36** (everything that worked, in one controller) | **75.2%** | 78.9% | 74.4% | 77.6% | 76.7% | 71.9% | 72.8% | 74.3% |
| 2 | 33 (24 + slip-check layer + executive) | 74.9% | 78.7% | 74.1% | 77.4% | 76.0% | 71.8% | 72.0% | 74.1% |
| 3 | 31 (24 + slip-check layer) | 74.8% | 78.7% | 74.1% | 76.7% | 76.0% | 71.8% | 72.0% | 74.1% |
| 4 | 34 (27, guard only when a probe is free) | 74.7% | 78.6% | 74.1% | 75.4% | 76.4% | 72.1% | 72.3% | 74.1% |
| 5 | 26 (24 + Bayesian sand pricing) | 74.7% | 78.6% | 74.1% | 75.4% | 76.0% | 72.3% | 72.1% | 74.0% |
| 6–11 | 22, 24, 25, 19, 23, 35 | 74.6% | 78.7% | 74.1% | 75.6% | 76.0–76.1% | 71.5–71.8% | 72.0% | 74.1% |
| 12 | 20 (cubature filter) | 74.5% | 78.7% | 74.2% | 75.6% | 76.0% | 71.2% | 72.0% | 73.7% |
| 18 | 27 (guarded moves always) | 73.2% | 77.0% | 72.5% | 74.0% | 74.9% | 70.7% | 70.2% | 72.8% |
| 22 | 1, `kf_mpc`, the frozen reference | 73.0% | 77.3% | 69.0% | 74.5% | 74.4% | 71.2% | 70.9% | 73.8% |
| 29 | `blind`, fixed plan | 55.0% | 59.4% | 59.4% | 57.2% | 55.1% | 53.0% | 43.8% | 56.7% |
| 30 | `cautious`, leg-and-wait | 42.0% | 46.0% | 44.8% | 44.0% | 45.5% | 42.7% | 42.5% | 28.8% |
| 31 | `solvi_reference` | 41.0% | 43.8% | 37.6% | 42.3% | 43.7% | 41.9% | 40.7% | 37.0% |
| 32 | `kristjan_reference` | 41.0% | 44.8% | 43.9% | 43.2% | 43.7% | 41.1% | 41.2% | 28.8% |

Paired by episode, in points of share, with a 95% bootstrap over seeds:

| Comparison, all biomes | Difference |
|---|---|
| 36 against `kf_mpc` | **+2.2 (+1.4 to +3.2)** |
| 36 against 33 | +0.4 (+0.1 to +0.7) |
| 36 against 24 | +0.6 (+0.1 to +1.2) |
| 33 against 24 | +0.3 (−0.1 to +0.7) |
| 35 against 24 | 0.0 (−0.1 to 0.0) |
| 34 against 24 | +0.1 (−0.1 to +0.3) |
| 27 against 24 | −1.4 (−2.1 to −0.7) |
| 24 against `kf_mpc` | +1.6 (+0.9 to +2.3) |

- **Controller 36 is the best overall.** It is 34 (guarded moves only when a probe is free) on the real-time-aware base of 29, under the slip-check layer and executive of 33, with the rules read once and a smaller energy reserve until the battery shows unmapped sand. It is first or level with the first in every biome but Troy Crust, where 26 is 0.4 points ahead.
- **Its lead over 33 is small but not noise:** +0.4 points over all biomes (+0.1 to +0.7). It comes from Gale Rock Field (+0.8, +0.3 to +1.5) and Bagnold Dunes (+0.7, +0.1 to +1.3); in the other five biomes the two are within noise.
- **33 was the best of controllers 1–34**, and is controller 24 everywhere except Hidden Valley. The 24 family (19, 22–26, 31, 33–35) lies within 0.3 points of each other.
- **The lead over the frozen reference is real: +2.2 points.** By biome it is +5.4 on Relay Pass (+3.8 to +7.2), +3.1 on Hidden Valley (+0.8 to +6.2), +2.3 on Bagnold Dunes, +2.0 on Gale Rock Field, +1.6 on Main Mars, +0.7 on Troy Crust and +0.5 on Meridiani; the last two intervals include zero.
- **`kf_mpc` is not aware of relay passes.** That is the whole Relay Pass gap: it plans as if an uplink left at once. It never stopped with an error at 8/4, though; only `solvi_reference` did, in 4 episodes.
- **In Hidden Valley the slip-check layer shows:** at delay 3, 36 and 33 are stopped 0.3 times per episode and always get home; 24 is stopped 0.6 times and gets home in 92% of episodes.
- **27's guarded moves cost 1.4 points here too**, as on the plain profiles. 34 and 36 remove that cost.
- **35 equals 24 here.** Its additions answer lost packets and outlier fixes, which no biome has.

### Best controller in each biome

| Biome | Best | Its share | 36 | `kf_mpc` | Fixed plan | Leg-and-wait |
|---|---|---|---|---|---|---|
| Main Mars | **36** | 78.9% | 78.9% | 77.3% | 59.4% | 46.0% |
| Relay Pass Schedule | **36** | 74.4% | 74.4% | 69.0% | 59.4% | 44.8% |
| Hidden Valley | **36** | 77.6% | 77.6% | 74.5% | 57.2% | 44.0% |
| Bagnold Dunes | **36** | 76.7% | 76.7% | 74.4% | 55.1% | 45.5% |
| Troy Crust | 26 | 72.3% | 71.9% | 71.2% | 53.0% | 42.7% |
| Gale Rock Field | **36** | 72.8% | 72.8% | 70.9% | 43.8% | 42.5% |
| Meridiani Ripple Plains | **36** (10 and 21 tie) | 74.3% | 74.3% | 73.8% | 56.7% | 28.8% |

### What each biome costs, and whether the cost grows with the delay

Controller 36's share by delay, and the difference from Main Mars at the same delay:

| Biome | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| Main Mars | 89.4% | 79.2% | 68.1% |
| Relay Pass Schedule | 88.2% (−1.2) | 73.2% (−6.0) | 61.9% (−6.1) |
| Hidden Valley | 89.6% (+0.2) | 78.1% (−1.1) | 65.1% (−3.0) |
| Bagnold Dunes | 87.6% (−1.8) | 76.5% (−2.7) | 66.0% (−2.1) |
| Troy Crust | 83.7% (−5.8) | 71.4% (−7.8) | 60.6% (−7.4) |
| Gale Rock Field | 86.7% (−2.8) | 71.4% (−7.8) | 60.5% (−7.6) |

- **Every biome costs more at delay 3 than at delay 0.** That is the pattern the brainstorm asked for: the difficulty should come from the delay, not from the terrain alone. It is shown here for a scripted controller only; the same test with a model has not been run.
- **Fixed plans pay most on rough ground.** `blind` loses 15.6 points in Gale Rock Field, where spins throw a plan off that never reads telemetry, and gets home in 64% of episodes. It loses 6.4 in Troy Crust and nothing in Relay Pass, since its whole plan leaves at tick 0, inside a pass.
- **Leg-and-wait pays most under relay passes, once there is a delay:** 43.1% against 50.2% on Main Mars at delay 3, and 25.8% against 34.3% at delay 5.
- **Meridiani Ripple Plains is, in practice, `rush_noisy`.** It switches the sensing noise on for `rush`, so both profiles become the same episode, and its row in the tables above reflects that noise. Against Main Mars on `rush_noisy` alone, controller 36 scores 88.2 / 72.6 / 61.9% against 88.2 / 73.4 / 61.9%: the noisier odometry on sand changes less than a point. As a biome it is nearly inert with today's controllers.

## Are the biomes hard enough? Not at the default settings

*Added Saturday about 14:30 Helsinki, after Manh's remark that the results look too easy.*

**The remark is right, and the reason is the keep rule above.** It kept a setting only if controllers that never read the biome's rule still scored at least 85% of their Main Mars score. So at the defaults a player can ignore the biome and lose 2 to 7 points. A biome like that cannot be what breaks a capable agent: the agent plays Main Mars with a small tax.

**And on most maps the biome is not even in play.** At delay 3, on 80 maps per biome (40 seeds on each of the two profiles), from the trial above:

| Biome | Maps where `kf_mpc` scores as on Main Mars (within 0.02) | Maps where it loses 0.25 or more | Maps where 36 beats it by 0.25 or more |
|---|---|---|---|
| Relay Pass Schedule | 23 | 8 | 4 |
| Hidden Valley | 73 | 6 | 3 |
| Bagnold Dunes | 66 | 7 | 4 |
| Troy Crust | 59 | 10 | 5 |
| Gale Rock Field | 29 | 10 | 2 |
| Meridiani Ripple Plains | 53 | 6 | 0 |

- **The small averages hide two different things.** On most maps the rover never meets the biome's area and nothing changes. On a few the biome decides the mission: in Hidden Valley on `rush` seed 2000, controller 36 scores 0.59 more than `kf_mpc`; in Troy Crust on `rush_noisy` seed 2024, 0.64 more.
- **So there are two roads to a hard task, not one.** Turn the dial up, which is the probe below. Or keep the dial and choose maps on which the biome is in play, as the main demo's missions were chosen for their maps and as `manh_controllers/seeds.py` already does for the plain profiles. The second road needs no new controller.

**What a hard setting has to do.** By the brainstorm's own rule, a biome earns its place when play that ignores the published rule loses a lot, while a controller that models the rule keeps its score. That needs a rule-aware reference, and today only one biome has one: Hidden Valley, through the slip-check layer and executive in controllers 33 and 36.

**Probe** on unused seeds 2100–2139, delay 3, 40 seeds per cell; share, and rovers home:

| Hidden Valley on `noisy` (80 ticks) | Main Mars | Slip limit 0.40 | 0.35 | 0.30 |
|---|---|---|---|---|
| 36, models the rule | 93.1%, 100% | 88.8%, 100% | 80.6%, 100% | 79.4%, 100% |
| 33, models the rule | 91.9%, 100% | 87.5%, 100% | 79.4%, 98% | 78.8%, 100% |
| 24, ignores it | 91.9%, 100% | 75.9%, 82% | 58.8%, 65% | 33.8%, 35% |
| `kf_mpc`, ignores it | 90.6%, 100% | 75.9%, 82% | 58.1%, 65% | 33.1%, 35% |
| `blind`, fixed plan | 67.2%, 78% | 60.9%, 72% | 42.8%, 52% | 17.5%, 22% |
| `solvi_reference`, never drives on sand | 75.0%, 100% | 75.0%, 100% | 75.0%, 100% | 75.0%, 100% |

- **On the 80-tick map the dial works.** At a slip limit of 0.30 the controllers that model the rule keep about 79% and always get home. `kf_mpc` and 24 fall from about 91% to 33%, stopped 7.5 times per episode. That is a 46-point gap between reading the rule and ignoring it, and the rule is one published line.
- **It punishes ignoring the rule, not a lack of cleverness.** A plan that simply never drives on sand scores 75%, four points below the best. An agent that reads the rule and keeps off the sand loses little.
- **The frozen reference would have to change.** `kf_mpc` is one of the players that collapses, so a graded Hidden Valley would need 33 or 36 as its reference.
- **On the 50-tick rush maps the same dial does almost nothing.** At 0.30, 36 scores 67.0% and 24 scores 64.3%, against about 74% on Main Mars: sand is rarely on the way, and a stop leaves no time to recover.
- **Putting sand on the way does not fix that.** A dune field across the routes together with the slip check brings everyone down together: with one field and a limit of 0.40, 36 scores 43%, 24 scores 39% and `kf_mpc` 37%. That lowers what any player can reach; it does not separate reading the rule from ignoring it. No controller models the dune slope yet.

**So a hard tier exists today for one biome on one profile** (Hidden Valley, `noisy`, slip limit 0.30 to 0.35), and it is a proposal, not a setting: nothing in the catalog has changed. For the other biomes the dials are there (the sweep above shows what breaks), but each needs a controller that models its rule before a hard setting can be called fair.

**What this still does not show:** how a model plays any of it. The team's own model runs point at energy and command-queue bookkeeping under delay as where Claude loses points. Events that drop or cut the queue (a slip stop, a closed link, a worn wheel) press on exactly that, so the hard settings may cost an agent more than they cost a scripted controller. Only a model run can say.

## No GPS: a prototype where the position has to be worked out

*Added Saturday about 15:40 Helsinki, at Manh's suggestion. A sandbox prototype: not in the catalog, the trial or the demo page, and not a rules decision. Scripted players only.*

```sh
python3 -m lightlag_dynamic.biomes.nogps_players --seeds 0-19                 # every player, about 5 seconds (needs numpy)
python3 -m lightlag_dynamic.biomes.nogps_players --seeds 0-19 --weak-gps      # the same with a very noisy GPS kept
python3 -m lightlag_dynamic.biomes --no-gps --profile rush_noisy --seed 7 --delay 3 < script.jsonl
python3 -m lightlag_dynamic.biomes.serve --no-gps --profile rush_noisy --seed 7 --delay 3    # over MCP
python3 -m unittest tests.lightlag_dynamic.test_nogps                         # 12 tests, about 8 seconds
```

### Why taking the position away is not enough

Today every telemetry packet carries an absolute position fix: exact on `rush`, within 0.3 m on the noisy profiles. It is GPS in all but name, and Mars has none. With a fix every tick nothing makes a player combine sensors.

A probe on seeds 2100–2139 (`rush_noisy`, delay 3), with the fix made worse and the hidden heading bias made wider, through the `sensing` dials of `scenarios.make_env`:

| Player | ±5° bias, 0.3 m fix (today) | ±5°, 4 m fix | ±15° bias, 0.3 m fix | ±15°, 2 m fix |
|---|---|---|---|---|
| Fusing filter (controller 36) | 74% | 61% | 63% | 27% |
| The same filter, believing there is no bias | 73% | 69% | 34% | 28% |
| Fixed plan, never reads telemetry | 54% | 54% | 25% | 25% |
| Re-plans from each fix as if exact | 17% | 0% | 4% | 0% |
| Leg-and-wait | 38% | 8% | 21% | 6% |

- **A useless fix alone does not force fusion.** With the published ±5° bias and short legs, dead reckoning stays inside the 0.75 m target radius. The filter that ignores the bias even beats the full one.
- **A wider bias with today's fix does:** 63% against 34% and 25%.
- **Both together are too hard for everyone.** With no usable fix the bias cannot be observed, and the filter waits.
- So fusion is needed only when each sensor alone is not enough and together they are. That is what the prototype is built to be.

### What the rover senses instead

After the launch briefing the `position` field is null. Everything below is published in `rules()["navigation"]`.

| Reading | When | What it is | Why it is not enough alone |
|---|---|---|---|
| `wheel_odometry`, `visual_odometry` | every drive | Wheel metres, and ground metres within 5% | The commanded heading is off by a hidden bias of up to ±15° that drifts |
| `sun_heading_deg` | every drive | The heading really driven, within 6° (a sun compass) | One reading is too coarse to steer by |
| `beacon_range_m` | every tick | Distance to the lander's beacon at the base, within 0.25 m | A ring around the base, not a point |
| `terrain`, battery, sample results | as today | Unchanged | Occasional |

The evaluator's truth, the scoring and the replay's states use the true position, as always: a player that never reads telemetry drives the identical episode with and without the fix (tested). The option sits on any biome: `make_nogps_env(seed, delay, profile, biome="troy_crust")`.

### The fusing reference

`fused` in `nogps_players.py` is the Manh controllers' particle-filter controller (the planner of controller 21) with one more likelihood per new reading: the beacon range weighs each particle by how well its distance from the base fits, the sun compass weighs the heading each particle itself drove, and the terrain reading is matched against the published map. A range is a ring and a terrain reading is a region, which a particle filter can weigh as they are and a Kalman filter's Gaussian cannot. 1,000 particles; the planner is unchanged and plans on the filter's mean and covariance.

The other players stand for what a player without that filter might do:

| Player | What it does |
|---|---|
| `fused_no_range`, `fused_no_compass`, `fused_no_terrain` | The reference with one reading ignored |
| `odometry_only` | The reference with all three ignored: wheels, cameras and sample results |
| `dr_mean_compass` | `kf_mpc` fed a position dead-reckoned from the commanded heading plus the average compass error so far: the simplest fusion there is, about ten lines |
| `dr_compass` | `kf_mpc` fed a position dead-reckoned from each raw compass reading |
| `dr_commanded` | `kf_mpc` fed a position dead-reckoned from the commanded headings |
| `blind` | Plans once from the briefing and never reads telemetry |

### Result on unused seeds

Seeds 2200–2239, one run, with the settings above fixed before any episode was played. Share of the maximum, and rovers home:

| Player | `rush_noisy`, delay 0 | delay 3 | delay 5 | `noisy` (80 ticks), delay 3 |
|---|---|---|---|---|
| **`fused`** | **84%**, 100% | **56%**, 100% | **34%**, 100% | **76%**, 100% |
| `fused_no_range` | 81%, 98% | 51%, 92% | 33%, 100% | 78%, 100% |
| `fused_no_terrain` | 84%, 100% | 56%, 100% | 34%, 100% | 78%, 100% |
| `fused_no_compass` | 51%, 98% | 27%, 100% | 14%, 100% | 52%, 100% |
| `odometry_only` | 49%, 98% | 24%, 100% | 14%, 100% | 44%, 98% |
| `dr_mean_compass` | 55%, 62% | 37%, 50% | 28%, 52% | 47%, 68% |
| `dr_compass` | 36%, 22% | 29%, 25% | 23%, 30% | 35%, 32% |
| `dr_commanded` | 35%, 75% | 24%, 60% | 20%, 65% | 26%, 70% |
| `blind` | 31%, 82% | 28%, 85% | 30%, 85% | 31%, 68% |
| With today's fix: controller 36 | 88%, 100% | 69%, 100% | 57%, 100% | 96%, 100% |
| With today's fix: `kf_mpc` | 87%, 100% | 70%, 100% | 55%, 98% | 90%, 100% |

- **Fusing is now what separates the players.** Paired over the three delays, `fused` is 17.7 points above the best player without a filter on `rush_noisy` (95% interval 14.1 to 21.6) and 25.8 above on `noisy` (19.8 to 31.7). It is 31 and 50 points above dead reckoning on the commanded headings.
- **Only the reference always gets home.** The dead-reckoning players end outside the base radius in a quarter to three quarters of episodes and lose half their score there. The beacon says how far the base is; they do not use it.
- **The cost of having no fix grows with the delay.** Against today's best player with a fix, `fused` gives up 4 points at delay 0, 13 at delay 3 and 23 at delay 5 on `rush_noisy`.
- **It is a two-sensor fusion so far, not a many-sensor one.** The compass carries it: without it the reference loses 27 and 25 points. The beacon adds 2.7 points on `rush_noisy` (1.0 to 4.8) and nothing measurable on `noisy`; the terrain reading adds nothing. A second beacon, or a compass coarse enough that the range has to help, would be the next dial.

**How the settings behave** (development seeds 0–19, `rush_noisy`, delay 3; `fused` against `dr_mean_compass`):

| Setting | `fused` | `dr_mean_compass` |
|---|---|---|
| Default: compass 6°, bias ±15° | 51% | 43% |
| Compass 2° | 61% | 59% |
| Compass 12° | 38% | 22% |
| Bias ±5° | 70% | 51% |
| Bias ±25° | 43% | 36% |

The beacon's noise (0.05 to 1 m) and the number of particles (300 to 3,000) change nothing beyond a point or two.

### With a very noisy GPS kept

*Added Saturday about 16:30 Helsinki, after Manh's point that a GPS may stay as long as it is very noisy next to the rest.*

`navigation=WEAK_GPS`, or `--weak-gps` on the runner, the MCP entry and the probe: the position fix is back in every packet with **2 m of noise per axis**, about seven times today's 0.3 m, and the compass is twice as coarse (**12°**). Both are published like everything else. The fix is then far too coarse to drive by and the compass too coarse to steer by.

**What is being fused, and what each sensor is worth to the reference.** Unused seeds 2300–2339, paired over delays 0, 3 and 5, points of share with a 95% interval; "worth" is what the reference loses when that one sensor is ignored:

| Sensor | What it tells the rover | Worth on `rush_noisy` | Worth on `noisy` |
|---|---|---|---|
| Wheel and visual odometry | How far each drive went | The backbone: every player here uses it | |
| Very noisy position fix, 2 m | Roughly where it is | +4.9 (+2.5 to +7.6) | +6.7 (+3.3 to +10.0) |
| Sun compass, 12° | Which way each drive really went | +5.9 (+3.6 to +8.3) | +4.8 (+2.1 to +7.5) |
| Beacon range, 0.25 m | How far the base is | −0.5 (−2.2 to +1.3) | +0.2 (−1.5 to +1.9) |
| Terrain under the rover | Bedrock or sand, against the map | 0.0 (−0.5 to +0.6) | +0.8 (0.0 to +2.1) |
| Sample results | A hit: within 0.75 m of that target; a miss: not | Built into every filter here | |
| Battery | Exact energy left | Not used by this reference | |

Share of the maximum, and rovers home, on the same seeds:

| Player | `rush_noisy`, delay 0 | delay 3 | delay 5 | `noisy` (80 ticks), delay 3 |
|---|---|---|---|---|
| **`fused`**: fix, compass, beacon, terrain | **84%**, 100% | **42%**, 98% | **23%**, 100% | **77%**, 100% |
| `fused_no_fix` | 81%, 100% | 33%, 95% | 20%, 100% | 67%, 100% |
| `fused_no_compass` | 80%, 100% | 34%, 100% | 18%, 100% | 76%, 100% |
| `fix_only`: particle filter on the fix and odometry | 76%, 98% | 30%, 95% | 16%, 100% | 76%, 100% |
| `kf_mpc_on_fix`: the frozen reference as it is | 66%, 95% | 26%, 100% | 12%, 95% | 72%, 100% |
| `trusts_fix`: takes each fix as exact | 0%, 0% | 1%, 0% | 1%, 0% | 0%, 0% |
| `dr_mean_compass`: averages the compass error | 28%, 42% | 22%, 42% | 15%, 22% | 26%, 35% |
| `blind` | 27%, 85% | 25%, 82% | 24%, 80% | 27%, 68% |
| With today's fix: controller 36 | 88%, 100% | 71%, 100% | 57%, 95% | 96%, 100% |

- **Two weak sensors are now fused with the odometry, and both count.** The fix is worth 5 to 7 points and the compass 5 to 6. Neither is enough alone.
- **Leaning on the fix alone falls short.** Paired over the delays, `fused` is 8.9 points above a particle filter on the fix alone on `rush_noisy` (6.4 to 11.4) and 5.7 on `noisy` (2.5 to 9.3). It is 15.2 and 11.1 above the frozen reference `kf_mpc`, which fuses the fix with odometry and nothing else.
- **Leaning on the compass alone falls further:** 28 and 47 points below.
- **Taking the fix at its word kills the rover** in about nine episodes in ten: it chases the noise until the battery is gone.
- **The beacon range is redundant here,** and so is the terrain reading. As a third sensor that counts, the beacon would need a partner: a second beacon, or a bearing.
- **The price is the reference's own score on the short missions.** On `rush_noisy` it falls from 71% with today's fix to 42% at delay 3 and 23% at delay 5. Fifty ticks are few for a filter to pin down a hidden bias from 2 m fixes. On the 80-tick map it keeps 74 to 77% at every delay.

**How the setting was chosen** (development seeds 0–19, `rush_noisy`, delay 3): a grid of compass noise 6°, 12° and 20° against fix noise 0.3, 1, 2, 3 and 5 m, looking for the cell where ignoring any one sensor costs the reference something and no single-sensor player comes within ten points of it.

| Compass 12°, fix noise | `fused` | `fused_no_fix` | `fused_no_compass` | `fix_only` | `kf_mpc_on_fix` |
|---|---|---|---|---|---|
| 0.3 m (today's) | 62% | 37% | 63% | 65% | 62% |
| 1 m | 54% | 37% | 48% | 46% | 46% |
| **2 m** | **45%** | 37% | 32% | 31% | 25% |
| 3 m | 40% | 37% | 29% | 26% | 17% |
| 5 m | 37% | 37% | 24% | 20% | 12% |

- At today's 0.3 m the fix alone is enough and the compass adds nothing.
- At 5 m the fix adds nothing.
- With the finer 6° compass the compass carries everything from 2 m up (53% against 51% without the fix).
- 2 m with a 12° compass is the cell where both matter.

### What it does not show

- **No model has played it.** Claude writes code, and averaging the compass error is ten lines that already reach 37–47%. A careful agent could write the particle filter too. What the prototype adds for certain is that reading the rover's position off a packet no longer works, and that the last drive home has to be checked against the beacon.
- **The tool descriptions still promise a position.** `lightlag_mcp/server.py` describes telemetry as it is today; it belongs to another owner and is unchanged. It has to say "no position" before any model run, or the run tests the wording.
- **The demo page cannot show it.** Its Earth view draws the reported position, which is null here.
- **The reference needs numpy**, like every Manh controller built on the particle filter, so it cannot run inside the Harbor task image as it is.
- **There is no bound** for this setting, so "56%" is the best known player, not the best possible.
- **Seeds:** 0–19 for the sensitivity tables and the grid, 2100–2139 for the probe, 2200–2239 for the no-GPS result, 2300–2339 for the weak-GPS result. All now used.

## Limits

- **No model has played a biome.** Whether a biome opens a gap between an agent and a reference is unknown.
- **No controller reads the new published areas.** Crust regions, rock fields and dune slopes are in `map()`, but every controller here only reacts to them through telemetry. The trial shows which existing controller is most robust, not how well a biome can be played. A controller that prices crust at its published rate, counts wheel wear, or fits the slope line should do better; none is built.
- **Bound 16 is not a bound in the biomes.** Its planner ignores their rules. On Relay Pass at delay 0 it scores below controller 36.
- **40 seeds, one draw each.** Differences under about one point are noise.
- **Mixed biomes** work and have one test; they were not part of the trial.
- **Seeds:** development 0–19 for the settings; 2000–2039 for the trial; 2100–2139 for the hard-setting and position probes; 2200–2239 and 2300–2339 for the no-GPS and weak-GPS results. All now used.

## Suggested next steps (not done)

1. Biome-aware layers for the 24 family, each inactive when its rule is absent: expected-cost pricing of crust at the published rate, a guard that only doubts ground inside crust regions, a wear count that shortens planned drives, a fit of the dune slope line.
2. With those, a second calibration: stronger settings should then pass the keep rule.
3. One model run in one biome at delay 0 and delay 3. This is the delay-relevance test with a real agent, it costs API credit, and it is a team decision.
4. A team decision on whether any biome ever joins a graded profile. The brainstorm's advice stands: at most one or two, Relay Pass first, and only after a model has played it.

## The biome edition of the 3D demo

**`viewer/biomes-demo.html`**: the 3D Mars demo with a row of biomes on its title screen. Open it by double-click, like the main demo. ← → choose a biome; the rest of the keys are the main demo's.

- **Main Mars** holds the main demo's own three missions (Deadlines, Sand, Rocks), with Claude's attempts and the reference, taken from `build_mars.gather()` unchanged.
- **Every other biome has one mission**, played when the page is built by four scripted controllers on the same map: controller 36 (best overall above), the frozen reference `kf_mpc`, the fixed plan and leg-and-wait. Keys 1–4 switch between them and M shows all four.
- **Drawn on top of the main demo's scenes:** crust regions and, on Mars and the map only, the soft cells the Earth picture cannot know; sharp-rock fields and their rough cells; dune faces shaded by slope, with the steep ones labelled; relay passes as a strip under the timeline; one line of biome status in the top right of each screen.
- **A slightly different Mars per biome.** Each biome shifts the main demo's own ground, sand, rocks, light, haze and sun a little, after the place it is modelled on, so the screen says which biome is playing: Relay Pass is late in the sol, cooler and dimmer; Hidden Valley a deeper rust; Bagnold Dunes has dark basalt sand; Troy Crust pale, bright soil; Gale Rock Field grey-purple ground and dark rock; Meridiani darker plains under a pale sky. Main Mars is left exactly as it is. A test keeps every shift small.
- **The seed of each mission** is the first of the trial's seeds (2000 upward) on which the biome's own mechanic actually happens, for example the reference standing on a soft cell. It is picked to show the mechanic, not as a typical result; the tables above are the typical result.

**Nothing of the main demo is edited.** `viewer/build_biomes.py` reads `viewer/mars/` as it is and adds one module, `viewer/biomes/addon.js`, which works through what the app already exposes. `viewer/mars-demo.html`, `viewer/mars/data.json`, `app.js`, `index.html` and `style.css` are not written; a test checks their hashes before and after a build.

```sh
python3 viewer/build_biomes.py                              # rebuilds viewer/biomes-demo.html, about 5 seconds
python3 -m unittest tests.viewer.test_build_biomes          # 12 tests, about 15 seconds
```

**Limits of the page:**
- The add-on leans on a few names inside the main demo's app (`window.LIGHTLAG`, the scene's groups, the title list). `AddOnContractTest` fails if one of them goes, which means the add-on must follow; the main demo itself is unaffected.
- The page embeds the main demo's app as it was when the page was built. After a change to the main demo, rebuild to pick it up.
- Checked in headless Firefox on Manh's laptop (title screen, every biome's mission, the compare view, no script errors). **Not checked in Chrome**, which is what the main demo was checked in.
