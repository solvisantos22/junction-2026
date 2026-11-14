# Six-region survey: frozen free-test gate

This protocol is agreed **before six-region policy outcomes**. It records the
free development/check study and its gate before any paid follow-up; it does not
promote the experiment to the team's final task. All outcomes, failed checks and source versions must be retained. Existing
expedition studies, shared physics and teammate code remain unchanged.

The observed three-region escape was productive: Opus sampled one region and
inspected the other two while travelling. Its first hidden score was .55 versus
the reference's .46. Six regions with two inspections prevent that opening from
covering every region, but extra regions could still be irrelevant to the best
route. The gate below tests that possibility. It does not presume model failure.

## Task and comparator contract

The new survey has six regions with rich priors `.90, .35, .50, .25, .70, .45`.
Each has two initial targets, with per-target base values `2, 3, 2, 3, 2, 3`.
Two value-3 discoveries belong to r4/r6, appearing at ticks 10/22 with deadlines
26/44. The public all-rich normalization is **36**. Geometry uses six clusters
60 degrees apart, bearing jitter ±20 degrees, and radial ranges r1 `[4,7]`,
r2 `[6,10]`, r3 `[5,9]`, r4 `[6,10]`, r5 `[4,8]`, r6 `[5,9]` metres.
Full initial-target windows and generator details must be published and source
frozen before the study. Horizon 60, delay 3, battery 100, ordinary rover physics,
costs, sensing, science multipliers and two-inspection budget remain unchanged.

Reference v2 must use only public tools and support inspection overlap with
productive drive/sample commands. All acquisition controls share its motion
estimator, route pool/search limits, overlap/wait admission, queue accounting,
sample learning and return reserve. They may use zero, one or two inspections.
Fixed-pair controls restrict eligible inspection regions; they are **not forced
to waste both inspections**. Entropy restricts acquisition candidates by current
entropy and uses the same value/admission calculation. Publish these limits: v2
is a bounded heuristic, not a globally optimal continuous-policy solver.

Before the survey study, an optional comparator-repair diagnostic runs old and
new references on the old three-region development maps 0–3, crossed with episode
seeds 100–107: 32 paired cases. Record scheduling, score and safety, including
regressions. These are development observations, not new model validation.

## Fixed study budget and split

| Stage | Geometry seeds | Episode seeds, crossed with every map | Policies | Episodes |
|---|---|---|---|---:|
| Development | 0–3 | 100–107 | adaptive, no-probe, entropy, all 15 unordered fixed pairs | 576 |
| Check | 4–7 | 200–207 | adaptive, no-probe, entropy, development-selected fixed pair | 128 |

The same episode seed supplies physics and quality/signal draws to every policy
in a paired case. Use the simulator's prior-generated worlds without selecting
favourable qualities/signals. These 32-case grids are crossed designs, not 32
independent map draws. Report per-map and pooled results; do not claim population
significance from this small check.

Select the fixed pair with greatest development mean **raw score** over all 32
cases; break exact ties by lexicographic region IDs. Freeze that pair, source
hashes, settings, candidate/search limits and runner before running any policy on check
maps. Do not inspect check layouts, qualities or outcomes for tuning. Automated
generator-invariant tests cover 100 geometry seeds, including 4–7, without
displaying layouts or running policies; these are not policy outcome checks. A failed check retires those
inputs into development; it cannot be repaired and rerun as the same validation.
Any replacement study requires a new explicit protocol and unused inputs.

Target runtime is under one second per episode using public route-pool caching;
measure on development inputs before launching the matrix. If impractical, amend
and record the computation budget **before** running the study, without selecting
cases or policies from their scores. No six-region world enumeration is required.

## Structural development gate

Before advancing to the check, require all of the following:

- On at least two development maps, **all six regions** have a feasible initial
  two-target-and-home plan, each worth at least half the best **single-region**
  two-target-and-home expected value on that map. Use the same public route/cost
  model and deadline accounting for all six. This is not comparison against a
  full multi-region itinerary. Retain plans, costs, timing and feasibility reasons.
- The adaptive policy physically samples targets in at least four distinct
  regions across development and uses at least two distinct nonempty inspection
  sets. Retain per-region considered/feasible/inspected/sampled counts and the
  first-batch information coverage. Merely listing an area on the map is not use.
- The controls satisfy the shared-comparator contract above. Full replay,
  grading, normalization, public-only access and command/accounting checks pass;
  unexplained harness errors stop the gate rather than count as weak policies.

Diagnose whether changing one delivered inspection signal, with the rest of a
public decision state fixed, changes a later inspection or route. This is **not a
mandatory gate**: batching two observations can be optimal. Preserve negative
diagnostics. The objective is useful allocation, not compulsory sequential probes.

## Held-out check gate

Run all 128 planned episodes without tuning. Advancement requires:

- Adaptive has **zero deaths** and returns home in at least **31 of 32** cases.
- Its mean paired raw-score gain is at least **1.0 over no-probe**, and at least
  **0.5 over entropy** and **0.5 over the development-selected fixed pair**.
- Against each of those three controls, adaptive has a nonnegative mean gain on
  at least **three of four check maps**.

Report every case, including deaths and unfinished/failed attempts. Show credited
science before the home/survival multiplier, terminal raw score, normalized score,
battery, home/death counts, samples/deadlines, inspections and wasted commands.
Separate navigation/safety losses from information allocation. Do not discard
unsafe cases or compare only successful survivors. Missing or unexplained cases
make the check incomplete, never a pass.

The raw margins are practical screening thresholds, not significance tests or
proof of optimality. A normalized score falling because the denominator changed
from 20 to 36 is **not hardness evidence**. Report the best fixed pair as
*development-selected*, not the globally best fixed policy on unseen missions.

A public-quality run of the same bounded reference may be added as a separately
labelled diagnostic. It is not an upper bound and is not required to outperform
every hidden run. If it performs worse, report and investigate the planning limit;
do not describe the difference as a benefit of hiding information. Neither this
control nor an optional inspect-first baseline replaces the three gate comparisons.

## Decision and possible model follow-up

If either gate fails, preserve the result and make **no paid call** under this
protocol. Identify whether the regions are decorative, the comparator is weak,
or a simple allocation policy suffices. Six regions alone do not establish that
selective acquisition is necessary. Weak-GPS fusion remains a separate teammate
axis: it tests passive state estimation, not this acquisition bottleneck.

If both gates pass, prepare a separate frozen proposal for **at most one or two
strong-model sessions**, with fresh missions, clear public rules and scripting
allowed. Target roughly $1.00–$1.20 total new reported usage; exact launch/in-flight
guards and the second-call condition must be frozen before calls. The historical
nominal $1.817839 remainder is not a live account balance. Reported-usage guards
can overshoot during an in-flight response and are not provider hard caps. Use
the verified live-container usage monitor; do not assume Harbor host logs are live.
The user's existing credit authorization applies; a follow-up begins only after
these gates pass and its task, assignments and spending guards are frozen.
