# Charging-aware RL interface

The [fixed protocol](../lightlag-rl-feasible.md) compares Sölvi's persistent
fourteen-feature policies with and without a public charging-time feasibility
mask. This is a local development experiment, not a new task or frontier result.

## Implementation checkpoint

`lightlag_rl_feasible.adapter.visit_return(pilot, tick, x, y, battery, target_id)`
returns the existing route model's estimated visit/return timings and battery,
or `None` if infeasible. It uses public map/rules and the pilot's estimates only.
`FeasiblePilot` applies that mask and inherits the unchanged low-level navigator.
Home remains available; the persistent wrapper releases targets removed by the
mask. This helper is available for Sölvi's separately owned learning campaign;
its source hash must be pinned by any consuming experiment.

Seven focused tests cover waiting for charge, return and sample energy, late-day
infeasibility, releasing a held target, exact old/new runner equivalence,
full-horizon behavior and paired statistics. The two-map smoke matrix has 20
completed missions; its [report](smoke/report.json) and complete traces are
retained. The [audit](smoke/audit.json) reproduces all 20 physical trajectories,
879 chooser invocations and 592 rejected candidate occurrences. All 21 inherited
persistence tests also pass. Smoke scores are implementation checks, not development conclusions.

```sh
python3 -m unittest discover -s tests/rl_feasible -v
python3 -m tools.rl_feasible.run --output docs/lightlag-rl-feasible-results/development
python3 -m tools.rl_feasible.run --audit docs/lightlag-rl-feasible-results/development/report.json --output docs/lightlag-rl-feasible-results/development/audit.json
```

Run directories are immutable: reruns must use a new path. No training update,
fresh map, cloud job or model API request belongs to this first comparison.

## Fixed development result

The protocol/code was published at `5b5dcb2` before the 240-case comparison.
All 120 time-only controls exactly reproduce Sölvi's saved persistent cases.

| Fixed chooser | Score: time-only → charging-aware | Alive/home |
|---|---:|---:|
| Initial weights, 48 per arm | .077621 → .098718 | 29/48 → 48/48 |
| Previously trained weights, 48 per arm | .093678 → .115034 | 28/48 → 48/48 |
| Greedy, 24 per arm | .226235 → .282238 | 13/24 → 24/24 |

There are no deaths or invalid calls. The primary final-weight paired gain is
.021355, map-bootstrap 95% interval [.010901, .031750]. The predeclared screen
passes. All 120 treatment cases return alive and home, compared with 70/120
controls. Sample counts barely change (final weights 7.208 → 7.167); the official
score gain largely reflects preserved return credit, not more collected samples.
All policies are unchanged: this is an interface intervention, not new learning.
The [paired score accounting](development/impact.json) gives final-weight science
change −.000181 and reduced terminal penalties +.021536, summing to +.021355.
There are 20 gained home outcomes and none lost, although six individual paired
scores are lower. Greedy gives up .009357 in normalized science value and recovers
.065359 in terminal penalties. These are arithmetic components of the measured
intervention; they are not a hypothetical rescue of unchanged trajectories.

[Complete report](development/report.json), [source/input freeze](development/freeze.json),
and all 240 compressed cases are retained. The [full audit](development/audit.json)
reproduces all 240 physical trajectories, 10,659 chooser invocations and 6,325
rejected candidate occurrences; every feature/decision/command is re-extracted. These are the same 24 previously used
training maps; this supports the charging-time diagnosis there, not a fresh
generalization or frontier-agent claim. The route model remains approximate.

The subsequent [planner-initialized contextual pilot](contextual.md) is complete:
imitation improves fresh score .0926 → .2822; the short RL phase adds no clear
gain (.2792), below greedy .3263 and the reference .5091. All 320 fresh missions
return alive/home. Its full audit reproduces 600 imitation epochs, 24 RL updates, all 724 physical
trajectories and all 340 teacher/evaluation controllers. This
complements Sölvi's larger scratch-learning campaign. The existing full-route planner
remains the project reference.
