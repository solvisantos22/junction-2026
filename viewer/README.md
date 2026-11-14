# Lightlag demo

## The 3D Mars demo

**Open [`mars-demo.html`](mars-demo.html) by double-clicking it.** It is one file with everything inside, so it needs no server and no network. Use Chrome, press **F** for full screen, pick a mission, and it plays.

It replays recorded runs. Nothing is simulated in the page and nothing is re-enacted: every tool call it shows was made by the agent in that saved trial, and the scores are the ones the verifier wrote.

### The two missions

Both come from the overnight evaluation ([protocol and all results](../docs/lightlag-overnight-evaluation.md)). Each shows the three unchanged-prompt attempts by Claude Opus 5.5 and the frozen reference controller on the same seed.

| Mission | Rules | Claude, attempts 1 · 2 · 3 | Reference |
|---|---|---|---|
| **1 Deadlines** (rush, seed 501) | Seven samples with deadlines, two appear mid-mission, 50 ticks | **0.00** · 0.83 · **0.00** | 0.83 |
| **2 Sand** (rush + noisy, seed 502) | The same, plus noisy position fixes and targets across sand | **0.46** · 0.77 · 0.81 | 0.77 |

The demo opens on the failing attempt in each (attempt 3 in Deadlines, attempt 1 in Sand). The other attempts are one key away, including the ones where Claude ties or beats the reference.

**These seeds are not a random sample.** They were picked overnight because the model had already failed on them, to see whether the failure repeats. It repeats sometimes. Say so when presenting.

### Mission view (four screens, one run)

| Screen | What it shows |
|---|---|
| **Mars · now** | The rover as it really is. The pale ghost is where Earth last saw it |
| **Earth** | The newest picture Earth has: a still frame, one per tick, 3 ticks old, drained of colour |
| **Map** | Top-down: the path driven, the commands still to land, each target's deadline |
| **Console** | The five MCP tools as keys that press when the agent calls them, commands and telemetry in transit, the call log, and at the end the agent's own account |

Things to point at:

- **Flags** are targets. The bar over each is its deadline running out. Green means sampled, grey means the deadline passed (a late sample is worth a quarter).
- **The HOME marker on the battery bar** is the battery needed to drive straight home and still be alive at the last tick. It is computed by the page as a lower bound (no slip, no detours). When the bar drops below it, no plan saves the rover, and the bar turns red.
- **"pt carried"** is what the samples are worth so far. It only counts if the rover ends at base alive: half if alive elsewhere, nothing if the battery is empty.
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
- **Tick 23:** on the Mars screen the battery drops below the HOME marker. On the Earth screen, at the same moment, the battery still reads 30 and looks fine.
- **Tick 24:** the late sample lands. Every target is taken: 10.5 points carried. The battery reads 12.7, and idling to tick 50 alone costs 13.
- **Tick 24–50:** the rover sits 4.3 m from base and runs flat on the last tick. Score 0.00. Claude's own explanation appears in the console.
- **Then press 2:** the same model, same prompt, skips D2 and gets home with 5 battery left: 0.83, the same as the reference (press 4).
- **Then press M:** all four at once.

**Sand, attempt 1** (press N):

- **Tick 6:** the first drive onto sand covers 4.08 m of the 4.70 m commanded.
- **Tick 12–15:** three drives across the sand slip by 22–25%. Claude had planned for 30%.
- **Tick 16:** so it overshoots T4 and the sample fails: nothing in range.
- **Tick 22:** a second miss, at D2, the most valuable target, which appeared mid-mission.
- **End:** home alive with 6 of 13 points, 0.46. The reference gets 0.77, and so does Claude's second attempt; its third beats the reference.

### Rebuild it

```sh
python3 viewer/build_mars.py     # refreshes viewer/mars/data.json and viewer/mars-demo.html
```

The missions and the saved trials they use are listed at the top of `build_mars.py`. For development, serve `viewer/mars/` with any static server (`python3 -m http.server` in that folder) and open `index.html`; it loads `app.js`, `style.css` and `data.json` separately. A test fails if the committed `mars-demo.html` is stale.

three.js (r187, MIT licence, in `viewer/mars/vendor/`) is the only dependency. The terrain, rover, lander and textures are generated in code; there are no image or model files. The display face is DIN Condensed, which ships with macOS; other systems fall back to another condensed face.

### Limits

- **It shows chosen runs.** Two seeds where the model had failed before, and the failing attempt first. The full record, wins included, is in the overnight evaluation.
- **The HOME marker is the page's own arithmetic,** not something the simulator reports: idle cost for the ticks left plus drive cost for the straight line to base.
- **Checked in Chrome only,** on this laptop (about 60 frames a second in Mission view and 35 in Compare), and opened from disk in headless Chrome.
- **Queued commands are drawn as if the wheels did not slip.** The dashed line is where commands aim, not where they land.
- **The original seed-7 mission is no longer in this page.** Claude solves it (1.00); that run is still in `docs/lightlag-runs/opencode-opus-5-5-seed7-delay3` and in the 2D page below.
- A replay contains the true rover states and the hidden slip values, so the page is evaluator-side material.

## The simple 2D page

[`demo.html`](demo.html) is the earlier flat version: four runs side by side on a top-down map with a chart of how wrong each operator's view is. Build it with `python3 viewer/build.py` (see `--help`). `template.html` opened alone accepts replay files by drag and drop.

Sölvi's [`decisions.html`](decisions.html) is a separate page about one selected failure and a checked alternative continuation; see [the decision demo notes](../docs/lightlag-decision-demo.md).
