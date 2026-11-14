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
- Every registered Manh controller (1–34), bound 16, and the team's `solvi_reference`, `kristjan_reference`, `blind` (a fixed plan) and `cautious` (leg-and-wait), all unchanged: 31 players, 52,080 episodes.
- Share = score / maximum available. A biome's number is the mean over both profiles, the three delays and the 40 seeds (240 episodes). "Overall" weighs every biome equally.
- Full tables per biome, profile and delay: [trial report](lightlag-biomes/trial-report.md). Numbers per controller: [trial summary](lightlag-biomes/trial-summary.json). Result rows are not committed; the command above reproduces them in about 15 minutes on 10 workers.
- Controller 34 landed on `main` while the trial ran. Main Mars was played again on the final code; all 7,200 episodes of the other controllers came out identical.

### Best overall: controller 33, by a margin that is mostly noise

| Rank | Controller | All biomes | Main Mars | Relay Pass | Hidden Valley | Bagnold Dunes | Troy Crust | Gale Rock Field | Meridiani |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **33** (24 + slip-check layer + executive) | **74.9%** | 78.7% | 74.1% | 77.4% | 76.0% | 71.8% | 72.0% | 74.1% |
| 2 | 31 (24 + slip-check layer) | 74.8% | 78.7% | 74.1% | 76.7% | 76.0% | 71.8% | 72.0% | 74.1% |
| 3 | 34 (27, guard only when a probe is free) | 74.7% | 78.6% | 74.1% | 75.4% | 76.4% | 72.1% | 72.3% | 74.1% |
| 4 | 26 (24 + Bayesian sand pricing) | 74.7% | 78.6% | 74.1% | 75.4% | 76.0% | 72.3% | 72.1% | 74.0% |
| 5–9 | 22, 24, 25, 19, 23 | 74.6% | 78.7% | 74.1% | 75.6% | 76.0% | 71.6–71.8% | 72.0% | 74.1% |
| 10 | 20 (cubature filter) | 74.5% | 78.7% | 74.2% | 75.6% | 76.0% | 71.2% | 72.0% | 73.7% |
| 16 | 27 (guarded moves always) | 73.2% | 77.0% | 72.5% | 74.0% | 74.9% | 70.7% | 70.2% | 72.8% |
| 20 | 1, `kf_mpc`, the frozen reference | 73.0% | 77.3% | 69.0% | 74.5% | 74.4% | 71.2% | 70.9% | 73.8% |
| 27 | `blind`, fixed plan | 55.0% | 59.4% | 59.4% | 57.2% | 55.1% | 53.0% | 43.8% | 56.7% |
| 28 | `cautious`, leg-and-wait | 42.0% | 46.0% | 44.8% | 44.0% | 45.5% | 42.7% | 42.5% | 28.8% |
| 29 | `solvi_reference` | 41.0% | 43.8% | 37.6% | 42.3% | 43.7% | 41.9% | 40.7% | 37.0% |
| 30 | `kristjan_reference` | 41.0% | 44.8% | 43.9% | 43.2% | 43.7% | 41.1% | 41.2% | 28.8% |

Paired by episode, in points of share, with a 95% bootstrap over seeds:

| Comparison, all biomes | Difference |
|---|---|
| 33 against `kf_mpc` | **+1.9 (+1.0 to +2.8)** |
| 24 against `kf_mpc` | +1.6 (+0.9 to +2.3) |
| 33 against 24 | +0.3 (−0.1 to +0.7) |
| 34 against 24 | +0.1 (−0.1 to +0.3) |
| 27 against 24 | −1.5 (−2.1 to −0.7) |

- **Controller 33 is the best overall, and it is controller 24 everywhere except Hidden Valley.** It is 24 with the slip-check layer and the executive from `mars.py`, which do nothing when the rules publish no slip check. Its whole lead over 24 comes from Hidden Valley: +1.8 points there (−0.6 to +5.1), with half as many slip stops (0.3 per episode against 0.6 at delay 3) and 99% of rovers home against 94%.
- **The honest reading is "the 24 family".** Controllers 19, 22–26, 31, 33 and 34 lie within 0.3 points of each other. With 40 seeds, differences under about one point are noise.
- **The lead over the frozen reference is real: +1.9 points.** By biome it is +5.1 on Relay Pass (+3.5 to +6.7), +3.0 on Hidden Valley, +1.6 on Bagnold Dunes, +1.3 on Main Mars, +1.1 on Gale Rock Field, +0.5 on Troy Crust and +0.3 on Meridiani; the last two intervals include zero.
- **`kf_mpc` is not aware of relay passes.** That is the whole Relay Pass gap: it plans as if an uplink left at once. It never stopped with an error at 8/4, though; only `solvi_reference` did, in 4 episodes.
- **27's guarded moves cost 1.5 points here too**, as on the plain profiles. 34 removes that cost.

### Best controller in each biome

| Biome | Best | Its share | 33 | `kf_mpc` | Fixed plan | Leg-and-wait |
|---|---|---|---|---|---|---|
| Main Mars | 20 (18–25, 31 and 33 tie) | 78.7% | 78.7% | 77.3% | 59.4% | 46.0% |
| Relay Pass Schedule | 20 | 74.2% | 74.1% | 69.0% | 59.4% | 44.8% |
| Hidden Valley | **33** | 77.4% | 77.4% | 74.5% | 57.2% | 44.0% |
| Bagnold Dunes | 34 | 76.4% | 76.0% | 74.4% | 55.1% | 45.5% |
| Troy Crust | 26 | 72.3% | 71.8% | 71.2% | 53.0% | 42.7% |
| Gale Rock Field | 34 | 72.3% | 72.0% | 70.9% | 43.8% | 42.5% |
| Meridiani Ripple Plains | 10 | 74.3% | 74.1% | 73.8% | 56.7% | 28.8% |

Controller 33 is within half a point of the best in every biome. Only in Hidden Valley is the winner clearly set apart.

### What each biome costs, and whether the cost grows with the delay

Controller 33's share by delay, and the difference from Main Mars at the same delay:

| Biome | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| Main Mars | 88.8% | 79.3% | 67.9% |
| Relay Pass Schedule | 87.4% (−1.4) | 73.2% (−6.1) | 61.6% (−6.3) |
| Hidden Valley | 88.8% (0.0) | 78.4% (−0.9) | 65.2% (−2.7) |
| Bagnold Dunes | 87.4% (−1.4) | 75.5% (−3.8) | 65.1% (−2.8) |
| Troy Crust | 83.9% (−4.9) | 70.5% (−8.8) | 60.9% (−7.0) |
| Gale Rock Field | 85.1% (−3.7) | 70.5% (−8.8) | 60.4% (−7.5) |

- **Every biome costs more at delay 3 than at delay 0.** That is the pattern the brainstorm asked for: the difficulty should come from the delay, not from the terrain alone. It is shown here for a scripted controller only; the same test with a model has not been run.
- **Fixed plans pay most on rough ground.** `blind` loses 15.6 points in Gale Rock Field, where spins throw a plan off that never reads telemetry, and gets home in 64% of episodes. It loses 6.4 in Troy Crust and nothing in Relay Pass, since its whole plan leaves at tick 0, inside a pass.
- **Leg-and-wait pays most under relay passes, once there is a delay:** 43.1% against 50.2% on Main Mars at delay 3, and 25.8% against 34.3% at delay 5.
- **Meridiani Ripple Plains is, in practice, `rush_noisy`.** It switches the sensing noise on for `rush`, so both profiles become the same episode, and its row in the tables above reflects that noise. Against Main Mars on `rush_noisy` alone, controller 33 scores 86.9 / 73.2 / 62.4% against 87.1 / 73.2 / 61.9%: the noisier odometry on sand changes less than half a point. As a biome it is nearly inert with today's controllers.

## Limits

- **No model has played a biome.** Whether a biome opens a gap between an agent and a reference is unknown.
- **No controller reads the new published areas.** Crust regions, rock fields and dune slopes are in `map()`, but every controller here only reacts to them through telemetry. The trial shows which existing controller is most robust, not how well a biome can be played. A controller that prices crust at its published rate, counts wheel wear, or fits the slope line should do better; none is built.
- **Bound 16 is not a bound in the biomes.** Its planner ignores their rules. On Relay Pass at delay 0 it scores below controller 33.
- **40 seeds, one draw each.** Differences under about one point are noise.
- **Mixed biomes** work and have one test; they were not part of the trial.
- **Seeds:** development 0–19 for the settings; 2000–2039 for the trial, now used.

## Suggested next steps (not done)

1. Biome-aware layers for the 24 family, each inactive when its rule is absent: expected-cost pricing of crust at the published rate, a guard that only doubts ground inside crust regions, a wear count that shortens planned drives, a fit of the dune slope line.
2. With those, a second calibration: stronger settings should then pass the keep rule.
3. One model run in one biome at delay 0 and delay 3. This is the delay-relevance test with a real agent, it costs API credit, and it is a team decision.
4. A team decision on whether any biome ever joins a graded profile. The brainstorm's advice stands: at most one or two, Relay Pass first, and only after a model has played it.

## The biome edition of the 3D demo

**`viewer/biomes-demo.html`**: the 3D Mars demo with a row of biomes on its title screen. Open it by double-click, like the main demo. ← → choose a biome; the rest of the keys are the main demo's.

- **Main Mars** holds the main demo's own three missions (Deadlines, Sand, Rocks), with Claude's attempts and the reference, taken from `build_mars.gather()` unchanged.
- **Every other biome has one mission**, played when the page is built by four scripted controllers on the same map: controller 33 (best overall above), the frozen reference `kf_mpc`, the fixed plan and leg-and-wait. Keys 1–4 switch between them and M shows all four.
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
