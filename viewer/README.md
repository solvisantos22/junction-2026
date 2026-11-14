# Lightlag replay viewer

One page that plays Lightlag episodes side by side on the same clock: where the rover really is, where the operator last saw it, the commands still in transit, and (for scripted controllers) where the controller believes the rover is.

**Open [`demo.html`](demo.html) by double-clicking it.** It needs no server and no network. It currently shows four runs on seed 7 at delay 3: the reference, Claude Opus 5.5 through Harbor, a controller that forgets commands in transit, and one that waits for every command to land.

Controls: Play, the slider, and the speed menu. Space toggles play; the left and right arrows step one tick.

## Build a page from other runs

```sh
python3 viewer/build.py --out viewer/demo.html \
    "Reference=policy:reference" \
    "Claude Opus 5.5 via OpenCode (Harbor run)=docs/lightlag-runs/opencode-opus-5-5-seed7-delay3/artifacts/evaluator/replay.json" \
    "Forgets commands in transit=policy:stale_telemetry" \
    "Waits for every command to land=policy:move_and_wait"
```

Each argument is `LABEL=SOURCE`. A source is either a `replay.json` (every Harbor run writes one under `artifacts/evaluator/`) or `policy:NAME`, which plays a scripted policy from `lightlag_controllers` on the simulator; `--seed` and `--delay` apply to those. `viewer/template.html` opened alone accepts replay files by drag and drop.

## What to say while it plays

- **Around tick 7:** the reference's raw view is about two metres behind, but its own estimate is within 0.3 m. The controller that forgets its queued commands believes the rover is still at base while it is 15 m away with four commands in transit.
- **Tick 9:** that controller hits the map edge. It keeps re-sending moves and drains the battery.
- **The end:** the reference and the model both collect everything and get home. The cautious controller runs out of clock with two targets.
- **The chart:** dashed lines are the raw delayed view, which is stale for everyone. Solid lines are each controller's own estimate. The reference's solid line stays near zero.

The belief marker exists only for scripted controllers, because they record what they believed. A model's run has no such record, so its panel shows the true rover and the delayed view only.

## Limits

- A replay contains the true rover states and the hidden slip values. It is evaluator-side material: fine for a demo, never for an agent's container.
- Queued commands are drawn as if the wheels did not slip, so the dashed line is where the commands aim, not where they will land.
- The page was checked by opening it in Chrome. `tests/viewer/` covers the build step only.
