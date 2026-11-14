# Fresh-world learning results

**Learning transfers to fresh maps, but neither method demonstrates an advantage over greedy, and both remain below the frozen reference. Keep the reference.** All 760 cases and their retained physics, scores, policy choices and summary arithmetic passed the frozen audit. The self-contained policy selection was published in `d81fa88` before worlds **82000–82039** were opened.

| Policy | Mean reward | Home / alive | Cases |
|---|---:|---:|---:|
| PPO initial | 0.082657 | 120 / 120 | 120 |
| PPO at 2048 | 0.367765 | 119 / 119 | 120 |
| PPO latest: 8192 each | 0.359237 | 117 / 117 | 120 |
| Replay initial | 0.082657 | 120 / 120 | 120 |
| Replay at 2048 | 0.350202 | 120 / 120 | 120 |
| Replay latest: 8192, 8192, 2048 | 0.362939 | 120 / 120 | 120 |
| Greedy, same navigator | 0.379921 | 40 / 40 | 40 |
| Frozen beam reference | 0.508170 | 40 / 40 | 40 |

Every learned row averages all three initialization seeds on the same 40 maps. Replay seed 43 stopped training at 6880 and retains its last completed declared checkpoint, 2048. Its shared latest/matched role is evaluated once, so this table's roles reuse cases; there are 760 unique cases, not the sum of every displayed row. All invalid-call counts are zero.

## Paired comparisons

Differences below are **percentage points**. Each bootstrap first averages the three initialization scores within each map, then resamples the 40 maps (10,000 draws, seed 17). Intervals are conditional on these three training initializations; they do not estimate variation across arbitrary future training seeds.

| Comparison | Mean difference | Paired 95% percentile interval |
|---|---:|---:|
| PPO latest − initial | +27.658 | [+25.140, +29.831] |
| Replay latest − initial | +28.028 | [+26.656, +29.459] |
| PPO latest − matched 2048 | −0.853 | [−2.665, +0.791] |
| Replay latest − matched 2048 | +1.274 | [+0.228, +2.261] |
| PPO latest − greedy | −2.068 | [−4.752, +0.156] |
| Replay latest − greedy | −1.698 | [−3.455, +0.069] |
| PPO latest − beam | −14.893 | [−17.202, −12.860] |
| Replay latest − beam | −14.523 | [−15.874, −13.217] |

The fresh replay gain over 2048 is retained even though its development continuation gate failed. It does not retroactively qualify another training stage, and its latest row has unequal training budgets. PPO's numerically better 2048 result does not replace its predeclared latest checkpoint. The greedy intervals crossing zero do not establish equivalence; they supply no evidence that these learners outperform greedy.

## Failures and interpretation

All three latest PPO policies lose the rover on world **82001**; PPO seed 29 at 2048 also loses it on **82024**. These four cases score zero and remain in every mean. The corresponding latest PPO home/survival count is 117/120, not a perfect-return result. Replay, greedy and beam return alive in every retained fresh case. The 736 development validation episodes had no such failure, so their perfect return record did not guarantee fresh-map safety.

[Post-hoc saved-trace diagnosis](failure-notes.json) finds all four deaths on the home leg after queued drives deplete the battery. The three latest PPO controllers on 82001 follow similar return corridors and die 20.65–23.46 m from base; PPO29 at 2048 on 82024 dies 6.02 m away. Their saved home forecasts were feasible. This motivates investigating forecast/controller-execution mismatch on development maps; it does not establish a cause, justify retuning on these final worlds, or alter the frozen result. The diagnosis checks saved artifacts only, with no additional policy or simulation runs.

These are small learned goal selectors above a hand-written navigation and feasibility scaffold. Their substantial improvement over initialization is evidence of learning in that system; it is not a learned-controller win over the stronger planner or an LLM post-training result. The [exact submission-campaign comparison](../campaign/README.md) is separate: no LLM played these 40 fresh evaluation worlds.

## Evidence and reproduction

- [Original frozen manifest](../policy-freeze.json), [manifest copied into this evaluation](freeze.json), [all cases and canonical summary](report.json), [760-case audit](audit.json).
- [Method means, per-seed outcomes and paired-map intervals](method-summary.json), including report/freeze/audit/analysis source hashes.
- [Training termination and cost](../fit/README.md), [development learning curve](../figures/learning-curve.png). The curve uses different, reused validation maps and must not have these fresh reference scores overlaid as if matched.

Reproduce the physics/choice audit from source `becbf3e` with Python 3.12.16, NumPy 2.3.4 and Torch 2.9.1, using `tools.learning_final.evaluate --audit .../report.json --output NEW_AUDIT.json` and single-threaded numerical libraries. The audit reconstructs mission physics and grades and recomputes choices on retained observations. Observation generation, choice-to-command linkage and original beam planning remain source-pinned. Production optimizer learning is not reconstructed by this audit.

`tools.learning_final.summarize --report .../report.json --audit .../audit.json --output NEW_SUMMARY.json` validates those hashes and derives the method-level table without executing policies or opening maps. Three focused tests cover duplicate/missing evidence, averaging before bootstrapping, shared checkpoint roles and rejection of an unrelated audit. An independent calculation reproduced all 760 artifact hashes and the paired statistics.
