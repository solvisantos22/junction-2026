# AfterQuery readiness after the 14 November update

Updated 14 November against Kristján's delivered Harbor/model evidence
(`180e504`), Manh's dynamic service/controller (`fb9ae07`, `b4bdd2e`) and the
[isolated dynamic experiment](lightlag-experiments.md) (`0bc0d43`). Organizer
requirements still come from the team's [record of Ved's 01:35 announcement](afterquery-update-2026-11-14.md).
This update does not claim a fresh read of logged-in Discord or prize pages.

**The basic submission path is demonstrated, and the fixed comparison now has
three auditable model deficits alongside three model wins and two ties.** All
[eight predeclared additional attempts](lightlag-fixed-seed-comparison.md) are
complete. The reference has higher mean reward in both profiles; two battery
failures strongly affect those means. Each run replays exactly with no
infrastructure findings. The next priority is repeatability, reference strength
and a clear decision-focused demo. Lightlag and final rules remain provisional.

## What is now demonstrated

- Deterministic simulator, fixed-horizon scoring, delayed public tools and
  [480 scripted comparison episodes](lightlag-reference-results.md).
- [Real Docker/Harbor runs](lightlag-harbor.md): original reference 1.0, no-op
  0.0, OpenCode 1.19.5 / Claude Opus 5.5 **1.0**, seed 7, delay 3. The model run
  recorded $0.31 and 27 tool calls. This is Kristján's evidence, not a new run by
  this audit.
- The simulator-side finish/collect hook, protected artifacts, separate verifier
  and five-tool discovery worked in that original model run.
- Manh's delivered [dynamic profiles, KF + MPC and MCP entry point](lightlag-dynamic-pilot.md).
  His [additional controller collection](../lightlag_dynamic/manh_controllers/README.md)
  landed in `b867839` during this update; it is not part of the frozen experiment.
- The [rush experiment](lightlag-experiments.md), seed 500, delay 3, now works
  through Harbor too: reference 1.0, blind 0.571429, whole-leg waiting 0.535714,
  no-op 0.0. All four reached tick 50 and matched direct runs. The waiting
  controller scored 1.0 in a direct delay-0 control. The fresh OpenCode 1.19.5 /
  Claude Opus 5.5 run also scored **1.0**, with 30 rover tool calls and reported
  cost **$0.4821436**. All six samples were on time; no execution error occurred.
- The [matched noisy pilot](lightlag-noisy-experiment.md) also produced Claude
  **1.0** / reference **1.0**, with all six samples on time, 29 rover tool calls,
  no execution exception and reported cost **$0.4642194**. The two new model
  attempts together report **$0.946363**. The noisy waiting baseline scored
  0.267857 and the blind plan 0.571429; neither predicts this model's result.
- [Fixed seeds 501–504](lightlag-fixed-seed-comparison.md): eight matched Harbor
  references, 32 direct controls and **8/8 model attempts** retained. Mean
  Claude/reference reward: rush **0.554808 / 0.724679**, noisy
  **0.544071 / 0.690224**. Three model wins, two ties, three deficits. All eight
  audits reproduce exactly with no infrastructure findings. Two energy-budget
  failures and a command-queue deficit have packet/rule pointers and explicit
  continuation checks. Reported API usage **$3.3513574** for this set;
  **$4.2977204** including this chat's two seed-500 pilots.
- A [replay viewer](../viewer/README.md) for the original runs is delivered;
  adapting its presentation to a future dynamic model result remains separate.

## Gaps that matter now

| Priority | Gap | Concrete completion evidence |
|---|---|---|
| 1 | **Repeatability and reference strength.** The completed set contains three deficits, three model wins and two ties; two battery deaths strongly affect the average. | Repeat the identified failure cases with a fixed fresh-attempt budget and retain recoveries. Compare the team's newer reference separately on the same seeds; preserve the frozen comparison. Do not tune rules solely to defeat saved traces. |
| 1 | **API budget tracking.** The user-supplied Claude key worked for the real run. User reports individual credits obtained and team Gemini application submitted; grant source and remaining balances are not independently verified. | Record reported cost per run and keep credentials local. Gemini application is not confirmation of an available balance. Modal's confirmed compute grant is separate. AfterQuery supplies no inference credits. |
| 2 | **Evidence for a general reasoning/control gap.** Specific energy/queue failures are audited, but there are only four maps per profile and one model attempt per map. | Use capable baselines and fresh predeclared confirmation data after any tuning. Keep infrastructure errors separate from poor decisions and retain negative findings. The new one-log minimum does not cancel earlier judging-rerun requirements. |
| 2 | **Final mission and demo.** The canonical task still uses the original profile; the generated experiment intentionally does not replace it. | Choose/version a profile after model evidence. Coordinate any canonical-task update with its owner, sync generated copies, and show the objective, decisive actions and reward in a playthrough. Exact judging model/budget remain unresolved. |
| 2 | **Submission and license.** The platform entry remains the recorded editable draft; prize selections/forms and a repository license are not confirmed. | Check final track/prize entries and any separate forms. The public Junction FAQ says submissions are open-sourced under MIT; confirm the team's terms/license treatment before finalizing. |

The reward adapter uses `raw_score / max_available_value`, validates finite
values and a positive denominator, and rejects malformed results. In the dynamic
task the maximum includes all generated targets, including later discoveries;
late samples earn the published reduced value. This is mission-value scaling,
not reference normalization. Preserve reference ratios as a separate metric.

Harbor's generic verifier accepts text or JSON rewards and prefers JSON when
both exist; AfterQuery's specific requirement is the single-number
`/logs/verifier/reward.txt`. The separate verifier receives protected artifacts
from the simulator after the agent stops. [Official verifier documentation](https://docs.harborframework.com/tasks/verifier).

The public event schedule previously checked on 14 November lists final
submission at **10:00 Sunday 15 November**, event local time. Recheck the platform
before final submission. The same page describes MIT submissions and tech prizes
accompanying any main track. [Junction schedule and FAQ](https://2026.hackjunction.com/).

## Coordination and next steps

1. Use the completed [fixed seed comparison and handoff](lightlag-fixed-seed-comparison.md)
   for a fixed-budget repeatability check and a decision-focused demo. Source/task
   hashes and mixed outcomes are preserved; canonical-task changes remain
   coordinated with the existing owner.
2. Keep the task's source commit/file hashes fixed during comparisons. Manh's
   newly delivered controller collection must not silently replace this reference.
3. Keep the current rules for the repeatability check. Manh's new real-time
   clock/controller remains a separate proposal, not part of this evidence.
   Scripting stays available; further physics or training is not a prerequisite.
4. Keep [prize evidence](prize-evidence.md) alongside delivered work, with accurate
   Claude Code/Codex/provider attribution. Credit redemption is not a prize entry.

Still unknown: exact judging model/version/effort and resource limits, this
team's remaining API balances, current additional-prize entry/form details and
later organizer announcements. This update submits no entry and chooses no
final project rules.
