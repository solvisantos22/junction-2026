# Lightlag demo

## The 3D Mars demo

**Open [`mars-demo.html`](mars-demo.html) by double-clicking it.** It is one file with everything inside, so it needs no server and no network. Use Chrome, press **F** for full screen, pick a mission, and it plays.

Use the visible playback bar to pause, step, restart or jump to the next event. Expand any panel for a closer look; on phones, switch between Mars, Earth, Map and Console with the view tabs. The **?** button opens the mission guide. [Full control guide and browser verification](USABILITY.md).

It replays recorded runs. Nothing is simulated in the page and nothing is re-enacted: every tool call it shows was made by the agent in that saved trial, and the scores are the ones the verifier wrote.

### The three missions

Each shows three unchanged-prompt attempts by Claude Opus 5.5 and the frozen reference controller on the same seed. The first two come from the overnight evaluation ([protocol and all results](../docs/lightlag-overnight-evaluation.md)); the third was run on Saturday for this page.

| Mission | Rules | Claude, attempts 1 · 2 · 3 | Reference |
|---|---|---|---|
| **1 Deadlines** (rush, seed 501) | Seven samples with deadlines, two appear mid-mission, 50 ticks | **0.00** · 0.83 · **0.00** | 0.83 |
| **2 Sand** (rush + noisy, seed 502) | The same, plus noisy position fixes and targets across sand | **0.46** · 0.77 · 0.81 | 0.77 |
| **3 Rocks** (rush + noisy, seed 1026) | The same rules on a map where two rock fields sit on the routes | 0.85 · **0.52** · 0.69 | 0.77 |

The demo opens on the weakest attempt in each (attempt 3 in Deadlines, attempt 1 in Sand, attempt 2 in Rocks). The other attempts are one key away, including the ones where Claude ties or beats the reference.

**These seeds are not a random sample.** Seeds 501 and 502 were picked overnight because the model had already failed on them, to see whether the failure repeats. It repeats sometimes. Seed 1026 was picked for its map alone, before any model played it: it is one of the three seeds, out of 0–1199, with the most straight routes blocked by rock. Say so when presenting.

### Mission view (four screens, one run)

| Screen | What it shows |
|---|---|
| **Mars · now** | The rover as it really is. The pale ghost is where Earth last saw it |
| **Earth** | The newest picture Earth has: a still frame, one per tick, 3 ticks old, drained of colour |
| **Map** | Top-down: the path driven, the commands still to land, each target's deadline |
| **Console** | The five MCP tools as keys that press when the agent calls them, commands and telemetry in transit, the call log, and at the end the agent's own account |

Things to point at:

- **Flags** are targets. The bar over each is its deadline running out. Green means sampled, grey means the deadline passed (a late sample is worth a quarter).
- **The HOME marker on the battery bar** is a lower bound on the reserve needed to finish home and alive: remaining idle drain plus a straight drive to the nearest position within the accepted 0.75 m base radius, with no slip or detours. Below it, the bar turns red: there is insufficient reserve to finish home alive. The rover may still reach home earlier or survive elsewhere; staying above the marker does not guarantee a feasible plan.
- **"pt carried"** is the credited value of the samples so far. At the final tick it counts fully if the rover is at base alive, half if alive elsewhere, and zero if the battery is empty.
- **"Wheels slipping"** appears when a drive covers less ground than commanded. The hollow ring is where the drive was aimed and the red line is how far short it stopped.

### Compare view (four runs at once)

Press **M**: the three attempts and the reference on the same clock. At the end each shows its verdict and score.

### Controls

| Key | Does |
|---|---|
| Enter | start the selected mission (↑ ↓ to choose on the title screen) |
| space | play / pause |
| ← → | step one tick |
| 1 2 3 4 | show that run (attempts 1–3, then the reference) |
| M | switch between Mission and Compare |
| Z | zoom one screen to fill the stage (press again for the next, then back to four); a double-click on a screen does the same |
| , . | jump to the previous / next event in the run |
| N | next mission |
| − = | slower / faster |
| Esc | back to the title screen |
| F | full screen |

Adding `#auto` to the address starts it automatically and loops, for an unattended screen.

### What to say while it plays

**Deadlines, attempt 3** (the default):

- **Tick 0:** Claude reads the rules and the map, works out headings in its own shell, and queues nine commands before the rover has moved. Watch them leave Earth in the signal lane.
- **Tick 6:** first sample. A new target, D2, appears. Mars shows it at once; the Earth screen learns of it three ticks later.
- **Tick 17:** Claude sends the trip to D2. Its deadline is tick 18, so the sample will be late and worth a quarter: half a point.
- **Tick 23:** on the Mars screen the battery drops below the HOME marker: insufficient reserve to finish home alive. On the Earth screen, at the same moment, the battery still reads 30 and looks fine. The sample for tick 24 is already queued.
- **Tick 24:** the late sample lands. Every target is taken: 10.5 points carried. The battery reads 12.7, and idling to tick 50 alone costs 13, so depletion is now unavoidable even without further actions.
- **Tick 24–50:** the rover sits 4.3 m from base and runs flat on the last tick. Score 0.00. Claude's own explanation appears in the console.
- **Then press 2:** the same model, same prompt, skips D2 and gets home with 5 battery left: 0.83, the same as the reference (press 4).
- **Then press M:** all four at once.

Attempt 1 illustrates why the warning concerns the finish: it warns at tick 23, reaches base alive at tick 25, then runs out of battery at tick 49.

**Sand, attempt 1** (press N):

- **Tick 6:** the first drive onto sand covers 4.08 m of the 4.70 m commanded.
- **Tick 12–15:** three drives across the sand slip by 22–25%. Claude had planned for 30%.
- **Tick 16:** so it overshoots T4 and the sample fails: nothing in range.
- **Tick 22:** a second miss, at D2, the most valuable target, which appeared mid-mission.
- **End:** home alive with 6 of 13 points, 0.46. The reference gets 0.77, and so does Claude's second attempt; its third beats the reference.

**Rocks, attempt 2** (press N again):

- **The map:** one rock field sits between the base and the targets to the north-west, a second between two targets. The route has to weave between them.
- **Tick 16:** a sample at T2 fails: the rover is not where Claude thinks it is.
- **Tick 17:** the next drive runs into the rocks. Safety stop, and every queued command is dropped, including the sample at T3. The Earth screen at that moment still shows tick 14 and a sample being taken.
- **After:** Claude finds out three ticks later, re-plans, gets T2 on a second try and reaches D2 late for a quarter of its value. Home alive: 0.52.
- **Then press 1:** the same model weaves through cleanly and scores 0.85, above the reference's 0.77. Worth saying out loud: on this map the reference is not the best run.

### Rebuild it

```sh
python3 viewer/build_mars.py     # refreshes viewer/mars/data.json and viewer/mars-demo.html
```

The missions and the saved trials they use are listed at the top of `build_mars.py`. For development, serve `viewer/mars/` with any static server (`python3 -m http.server` in that folder) and open `index.html`; it loads `app.js`, `style.css` and `data.json` separately. A test fails if the committed `mars-demo.html` is stale.

three.js (r187, MIT licence, in `viewer/mars/vendor/`) is the only dependency. The terrain, rover, lander and textures are generated in code; there are no image or model files. The display face is DIN Condensed, which ships with macOS; other systems fall back to another condensed face.

### Limits

- **It shows chosen runs.** Two seeds where the model had failed before, one chosen for its rocks, and the weakest attempt first. The full overnight record, wins included, is in the overnight evaluation.
- **The Rocks runs needed a second launch.** The first three launches timed out installing OpenCode in the container (slow network) before any model call, so there was nothing to keep from them. The three attempts shown are the only ones in which the model played.
- **The HOME marker is the page's own arithmetic,** not something the simulator reports or the model predicted. It includes idle drain through the horizon and the shortest distance to the accepted base radius, but excludes slip, detours and other action costs, including queued samples. On Mars it uses true replay positions: a necessary lower bound, not a safe-route forecast. Earth uses the delayed, potentially noisy reported position, so its marker is an estimate and its caption says “low estimated reserve.” The synthetic true-state warning is omitted from Earth; it is a replay annotation, not a telemetry event.
- **Checked in Chrome only,** on this laptop (about 60 frames a second in Mission view and 35 in Compare), and opened from disk in headless Chrome.
- **Queued commands are drawn as if the wheels did not slip.** The dashed line is where commands aim, not where they land.
- **The original seed-7 mission is no longer in this page.** Claude solves it (1.00); that run is still in `docs/lightlag-runs/opencode-opus-5-5-seed7-delay3` and in the 2D page below.
- A replay contains the true rover states and the hidden slip values, so the page is evaluator-side material.

## The simple 2D page

[`demo.html`](demo.html) is the earlier flat version: four runs side by side on a top-down map with a chart of how wrong each operator's view is. Build it with `python3 viewer/build.py` (see `--help`). `template.html` opened alone accepts replay files by drag and drop.

Sölvi's [`decisions.html`](decisions.html) is a separate page about one selected failure and a checked alternative continuation; see [the decision demo notes](../docs/lightlag-decision-demo.md).
