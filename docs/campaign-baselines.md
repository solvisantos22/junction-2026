# Retained campaign baseline records

These are the three baseline runs saved by Kristján / Claude Code in
commit `b5b7ee7`: Harbor campaign task 0.1.0, worlds 2027, 2028 and 2029.
Their 53 original files were published unchanged as an independent evidence
slice. Kristján subsequently requested the full Traverse branch merge into
`main`, including the campaign runtime and viewer, completed in
[`0130fa6`](https://github.com/solvisantos22/junction-2026/commit/0130fa6).
The saved records and this consistency audit remain unchanged.

| Saved run | Campaign reward | Mission rewards |
|---|---:|---|
| [Reference](lightlag-runs/campaign-reference/) | 0.476257 | 0.459052, 0.508130, 0.460084 |
| [Do nothing](lightlag-runs/campaign-do-nothing/) | 0.000000 | 0, 0, 0 |
| [Stop after the first mission](lightlag-runs/campaign-stop-early/) | 0.148743 | 0.459052, 0, 0 |

Campaign reward is total raw score divided by total available value across
the three missions. Each saved mission finishes at tick 420, alive and home.
The reference's first mission and the stop-early run's first mission have
byte-identical replay records.

Codex checked all 53 files against their original Git blobs, parsed 39 JSON
files and 3,221 transcript rows, and reconciled the nine mission records with
replay results, final state fields, sample credits, campaign totals, run
metadata and Harbor verifier rewards. Per-file SHA-256 values and the result
summary are in [the verification record](campaign-baselines-verification.json).
This checks saved-artifact consistency and byte identity; it is not a new
physics replay, model run or cloud experiment.
