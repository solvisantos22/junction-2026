# AfterQuery readiness after the 14 November update

Updated 14 November against Kristján's delivered Harbor/model evidence
(`180e504`), Manh's dynamic service/controller (`fb9ae07`, `b4bdd2e`) and the
[isolated dynamic experiment](lightlag-experiments.md) (`0bc0d43`). Organizer
requirements still come from the team's [record of Ved's 01:35 announcement](afterquery-update-2026-11-14.md).
This update does not claim a fresh read of logged-in Discord or prize pages.

**The basic submission path is demonstrated: Harbor, a real model run and a
valid reward are recorded. The research gap is still unproven.** Claude matched
the reference at 1.0 on the original task. The next milestone is a real model
playthrough of the harder, time-pressured experiment. Lightlag and final rules
remain provisional.

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
  controller scored 1.0 in a direct delay-0 control. No model result on these
  settings yet.
- A [replay viewer](../viewer/README.md) for the original runs is delivered;
  adapting its presentation to a future dynamic model result remains separate.

## Gaps that matter now

| Priority | Gap | Concrete completion evidence |
|---|---|---|
| 1 | **Actual model on the harder task.** The original mission is already solved by Claude. | Run the frozen seed-500 `rush` task with a real model, preserve model/agent versions, limits, cost, score, transcript and replay. Local `.env` was created with a blank `ANTHROPIC_API_KEY`; the user will fill it. |
| 1 | **Usable API access for this worktree.** User reports individual Claude API credits obtained and team Gemini application submitted. Older sponsor notes still record Sölvi's Claude grant as pending; neither a key nor a new balance has been independently verified here. | Load the user-supplied local key and distinguish successful inference from authentication/credit errors. Gemini application is not confirmation of an available balance. Modal's confirmed compute grant is separate. AfterQuery supplies no inference credits. |
| 2 | **Evidence for a general reasoning/control gap.** Seed 500 only separates scripted strategies so far. | Compare the real agent, KF + MPC, blind plan and capable whole-leg-waiting baseline under identical rules; add a delay-0 model control and repeated/predeclared seeds as appropriate. Keep infrastructure errors separate from poor decisions and retain negative findings. The new one-log minimum does not cancel earlier judging-rerun requirements. |
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

1. Use the [experiment handoff](lightlag-experiments.md) for the first harder
   model run. The original `harbor/lightlag/`, simulator and teammate controllers
   were preserved; experiment tasks are generated outside the checkout.
2. Keep the task's source commit/file hashes fixed during comparisons. Manh's
   newly delivered controller collection must not silently replace this reference.
3. Let real model evidence guide the next difficulty experiment. Scripting stays
   available; additional physics or optional training are not prerequisites.
4. Keep [prize evidence](prize-evidence.md) alongside delivered work, with accurate
   Claude Code/Codex/provider attribution. Credit redemption is not a prize entry.

Still unknown: exact judging model/version/effort and resource limits, this
worktree's working API access, current additional-prize entry/form details and
later organizer announcements. This update submits no entry and chooses no
final project rules.
