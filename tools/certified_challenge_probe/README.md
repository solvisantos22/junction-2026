# Certified sample-chain probe

This is an isolated research probe, not a playable environment or Harbor task.
It evaluates a **collect → process → transmit** mission. All opportunities,
durations, shelf lives, values and capacities are public. No model/API calls.

The rover, lab and radio each handle one operation at a time. At most two of
those machines can draw power simultaneously. Two cold-storage slots hold
unprocessed samples; two memory slots hold processed data until transmission
finishes. Value is earned only by completing a sample's entire
chain before its delivery deadline. Samples have heterogeneous values.

Time is an integer and all intervals are half open `[start, end)`. Cold storage
is occupied from collection completion until lab start. Memory is occupied
from lab completion until transmission completion. The lab must finish before
the sample's shelf life expires, measured from collection completion. There is
no travel model, sensor noise, live clock, hidden state or neural reference.

`model.py` generates public instances and independently reconstructs each plan
one tick at a time. `search.py` enumerates feasible complete chains and uses
branch and bound over them. Its optimistic bound ignores conflicts between
remaining jobs, so completing the search establishes the optimum. Hitting the
node limit is explicitly **uncertified**, never relabelled as a proven optimum.
The winning plan is a feasibility witness; the upper-bound argument and
completed exhaustive search establish optimality. This is not a proof-assistant
certificate or an independently verified production solver.

Controls are four greedy priorities (value, deadline, value per operation time,
and opportunity scarcity), their best-of-four portfolio, and a generic beam
search retaining 64 partial schedules. The portfolio is realistic because an
agent can validate several candidate schedules before selecting one. None of
these controls is an LLM or a learned policy.

## Verification and frozen free check

```sh
python3 -m unittest discover -s tests/certified_challenge_probe -v
python3 -m tools.certified_challenge_probe.study --split development --start 0 --count 12 --jobs 8 12 --output tools/certified_challenge_probe/results/development.json
python3 -m tools.certified_challenge_probe.study --split check --start 30000 --count 24 --jobs 8 12 --max-nodes 1000000 --output tools/certified_challenge_probe/results/check.json
```

The ten tests include independent brute-force optima on eight tiny instances,
temporal boundaries, invalid plans, power/storage constraints, and 500 random
candidate sequences checked against resource masks and the separate replay.
No third-party package is needed.

Development used seeds 0–11 at each size (24 cases). Before opening check data,
the rule is fixed: a candidate merits a paid pilot only if all check references
prove optimal within the declared limit, all plans replay validly, the greedy
portfolio averages at most 90% of the optimum, and beam search averages at most
95%. A threshold is a project screening choice, not a statistical guarantee of
an LLM gap. The 12-job development beam score, 96.80%, already fails it. The
fresh check is cheap validation of that conclusion, not a rescue search.

The check range is seeds 30000–30023, both sizes, with a one-million-node cap.
All instances and results are retained; there is no rejection sampling or
selection based on baseline/model scores. The same numeric seed at two sizes
does not create two independent statistical observations. Summaries are
descriptive; no independence-based confidence interval is claimed.

JSON artifacts retain full public missions, all plans, raw values, search
status, timings, configuration and SHA-256 source hashes. Timings and the Python
version can differ between machines. Scores, plans and search counts should
reproduce on the same implementation. Counts include every case; normalized
scores are only defined for certified, nonzero optima, with exclusions explicit.

See [research and decision](../../docs/research/2026-11-14-certified-challenges.md).

## Result: do not promote this version

All 48 check references prove optimal and all 336 saved policy records replay
validly (including 48 portfolio records reusing a greedy plan). The eight-job
beam mean is **99.35%** of optimum; the twelve-job beam mean is **97.29%**. The
best-of-four greedy portfolio reaches **95.74%** and **90.41%** respectively.
Both sizes fail the frozen difficulty gate. The prototype demonstrates a
reliable exact reference, but does **not** establish an agent weakness. No paid
model test or full environment build follows from this result.

Check data is now used. Further development requires a new version and fresh
check range. The retained protocol and source hashes were published in
[`465d91e`](https://github.com/solvisantos22/junction-2026/commit/465d91e)
before the check was run.
