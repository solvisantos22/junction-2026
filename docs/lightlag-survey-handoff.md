# Six-region survey: decision and handoff

The approved follow-up is complete. The larger environment passes the structural
check but fails the held-out information-value gate. Keep it as experimental
code/evidence; do not promote it to the canonical task or spend model credits
under this protocol. Project/rules choice remains with the team.

## What shipped

- `lightlag_survey/`: six regions, fourteen targets, two imperfect inspections,
  exact delayed sample information, and unchanged physical rover rules.
- Separate `lightlag_expedition/reference_v2.py`: overlap-aware scheduling and a
  guarded energy forecast, shared across all acquisition controls. Frozen original
  reference/experiments and teammate simulators/controllers/viewers are preserved.
- A sealed development/check runner, full retained public transcripts and hidden
  evaluator replays, all regressions, source hashes and explicit error handling.
- Sixty relevant tests across mechanics (22), final reference (25), repair runner
  (3) and study runner (10). Root's final combined reference/runner run passed 38;
  mechanics passed 22 separately. Independent code reviews cleared all blockers.

## Results that determine the decision

[Full report](lightlag-survey-experiment.md) and [predeclared gate](lightlag-survey-gate.md).

| Held-out policy | Mean raw score | Alive and home |
|---|---:|---:|
| Adaptive | 9.96250 | 32/32 |
| No inspection | 9.79219 | 32/32 |
| Entropy | 10.09687 | 32/32 |
| Development-selected fixed r5+r6 | 9.80156 | 32/32 |

All 576 development and 128 check episodes complete and reconstruct. Every rover
returns home alive. Six regions are competitive on three development maps and
adaptive samples all six across cases, but check gains miss all three thresholds.
Adaptive uses r2+r6 in every check case. More choices have not established useful
adaptive selection; a simple policy remains competitive.

The reference repair itself is a tradeoff: new reference 7.17031 versus old 7.68594
on 32 old-map development cases, but deaths 1→0 and alive-home 30→32. The first repair
attempt was worse still on safety; both 128-case versions are retained. The new
no-probe reference improves 6.24375→7.12344. No claim of universal improvement.

## Frozen evidence and inputs

- [First repair regression](lightlag-runs/survey-reference-repair-v1/): 128 cases,
  original source `584809a`; unchanged.
- [Guarded repair](lightlag-runs/survey-reference-repair-v2/): 128 cases,
  source `6192e8e`; artifact/source hashes and all sample/grade arithmetic audited.
- [Runtime smoke](lightlag-runs/survey-timing-v1/): development map 0/seed 100,
  .517 seconds including replay reconstruction; outcome retained, no tuning.
- [Development](lightlag-runs/survey-development-v1/): maps 0–3 × seeds 100–107 × 18
  policies, 576 cases; launch/source provenance `4f3a472` (consumed implementation
  identical to `6192e8e`). Selected pair r5+r6 by greatest mean raw score.
- [Held-out check](lightlag-runs/survey-check-v1/): maps 4–7 × seeds 200–207 × 4
  policies, 128 cases. Source/config/selection seal pushed in `6760d3c` before any
  check rollout. All sources remain unchanged throughout both matrices.

Check inputs are now used. Do not tune and rebrand a rerun on them as validation.
Any replacement needs a new explicit protocol and unused check inputs. Prior
geometry-only tests cover 0–99; distinguish that from outcome exposure. Seeds
with the same numbers in another generator/profile are not automatically the
same worlds; document namespaces and sources rather than assume independence.

## Interpretation and next work

No paid model ran on the survey, so this is not a model failure. The comparator
is a bounded public heuristic, not an optimum: four-target planning, batched
probes, approximate hypothetical sample success/pose and no forecast of later
fixes or undiscovered positions. The check is four maps crossed with eight
quality/noise draws, not 32 independent maps and not a significance claim.

The next design should make information change an important commitment. Before
building another larger map, specify the commitment, what remains uncertain,
which observation can change the choice, and the science lost by a plausible
fixed choice. Verify this with a small exact decision model and strong shared
controls, then embed it in the rover. Avoid adding regions simply to increase
choice count. This is a proposal, not a selected rule or implemented feature.
A concrete candidate is four camps with two nonrecoverable drilling deployments
and two inspections, with public stakes varying by mission. The first exact model
must show that which inspection is useful changes with context or earlier evidence,
and that scouting cannot cheaply reveal everything before investment. This is
unbuilt; adding these rules alone would not establish frontier-model difficulty.

Saved traces expose a comparator limitation too: adaptive opens with two
inspection-only commands in every development/check case, although it can
consider productive prefixes. It samples fewer regions than no-probe on check
(3.71875 versus 4.0 per episode) and has more failed/late samples (9/9 versus 3/3).
These are associations, not a causal ablation. Repair or replace that bounded
value estimator in a future protocol before claiming the environment itself
makes information unhelpful; do not force overlap merely to improve these seeds.
Initial standalone region values/rankings are identical across check cases,
even though all regions are feasible. A next protocol should demonstrate that
public context changes which observation is useful before any model call.

Kristján's [Live research](lightlag-live.md) independently warns against relying
on a hand-played navigation gap: a saved Opus autopilot ties the reference on 200
fresh maps. Keep scripting explicitly available in future model tasks. Manh's
weak-GPS work tests passive sensor fusion and remains a separate teammate axis;
this survey does not validate or invalidate it.

## Credits and ownership

No new API calls or spending in this follow-up. Historical known shared reported
usage remains $13.882161, nominally $1.817839 below the user's earlier $15.70 allowance;
this is not a live provider balance. Kristján separately reports about $9.15 on
his key in Live; no shared-credential identity is established by those docs.
No six-region protected model package was needed because the free gate failed.

Independent artifact audits pass for both repair versions and all 704 survey
episodes; additive reports sit beside the preserved manifests. The check seal
was independently matched to its published pre-run commit.

Claim released with the verified final push. Future work should claim a narrow scope
in TEAM_STATUS before editing; do not change frozen artifacts or the shared
physics to repair this result. Decisions and failed outcomes are part of the
handoff, including the first scheduling regression and the failed check.
