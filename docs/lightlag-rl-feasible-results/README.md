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
