# Frozen comparison on the submission campaign

This additional fixed-campaign comparison was requested by Sölvi after discussing the difference between RL validation worlds and the worlds used for the recorded LLM attempts. It uses **2027, 2028 and 2029**, the exact submission campaign, with every arm of policy freeze `d81fa88`. No model, seed or checkpoint will be selected using this result.

The [campaign freeze](freeze.json) binds the parent policy manifest, all 19 arms, source/runtime hashes, and byte-identical copies of the task simulator/reference. Its SHA-256 is `cb1a978bf4e69921dd0e3422c1f0e0c9d0370f4723210ae9b23f5c4c19d8ddd4`. This file and the runner are published before opening campaign cases. There will be **19 complete campaigns / 57 missions**, including initial, matched-2048, latest, greedy and beam. Replay seed 43 shares its latest and matched-2048 artifact.

The runner uses the actual `TraverseCampaign` five-tool API, a fresh controller for each mission, and stops at `campaign_complete`. The score is total raw credit divided by total available value, not an average of mission percentages. Complete mission and campaign replays are retained and audited. This is a local public-tool controller evaluation, not another Harbor/LLM attempt or a fresh generalization test.

Six focused tests pass on already-used worlds 1/2, including eight complete campaign missions and exact standalone/campaign greedy transition comparisons. The final parent-hash hardening also passed both metadata tests. Independent review found no remaining blocker. Training, the original evaluator, the reference and the Harbor task are unchanged.

[Recorded LLM evidence](recorded-llm.json) preserves all seven attempts on task 0.1.0, including source hashes and 135 consistency checks. Opus's four exact rewards average **0.219797486**, best **0.267458101**; Sonnet's two average **0.252793296**, best **0.292597765**. All seven attempts retain EPIPE/nonzero-exit errors; the six Opus/Sonnet attempts completed the campaign. Haiku's zero is length-censored before any advance or uplink. These limitations are not removed by a controller scoring higher. The independently recorded reference is **0.476256983**; verify its reproduction before interpreting the new comparison.

Run with the existing learning runtime from the repository root, preserving the frozen sources:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /tmp/junction-learning-venv/bin/python -m tools.learning_final.campaign \
  --run docs/learning-final-results/campaign/freeze.json \
  --output docs/learning-final-results/campaign/evaluation --workers 6
```

After completion, use `--audit .../evaluation/report.json --output .../evaluation/audit.json`. The audit reconstructs mission/campaign physics, weighted scoring and choices on retained observations; observation generation and controller linkage remain source-pinned. The fresh-world experiment and its results remain separately reported.
