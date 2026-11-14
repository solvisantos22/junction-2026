# Regional-science rover experiment

A separate experimental extension of the continuous delayed rover. Three regional
qualities affect eight target values; two imperfect remote inspections compete
with driving, sampling, deadlines and the return journey. Physical samples reveal
regional quality too. Final project/task selection remains with the team.

See [contract, results and limitations](../docs/lightlag-expedition-experiment.md).
Existing `lightlag`, `lightlag_dynamic` and the canonical Harbor task are unchanged.

Run the public-only reference locally:

```python
from lightlag_expedition.service import ExpeditionService
from lightlag_expedition.reference import run_policy

service = ExpeditionService(seed=100, mission_seed=0, visibility="hidden")
run_policy(service, "reference")
print(service.finish())  # evaluator-side only; not a model tool
```

The model sees only `rules`, `map`, `telemetry_log`, `uplink`, and `advance`.
A new command `{"action":"inspect","region":"r2"}` uses the same FIFO queue and
telemetry delay. `visibility="public"` discloses the same regional qualities at
launch; it does not change physics or grading.

Reproduce the free study into a **new** directory:

```sh
python3 -m lightlag_expedition.study --output /tmp/expedition-development-new
```

Generate an isolated Harbor package outside the checkout, then run it without a
model or API key:

```sh
python3 -m tools.expedition_experiments.prepare /tmp/expedition-task-new --mission-seed 0 --seed 100
harbor run -p /tmp/expedition-task-new -a oracle -n 1 -k 1 --max-retries 0
```

The oracle is the public-information four-target KF/MPC heuristic, not a globally
optimal policy. Available controls are `no_probe`, `leader_probe`, `entropy_probe`,
`forced_leader_probe`, and `value_blind`. The reported model pilot has separately
frozen tasks; do not regenerate or overwrite its evidence.

Package checks (MCP tests require the pinned runtime):

```sh
uv run --with 'mcp==2.3.0' python -m unittest discover -s tests/lightlag_expedition -q
python3 -m unittest discover -s tests/expedition_experiments -q
```
