# Earlier decisions and new learned planner strategies

Kristján requested continuing model/idea experiments on Modal after the previous
Extra Trees selector gained 0.4845 percentage points on 96 fresh worlds. That
study and its consumed worlds stay unchanged. This is a new, separately frozen
wave on the normal Traverse map. The canonical pilot, simulator, tasks and
teammate learners remain read only.

## Fixed design

- At tick **70**, a selector chooses one of **16 deterministic strategy programs**.
  Programs may activate at 70 or 140, reset to reference options at 300/340, or
  use a public-data energy/time guard. Strategy definitions are in
  `lightlag_planner_lab/policy.py`: baseline, refresh, early/late aggressive,
  balanced, stronger path energy price, deadline push, guarded fast/aggressive,
  two scheduled resets, late-value preferences 0/.5, wider arrival, conservative
  energy and two-start route search. The alternative late values are planning
  preferences; the actual reward remains unchanged.
- **61 features** combine the previous 49 public-state features with 12 public
  route/return/solar forecasts. No world seed, hidden physics or future reward is
  an input. Final reward and home/alive are evaluator-owned training labels.
- Training **570000–570383**: 384 worlds × 16 strategies = **6,144 missions**.
- Validation **571000–571063**: 64 × 16 = **1,024 missions**, plus **64** matched
  evaluations of the previous frozen Extra Trees policy at tick 140.
- Fit four fixed families on training worlds only: larger-data Extra Trees,
  Random Forest, a pooled action-conditioned forest with a separate failure
  classifier, and a two-layer MLP. Hyperparameters and RNG seed 37 are fixed in
  `model.py`. The MLP's early-stopping subset is inside training worlds. Pooled
  rows from the same world never cross train/validation boundaries.
- Validation tests thresholds 0/.002/.005. The two multi-output forests also
  test tree-disagreement penalties 0/.5; the pooled forest tests failure penalties
  0/.1/.3; the MLP has no additional penalty: **24 settings**. These penalties
  are decision heuristics, not calibrated uncertainty or safety guarantees.
- Rank eligible settings by validation mean reward, requiring no worse home/alive
  or deaths than the reference and zero invalid calls/errors. Choose the best
  two distinct model families; first is primary. Tie-break by family name then
  larger threshold/penalties. If fewer than two are eligible, retain remaining
  highest-ranked families as explicitly unqualified diagnostics. No refitting
  with validation data. Also retain the best fixed strategy by validation mean.
- Publish weights/selection before opening **572000–572191**. Compare reference,
  previous frozen Extra Trees, best new fixed strategy and two selected models:
  192 × 5 = **960 fresh missions**. Total production: **8,192 missions**.
- A practical upgrade needs primary mean gain >=.01 over the reference, positive
  paired 95% bootstrap lower bound, nonnegative mean gain over the previous
  Extra Trees, no worse home/alive or deaths than either control, zero invalid
  calls/errors, and validation eligibility. Also report family-adjusted intervals
  for all four comparisons with reference and the paired gain over the old model.
  Use 20,000 bootstrap draws with RNG seed 572192. No settings change after freeze.

## Fast, auditable execution

Each data job computes a common 70-tick prefix, then deep-copies pilot, environment
and tool proxy together before four independent continuations. Prove clone/full
run parity, baseline/reference parity and prior-model parity before production.
The prefix copies preserve alias relationships and RNG state. Final jobs share a
prefix across five arms, including the old model's later decision at tick 140.
The models never see the evaluator-owned environment or labels during play.

Use up to **100 mission containers**, 1 CPU and 1.5 GiB each, timeout 900 s, no
user-code retries. Fit calls use 2 CPU / 4 GiB, timeout 1,800 s, at most four
containers. Retain all policy outcomes including deaths. Results arrive unordered
and each completed batch is durably archived before requesting more. On an
infrastructure interruption, retain original attempts and resume only batches
without archived outcomes; platform preemption may still duplicate unreceived work.

Pin controller/model/source and job grids before execution. Record orchestration
files separately for each attempt so a transport-only recovery can preserve the
same experimental source. Save commands, decision features, grades, component/full
replay hashes and timings; fresh/smoke artifacts also retain complete replays.
Independently replay all results on Linux and check local physical replay/grades,
allowing only documented decorative-map floating-point differences. Recompute
model decisions, selection and statistics; repeat selected full controllers.

No GPU or LLM API calls. Prior Modal-spend authorization remains in force. Fixed
jobs and timeouts bound running compute; report recorded execution separately
from an actual invoice, including interruption limitations. Do not alter other
apps or jobs. Stop this experiment's completed apps and publish a full handoff.

Implementation references:
[Random Forest](https://scikit-learn.org/1.7/modules/generated/sklearn.ensemble.RandomForestRegressor.html),
[MLP](https://scikit-learn.org/1.7/modules/generated/sklearn.neural_network.MLPRegressor.html),
[deep copy](https://docs.python.org/3.12/library/copy.html).
