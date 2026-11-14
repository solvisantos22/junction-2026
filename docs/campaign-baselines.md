# Retained campaign baseline records

These are the three baseline runs saved by Kristján / Claude Code in local
commit `b5b7ee7`: Harbor campaign task 0.1.0, worlds 2027, 2028 and 2029.
Their 53 original files are published unchanged as an independent evidence
slice. The campaign runtime and its new viewer remain pending compatibility
with the retained RL source manifests; this evidence publication does not
promote that implementation or select it as the team's task.

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
