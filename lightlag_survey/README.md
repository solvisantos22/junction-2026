# Six-region survey experiment

Six regions share hidden science qualities across fourteen targets; the rover has
only two imperfect remote inspections. Physical samples reveal regional quality
too. The original expedition, shared physics and canonical task are unchanged.

[Contract and current results](../docs/lightlag-survey-experiment.md) ·
[Predeclared free gate](../docs/lightlag-survey-gate.md)

This package is experimental. The completed free study has 576 development and
128 held-out episodes, all alive and home. The structural gate passes, but the
information-value check fails: adaptive raw 9.9625 versus no inspection 9.79219,
entropy 10.09687 and the development-selected fixed pair 9.80156. No paid model
call follows this protocol. Extra regions or lower normalized scores alone do
not prove difficulty. [Decision and handoff](../docs/lightlag-survey-handoff.md).

## Free development and separate check

The commands below reproduce the published experiment; they do not create fresh
validation data. Maps 0–7 and the declared episode seeds are now used. Any tuned
revision needs a new protocol and unused check inputs.

Run from the repository root. Choose new output directories; existing evidence
is never overwritten. Workers can be 1, 2 or 3.

```sh
python3 -m lightlag_survey.study --stage development --workers 3 --output /tmp/survey-development-new
python3 -m lightlag_survey.study --stage prepare-check --development /tmp/survey-development-new --output /tmp/survey-check-new
python3 -m lightlag_survey.study --stage check --workers 3 --output /tmp/survey-check-new
```

Development runs 576 episodes: four maps, eight episode seeds per map, adaptive,
no-probe, entropy and all fifteen fixed pairs. Preparation checks all evidence,
selects the development-best fixed pair, requires the structural gate, and seals
sources/settings without a check rollout. The check then runs 128 episodes on
disjoint inputs. Do not prepare or run it until development choices are finished.

All policies see only `rules`, `map`, `telemetry_log`, `uplink` and `advance`.
The four-target reference is a bounded heuristic with explicitly documented
forecasting approximations. Fixed pairs and entropy share its navigation and
admission rules; they can decline an inspection. Every transcript, replay,
reported failure and paired score is retained. Errors cannot make a gate pass.

A model pilot is a separate step only after both gates pass. These commands use
no model API or credits.

## Mechanics and tests

`SurveyEnvironment(seed=..., mission_seed=..., visibility="hidden")` is the trusted
simulator interface. Visibility `public` discloses the same sampled qualities at
launch. `evaluate()` and `replay()` are evaluator-only and must never be exposed
to a model. The remote action is `{"action":"inspect","region":"r4"}`; all six
regions are accepted, but only two total reservations are allowed.

```sh
python3 -m unittest discover -s tests/lightlag_survey -q
python3 -m unittest discover -s tests/lightlag_expedition -p test_reference_v2.py -q
```
