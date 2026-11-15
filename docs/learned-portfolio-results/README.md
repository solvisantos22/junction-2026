# Modal learned planner: a small measured gain

**Extra Trees improved the reference's mean score from 49.9782% to 50.4627% on
96 fresh worlds**, a gain of **0.4845 percentage points** (paired 95% interval
**+0.2679 to +0.7206 pp**). Both methods returned home alive on all 96 worlds.
The gain passes the positive-interval, return, survival and validity checks but
falls below the predeclared **1 percentage point** practical-improvement target.
`confirmed: false` in the result refers to that combined gate. **The frozen
reference remains unchanged.**

This model chooses one of 12 planner strategies once at tick 140, using 49
features derived from public map/telemetry and the pilot's belief. The team's
existing pilot still performs navigation and estimation. Three classical models
were trained on Modal. The experiment generated **3,264 production missions**:
2,304 training, 576 validation and 384 fresh evaluation, plus 12 smoke missions.

## Fresh comparison

| Method | Mean score | Gain vs reference (pp) | Paired 95% interval (pp) | Home/alive | Deaths |
|---|---:|---:|---:|---:|---:|
| Frozen reference | 49.9782% | — | — | 96/96 | 0 |
| Extra Trees (primary) | 50.4627% | +0.4845 | +0.2679 to +0.7206 | 96/96 | 0 |
| Ridge | 49.7010% | -0.2772 | -1.5339 to +0.4721 | 95/96 | 1 |
| Fixed aggressive strategy | 49.4766% | -0.5016 | -2.1741 to +0.6620 | 94/96 | 2 |

Extra Trees scores higher on **49** maps, ties on **40**, and scores lower on
**7**. Its interval remains positive after the declared three-comparison
adjustment: **+0.2250 to +0.7777 pp**. No method made an invalid tool call or
raised a controller error. Extra Trees used 49.53 CPU seconds per mission versus
45.52 for the reference, an 8.8% increase including the changed planning behavior.
[Full statistics and gates](final/summary.json), [independent statistics audit](final/summary-audit.json).

The learned choice helped on two concrete maps where the fixed aggressive
strategy died. On world 562006, Extra Trees chose `balanced` and returned home
with 55.36%; on 562054, it chose `refresh` and returned home with 45.95%.
Ridge died on world 562068 after choosing `legs_fast`; Extra Trees chose
`balanced` and returned home with 53.00%. These cases describe this test set.
[All cases and strategy consistency](final/strategy-consistency.json).

Extra Trees selected `aggressive` on 69 fresh worlds, `balanced` on 15,
`refresh` on 8 and `arrival_wide` on 4. Learning improved the measured reference
result, while this study does not establish a large gain or broad safety guarantee.

## Training and selection

Training uses **192 worlds (560000–560191)**, with all 12 strategy outcomes per
world. Each fitted example has 49 public features and 11 reward differences from
baseline. **48 validation worlds (561000–561047)** choose among three algorithms
and thresholds 0, .002 and .005. Their outcomes do not fit weights.

| Validation method | Mean score | Gain vs reference | Home/alive |
|---|---:|---:|---:|
| Frozen reference | 50.1011% | — | 48/48 |
| Extra Trees, threshold 0 | 50.7287% | +0.6276 pp | 48/48 |
| Ridge, threshold 0 | 50.6527% | +0.5516 pp | 48/48 |
| Gradient boosting, best threshold .005 | 50.2483% | +0.1472 pp | 48/48 |
| Best fixed strategy: aggressive | 50.7567% | +0.6556 pp | 48/48 |

Extra Trees is a 400-tree regressor; histogram gradient boosting fits 11
regressors; ridge uses standardized inputs. Hyperparameters and RNG seed were
fixed beforehand. Three asynchronous Modal fit calls were submitted before
waiting for any result, with a cap of three fit workers. All succeeded and their
saved predictions reproduce with local refits. Modal's call graph omits container
IDs, so it cannot confirm the exact number of fit containers.
[Fit receipt](fit-receipt.json), [call graph](fit-call-graph.json), [model audit](model-audit.json).

Extra Trees and ridge, both at threshold zero, were frozen in
[selection.json](selection.json), published to `main` in **51e33ba** before fresh
worlds **562000–562095** opened. No weights, strategy, threshold or selection was
changed after that. Gradient boosting was not selected for fresh evaluation.
[Selection audit](selection-audit.json), [protocol](../learned-portfolio.md).

The hindsight best choice among these 12 strategies gains only **0.7654 pp** on
training and **0.8634 pp** on validation. This limits the opportunity within this
particular strategy family; it does not bound other controllers. Extra Trees'
validation prediction MSE is below the zero-improvement predictor; gradient
boosting and ridge are above it. [All profile scores, thresholds, prediction
errors and choices](diagnostics.json).

## Verification

- Seven focused tests passed: original-pilot parity on the smoke world, common
  prefixes, public-data boundary, seed exclusions, decision thresholds, incomplete
  matrices, and fitting/checkpoint round trips for all three models.
- Every data/fresh physics replay matches its original full hash on Linux:
  **3,264 missions, 1,301,528 commands, 1,374,144 states**. The 12 smoke replays add
  4,874 commands and 5,052 states. [Data audit](data/cloud-audit.json),
  [fresh audit](final/cloud-audit.json), [smoke audit](smoke/audit.json).
- Local replays independently match all production grades, commands, states and
  telemetry. 264 full hashes differ only in decorative `world.features` metadata.
  A retained example differs by `1.11e-16` in one illustrative terrain field.
  [Data local audit](data/audit.json), [fresh local audit](final/audit.json),
  [cross-platform diagnosis](data/cross-platform/diagnosis.json).
- All 192 fresh learned decisions were recomputed. Every fresh world has identical
  pre-switch commands/features across methods. All 109 comparisons where methods
  chose the same strategy have exactly identical full replays.
- The original full-budget reference matches the baseline wrapper exactly on
  Linux and separately on macOS. Comparing controllers across platforms directly
  gave three differing commands on the checked map, with the same score; full
  controller parity is therefore checked on the same platform.
  [Linux original-reference repeat](reference-parity.json),
  [macOS parity](reference-parity-macos.json). A complete Linux Extra Trees repeat
  also matches its saved decision and replay exactly: [receipt](final/controller-repeat.json).
- Independent calculations reproduced the selected thresholds, all reported
  statistics, bootstrap intervals and final gate outcome. Feature construction
  and control logic are source-pinned and covered by selected full-controller
  repeats; they were not independently reconstructed for every mission.

## Modal execution and recovery

The run reached **100 simultaneous mission workers**, then used 96 to leave slots
for verification. The original data app lost its result stream during a system
DNS outage after 833 outcomes were archived. Those outcomes were retained and
only missing jobs were resubmitted. A second attempt timed out before app
creation. The optional `dns_run` launcher uses public DNS inside its process,
with normal TLS hostname verification and no OS setting changes.
[Original interruption](data/attempts/01/failure.json),
[startup failure](data/attempts/02/failure.json). User-code retries were zero;
Modal still restarted containers after platform preemptions. Completed but
unreceived work may have been duplicated after the lost stream.

- Data: original `ap-tctysvmd3CxtowroSpSlM0`, resumed `ap-vmIsFVOKPZVhhmunxtJuuB`.
- Fits: `ap-LZbxrxLV7aLLJ4ktdoQxps`.
- Fresh: `ap-kBigQmFdEX9LgbCt0dQpbA`; 384 missions completed in 277 seconds.
- All source/job grids, app/call IDs, checkpoints, accepted commands and outcomes
  are retained. Training artifacts retain replay digests; fresh artifacts include
  complete replays. No campaign, MAX reserved world or teammate learner was changed.

Recorded controller execution totals 154,565 wall seconds and 151,944 CPU seconds.
At the rates recorded in the protocol, its CPU/memory allocation estimate is
**$2.37**. **This is not the total bill**: it excludes environment initialization
and serialization, lost or preempted work, startup/idle time, fits, audits, builds,
storage and network. The remaining credit balance was not checked. No GPU or
LLM API call was used.

## Artifacts and local verification

The selected checkpoint is [models/extra_trees.pkl](models/extra_trees.pkl), with
its digest and feature order in [metadata](models/extra_trees.json). Ridge and
gradient-boosting checkpoints are retained beside it. Use the hash-checked loader
and the saved selection spec with `lightlag_learned_portfolio.policy.play` for an
opt-in experiment. The canonical reference and Harbor tasks are unchanged.

With Python 3.12, NumPy 2.3.4, scikit-learn 1.7.2 and SciPy 1.18.1, local checks are:

```sh
python -m tools.learned_portfolio.audit selection
python -m tools.learned_portfolio.audit summary
python -m tools.learned_portfolio.audit switches
python -m tools.learned_portfolio.audit final
```

These commands verify saved evidence and make no cloud call. Re-running cloud
stages requires Modal and its authenticated profile; retained completed stages
are not overwritten.
