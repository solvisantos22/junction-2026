# Planner-initialized contextual learning

This is the local, bounded [three-seed protocol](../lightlag-rl-contextual.md).
It follows the [verified charging-aware interface](README.md). Sölvi separately
owns scratch PPO/replay learning on Modal; his map ranges and results are separate.
The original full-route planner remains the project reference.

## Implementation verification

The 1,984-parameter model receives 60 public features, including charging
estimates, onward opportunities and pooled candidate context. It learns a next
goal above the unchanged navigator. Teacher search runs only while generating
demonstrations. Imitation and RL checkpoints are saved separately; overridden
proposals remain in the trace but receive no policy gradient.

Six focused tests pass, including numerical differentiation, context dependence,
public-only feature extraction, synthetic imitation, excluded overridden draws,
full-horizon student inference with teacher calls forbidden, and complete paired
evaluation bookkeeping. Sölvi's tested gradient/Adam implementation is reused.

The [smoke run](contextual-smoke/report.json) uses only already-used maps 1/2,
two imitation epochs and one four-mission RL update per initialization. Its
[audit](contextual-smoke/audit.json) reconstructs all three optimizer updates,
six imitation epochs and 536 training draws. All 54 saved physical trajectories
replay; all 42 teacher/evaluation policy scaffolds re-execute, including candidate
features, choices and commands. Smoke outcomes are not learning conclusions.

```sh
python3 -m unittest discover -s tests/rl_contextual -v
python3 -m tools.rl_contextual.run --output docs/lightlag-rl-feasible-results/contextual
python3 -m tools.rl_contextual.audit docs/lightlag-rl-feasible-results/contextual/report.json --output docs/lightlag-rl-feasible-results/contextual/audit.json
```

The production runner requires the completed feasibility audit, freezes sources
and maps before teacher data, saves every update, and freezes all nine checkpoints
before opening any fresh evaluation map. Directories are immutable. A failure
is retained and does not silently trigger a retry. Audit from the source version
in the freeze; later unrelated experiments must preserve these source files.

No production teacher collection, RL run or new check result is claimed at this
implementation checkpoint. There has been no cloud job or model API spend in
this branch.
