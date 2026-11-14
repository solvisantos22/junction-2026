# Matched results on the submission campaign

**All six latest trained controllers score above every recorded Opus and Sonnet attempt on the exact same campaign.** PPO averages **0.366387** and replay **0.333566**, versus best recorded Opus **0.267458** and Sonnet **0.292598**. This clears Sölvi's requested performance bar for the recorded comparison. The same-navigator greedy control scores **0.367318**, and the unchanged reference scores **0.476257**. The result supports learning and a narrow comparison with recorded agents; it does not establish an advantage over greedy or the reference.

All **19 campaigns / 57 missions** passed the physics, grade, retained-choice and aggregation audit; every rover finished alive at home, with no invalid calls. The new reference exactly reproduces the recorded reference's three raw scores (53.25, 62.5, 54.75), totaling **170.5 / 358**. The campaign freeze was published in **`48a63ee`** before these runs.

| Policy / recorded agent | Mean campaign reward | Observed range across seeds / attempts | Count |
|---|---:|---:|---:|
| Initial controller, each learned method | 0.080074 | 0.000000–0.240223 | 3 seeds per method |
| PPO matched 2048 | 0.362896 | 0.343575–0.396648 | 3 seeds |
| PPO latest, 8192 each | 0.366387 | 0.340084–0.395251 | 3 seeds |
| Replay matched 2048 | 0.331704 | 0.324721–0.343575 | 3 seeds |
| Replay latest, 8192 / 8192 / 2048 | 0.333566 | 0.326117–0.343575 | 3 seeds |
| Greedy, same navigator | 0.367318 | — | 1 deterministic controller |
| Frozen beam reference | 0.476257 | — | 1 deterministic controller |
| Recorded Opus 5.5 | 0.219797 | 0.120112–0.267458 | 4 attempts |
| Recorded Sonnet 5.5 | 0.252793 | 0.212989–0.292598 | 2 attempts |

The weakest of the six latest policies scores **0.326117**, above the best recorded Opus by **5.866 percentage points** and best Sonnet by **3.352 points**. These are observed differences on one fixed campaign, not confidence intervals or estimates of general LLM performance. The mean PPO score is only 0.093 percentage points below greedy; showing greedy alongside it is essential to attributing the learned system's performance honestly.

[Complete campaign report and per-seed results](evaluation/report.json) · [57-mission audit](evaluation/audit.json) · [hash-bound recorded-agent comparison](comparison.json) · [recorded LLM evidence](recorded-llm.json).

## Comparison limits

The trained controllers use hand-written navigation and feasibility logic and had many simulated training missions. The recorded LLMs wrote/adapted their own programs through OpenCode/Harbor; training and compute budgets differ. All six Opus/Sonnet attempts reached campaign completion but retain **EPIPE/nonzero-exit errors**, which remain visible in the evidence. Haiku's zero was length-censored before driving and is excluded from the performance table. No new LLM or Harbor run was conducted for this comparison. The [40-world generalization check](../evaluation/README.md) is separate and includes three deaths among the latest PPO policies; the campaign's perfect return record must not obscure them.

## Frozen setup and reproduction

This additional fixed-campaign comparison was requested by Sölvi after discussing the difference between RL validation worlds and the worlds used for the recorded LLM attempts. It uses **2027, 2028 and 2029**, the exact submission campaign, with every arm of policy freeze `d81fa88`. No model, seed or checkpoint was selected using this result.

The [campaign freeze](freeze.json) binds the parent policy manifest, all 19 arms, source/runtime hashes, and byte-identical copies of the task simulator/reference. Its SHA-256 is `cb1a978bf4e69921dd0e3422c1f0e0c9d0370f4723210ae9b23f5c4c19d8ddd4`. This file and the runner were published before opening campaign cases. The **19 complete campaigns / 57 missions** include initial, matched-2048, latest, greedy and beam. Replay seed 43 shares its latest and matched-2048 artifact.

The runner uses the actual `TraverseCampaign` five-tool API, a fresh controller for each mission, and stops at `campaign_complete`. The score is total raw credit divided by total available value, not an average of mission percentages. Complete mission and campaign replays are retained and audited.

Six focused tests pass on already-used worlds 1/2, including eight complete campaign missions and exact standalone/campaign greedy transition comparisons. The final parent-hash hardening also passed both metadata tests. Independent review found no remaining blocker. Training, the original evaluator, the reference and the Harbor task are unchanged.

[Recorded LLM evidence](recorded-llm.json) preserves all seven attempts on task 0.1.0, including source hashes and 135 consistency checks. Opus's four exact rewards average **0.219797486**, best **0.267458101**; Sonnet's two average **0.252793296**, best **0.292597765**. All seven attempts retain EPIPE/nonzero-exit errors; the six Opus/Sonnet attempts completed the campaign. Haiku's zero is length-censored before any advance or uplink. These limitations are not removed by a controller scoring higher. The independently recorded reference is **0.476256983**; verify its reproduction before interpreting the new comparison.

Run with the existing learning runtime from the repository root, preserving the frozen sources:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /tmp/junction-learning-venv/bin/python -m tools.learning_final.campaign \
  --run docs/learning-final-results/campaign/freeze.json \
  --output NEW_CAMPAIGN_DIRECTORY --workers 6
```

After completion, use `--audit .../evaluation/report.json --output .../evaluation/audit.json`. The audit reconstructs mission/campaign physics, weighted scoring and choices on retained observations; observation generation and controller linkage remain source-pinned. The fresh-world experiment and its results remain separately reported.
