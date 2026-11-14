# Modal learned planner portfolio

Kristján requested parallel cloud training, prioritizing speed, using his roughly
$90 remaining Modal credit. This study trains three classical models above the
frozen normal Traverse reference. It does not change the mission or promote a new
reference automatically. Sölvi's and Manh's learner packages/jobs are separate.

At tick 140 every policy has followed the same reference prefix. It may switch
once to one of 12 fixed planner strategies, using only public map/telemetry and
the pilot's derived belief. Training labels are the final official rewards of
these counterfactual strategies. Hidden simulator values are never features.
Strategies are fixed in `lightlag_learned_portfolio/policy.py`; baseline is an
exact no-op, while `refresh` isolates the cost/effect of forcing a replan.

## Fixed experiment

- Training worlds **560000–560191**: 192 worlds × 12 strategies = 2,304 missions.
- Validation **561000–561047**: 48 × 12 = 576 missions. Their common-prefix
  features must agree exactly. Since there is one decision, validation of a
  learned selector can use the exact corresponding strategy outcome.
- Train an ExtraTrees regressor, histogram gradient-boosted regressors, and a
  standardized ridge regressor, in separate Modal containers. Predict each
  strategy's reward minus baseline; baseline's predicted improvement is zero.
- Use only training data to fit weights. Validation chooses among the three
  algorithms and improvement thresholds 0, .002, .005. Rank by paired mean reward,
  excluding invalid models or any with worse alive/home counts than baseline.
  Select the top two distinct algorithms; the better is the primary candidate.
  If none is eligible, retain the best two as explicitly unqualified diagnostics.
- Freeze all weights, selected thresholds and the best fixed strategy before
  opening **562000–562095**. Evaluate baseline, best fixed strategy, and the two
  selected learners: 96 worlds × 4 = 384 fresh missions.
- Report paired bootstrap intervals, home/alive, invalid calls/errors, profile
  choices, controller CPU/wall time, fit diagnostics and actual Modal call IDs.
  A confirmed improvement needs primary mean gain >=.01, lower paired 95% bound
  >0, no worse alive/home and no invalid calls/errors. Secondary intervals are
  also adjusted for the three comparisons. No settings change after final freeze.
- Keep all results and failed attempts. Training/validation artifacts retain
  accepted commands, grade, public decision features, prefix digest and a digest
  of the complete simulator replay. Fresh artifacts retain complete replays too.
  Replay commands to check grades and replay digests; repeat selected controllers.

## Resources

Up to 100 simultaneous 1-CPU / 1-GiB mission containers, each bounded to 600 s,
with zero automatic retries. Three 2-CPU / 4-GiB fit containers, each <=1,800 s.
3,264 production missions plus a small smoke/verification allowance, no GPUs or
model API calls. This fixed running-compute envelope is below $40 at Modal's
listed CPU/memory rates ($0.0000131/core/s and $0.00000222/GiB/s); it is an
estimate, not an invoice cap, and excludes build/storage/egress. Actual successful
mission runtime should be substantially below the timeout envelope. The user's
remaining-credit figure is user-reported, not a verified balance.

[Modal scaling](https://modal.com/docs/guide/scale),
[published prices](https://modal.com/pricing),
[scikit-learn ensembles](https://scikit-learn.org/stable/modules/ensemble.html).
