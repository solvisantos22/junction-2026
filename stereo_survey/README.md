# Stereo survey

A standard-library-only prototype for choosing compatible images under camera,
energy, memory and communication constraints. This is a small planning
experiment, not a new canonical Harbor task or a model evaluation.

## Mission and reward

Two camera platforms follow known tracks above a flat map. At each opportunity,
choose one of two offered frames, or take neither. A map cell earns its weight
once if a pair of **returned** frames satisfies all of these conditions:

- Both orthorectified rectangular footprints contain its centre.
- The camera-to-cell rays differ by 15–55 degrees, inclusive.
- Capture times differ by at most nine ticks.
- The larger ground-sampling distance divided by the smaller is at most 1.5.

One frame may support multiple products; one cell never earns its weight twice.
Taking photos without a compatible second view earns no stereo science.
The matched monocular control rewards coverage from a single returned frame.

All coordinates are metres: **x east, y north, z up**, with ground at `z=0`.
Angles are degrees. Footprints and pixel scales are supplied planning inputs;
the prototype does not model optics, terrain occlusion or orbit propagation.
`geometry.py` is the public executable convention, suitable for an eventual
agent workspace. For a cell at `(0,0,0)`, cameras at `(-5,0,10)` and `(5,0,10)`
have a convergence angle of `2 * atan(0.5) = 53.1301°`, inside the allowed range.
Identical camera positions have zero convergence and do not make stereo.

## Resource timing

An exposure lasts one tick. The camera then needs `ceil(angle / slew_rate)`
ticks before another exposure; its initial direction and start time are public.
Capture and transmission each use their specified energy. Each slew consumes
`ceil(angle / slew_energy_angle)` additional energy. The public helper uses a
`1e-9` tolerance at angle and rounding boundaries. There is no recharging.

Images occupy one memory slot. Known downlink windows drain the camera's FIFO
queue, up to that window's capacity. **Downlink happens before capture at the
same tick**, so a newly captured frame waits for a later pass. The two cameras
have separately allocated relay channels. All selected frames must return by
the horizon. Invalid resource schedules score zero and receive explicit errors.

There is no stochastic noise, secret parameter, wall-clock simulation deadline
or privileged reference input. `mission.json` contains every planning input.

## Running a mission

From the repository root:

```sh
python3 -m stereo_survey generate --seed 0 --profile compact --output /tmp/stereo-mission.json
python3 -m stereo_survey solve /tmp/stereo-mission.json --max-joint 10000000 --output /tmp/stereo-plan.json
python3 -m stereo_survey verify /tmp/stereo-mission.json /tmp/stereo-plan.json
python3 -m unittest discover -s tests/stereo_survey -v
```

A plan has exactly this schema: `{"images": ["p0-t00-v0", "p1-t03-v1"]}`.
The IDs above illustrate the syntax; they are not a recommended schedule.
`solve` prints raw science and proof status, writes the plan, and exits with
code 2 if a search cap prevents proof. `verify` exits with code 1 for an invalid
plan. Empty plans are valid and score zero. Never call a capped result optimal.

The `compact` profile has 24 candidate frames across 12 camera opportunities;
`expanded` has 32 across 16. Both use the same 20-cell map, with seeded public
weights, offered footprints and pixel scales. No instance is filtered based on
reference, baseline or model performance.

## Reference and controls

`search.py` compiles pair geometry and resource constraints. The exact reference
enumerates all feasible local frame selections and checks their joint plans,
pruning only with an optimistic coverage bound. Deleting frames cannot worsen
energy, storage or slew feasibility, so invalid partial selections can be
pruned. The angular triangle inequality justifies direct-slew pruning.

`verify.py` independently reconstructs the chronological resource timeline and
science products without importing search code. Geometry is intentionally the
same public helper; known-angle, coordinate-translation and boundary tests check
that contract separately. Six tiny missions are also checked against every
image subset through the standalone replay, for both scoring objectives.

Controls include coverage-only greedy, pair-aware greedy, pair-aware greedy
per added image, image beam search and pair beam search (width 64). Greedy and
beam portfolios select their highest-scoring valid plan using the public
checker. They receive no optimum or winning schedule. They are **programs, not
LLM agents**. All share compiled public geometry; recorded timings have warm
caches and are diagnostics, not a fair speed benchmark.

## Retained study

```sh
python3 -m stereo_survey.study --split development --start 0 --count 12 --output docs/stereo-survey-results/development.json
```

Every JSON report includes all missions, plans, raw scores, proof status, search
counts, source hashes and timings. A capped reference remains in the report;
normalized statistics explicitly exclude unproved or zero optima. Such cases
fail the screening gate rather than being silently dropped. Portfolio records
reuse existing plans, and the same seed at different sizes is correlated.

Initial development: the pair-aware beam portfolio matches all 23 proven stereo
optima. The remaining expanded case (seed 11) reaches the two-million-joint-plan
proof cap, with reference and beam both scoring 36. That score is not yet proved
optimal. Coverage-only greedy obtains only 15–17% on the certified cases, but
pair-aware greedy obtains about 96%. This demonstrates the intended pairing
mechanism; it does not yet justify a model-difficulty claim.

See [design, protocol and results](../docs/stereo-survey.md).
