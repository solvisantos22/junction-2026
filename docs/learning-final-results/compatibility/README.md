# Final Traverse controller compatibility

Both prespecified compatibility gates pass. All six completed scratch policies
were tested unchanged, using deterministic argmax, on previously used training
maps 80000–80007 under the old and final controllers. Greedy supplies context.
This is **112 unique cases**, not fresh evaluation or additional training.

| Policy | Cases per controller | Old mean | Final mean | Home, old/final | Gate |
|---|---:|---:|---:|---:|---|
| PPO, three initializations | 24 | 0.405241 | 0.405241 | 24 / 24 | Pass |
| Replay, three initializations | 24 | 0.354855 | 0.354855 | 24 / 24 | Pass |
| Greedy | 8 | 0.363907 | 0.363907 | 8 / 8 | Context only |

Per initialization, all eight cases return home under both controllers:

| Initialization | Old mean | Final mean |
|---|---:|---:|
| PPO 17 | 0.407313 | 0.407313 |
| PPO 29 | 0.413724 | 0.413724 |
| PPO 43 | 0.394687 | 0.394687 |
| Replay 17 | 0.375242 | 0.375242 |
| Replay 29 | 0.311370 | 0.311370 |
| Replay 43 | 0.377954 | 0.377954 |

Every case is alive with zero invalid calls. Each algorithm's gate required
mean new-minus-old reward at least −0.01, at most one fewer return, and no
deaths or invalid calls. No policy selection or tuning followed these results.

**The controllers are not behaviorally identical.** All 56 matched pairs have
identical rules, grades, decision observations and chosen actions. However,
28 pairs have different commands and physics traces. Their first differing
command occurs while the selected goal is base, between ticks 329 and 401.
Their learning transitions differ only in the final next observation. The
other 28 pairs have identical complete episodes apart from wall-clock timing.
The final controller's changed home-driving behavior is real even though it
does not change these scores. Keep old experiments under their original pins.

The [freeze](freeze.json) was written before cases. It embeds every policy,
pins both source trees, policy and training-report hashes, this evaluator,
the protocol and runtime versions. The old tree is the original frozen
training source; the new existing packages match `496ba56`. New final-training
packages are outside this compatibility import closure.

Each compressed case contains the full replay, transitions, rules and actual
loaded Python-module paths with hashes. Old and new cases used independent
fresh interpreters, with the source root selected before project imports.
All 112 cases passed independent command/acknowledgement and 420-tick physics
reconstruction, grade checks, retained-policy choice reconstruction, and a
complete deterministic rerun through the public controller. Thus collection
executed 224 controller runs and 112 physics reconstructions of the same
112 cases; it did not open additional maps. Exceptions would be retained with
an incomplete result; there were none.

The [report](report.json) holds all case hashes and aggregate scores. The
[verification](verification.json) checks all artifact identities, recorded
audit successes, import proofs, paired differences and summary arithmetic.
Reproduce that retained-artifact check without episodes or cloud calls:

```sh
python docs/learning-final-results/compatibility/verify.py
```

The four focused compatibility tests pass, including a real used-seed-1
worker and a synthetic check that return failures cannot be hidden by score
improvement. Maps 2026–2029 and final maps 82000–82039 were never opened.
Passing supports the separately declared final-version experiment; it does
not establish universal controller equivalence, fresh generalization, or an
RL improvement over the reference.
