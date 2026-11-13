# AfterQuery readiness after the 14 November update

Checked against repository code through `d2dee96`, including Kristján's Harbor task, which landed during this audit, and the team's [record of Ved's 01:35 announcement](afterquery-update-2026-11-14.md). Public Harbor verifier documentation and the Junction overview were checked on 14 November. This session could not directly reopen logged-in Discord or Junction prize pages: computer-use access to Discord and Chrome was unavailable. Distinguish the recorded announcement from a fresh independent read of the channel.

**We are moving forward, but the submission path is not demonstrated yet. The next milestone is one complete Harbor model playthrough with a valid reward and preserved logs.** More sophisticated physics or a stronger controller can proceed in parallel; they should not become a prerequisite for that first integration test. Lightlag and the final rule set remain provisional.

## What is already usable

- Deterministic simulator, fixed-horizon scoring and delayed public tools.
- Tested scripted controllers, including the stronger adaptive reference from Kristján.
- A shared evaluator with an explicit factory for Manh's dynamic environments.
- [480 recorded scripted episodes](lightlag-reference-results.md), reproducible score rows and replay exports. These are algorithm comparisons, not model playthroughs.
- An [MCP service](lightlag-mcp.md) with stdio/HTTP tests and evaluator-only finish.
- A [Harbor task](lightlag-harbor.md) with instructions, configuration, separate verifier, reference solution and 0–1 reward adapter. Kristján reports lint and plain-process checks; container and model runs remain unverified. This audit ran its standard-library test suite: six tests passed, five SDK/Python-dependent tests were skipped.
- A [dynamic pilot](lightlag-dynamic-pilot.md) with deadlines, discoveries and whole-leg waiting. Manh has claimed further noisy-sensing/Kalman-filter/MPC experiments; those are active work, not delivered evidence at this audit snapshot.

## Gaps that matter now

| Priority | Gap and evidence at this snapshot | Concrete completion evidence |
|---|---|---|
| 1 | **Real Harbor/container execution.** `harbor/lightlag/` now contains the required packaging and reward adapter. It has not been built or run in containers. | Build the images and complete `harbor run` with the reference and no-op; confirm a finite, valid `/logs/verifier/reward.txt` and saved diagnostics. Record/pin the working Harbor, OpenCode and dependency versions. The task handoff reports Harbor 0.25.0 linting. |
| 1 | **An actual model run and usable inference budget.** No model playthrough is recorded in the repository. AfterQuery cancelled its inference credits. | A real Harbor run with model/provider/version, agent settings, limits, task/seed/configuration, score, transcript and replay. Confirm authorized provider access/budget first; Codex participant usage credits do not establish API inference funding. |
| 1 | **Verification lifecycle, isolation and tool discovery.** The new task defines a simulator-side collect hook and separate verifier, but that lifecycle is untested in containers. Its handoff also flags a possible Harbor/OpenCode MCP-configuration mismatch. | Demonstrate that the agent sees the five tools, stopping it finishes the existing episode rather than resetting it, and the verifier receives protected results. Confirm the evaluator token, hidden state and reward files remain inaccessible to the agent. |
| 2 | **Evidence for the research claim.** Stale-telemetry and one-command-waiting failures are deliberately weak baselines. | Compare the real agent, adaptive reference, blind plan and capable whole-leg-waiting baseline under the same public information/rules. Preserve failures and classify infrastructure problems separately from decisions. Follow the earlier prescribed judging reruns as well as the new minimum log requirement. |
| 2 | **Final mission and judge-facing evidence.** The Harbor task currently uses seed 7, delay 3 and the original map; Manh's experimental profiles are not wired into it. A replay schema is available, but no demo video was found in tracked files. | Choose/version the final profile and comparison seeds after real-run evidence; synchronize generated task copies after source edits. Add a short playthrough demonstrating objective, difficulty, decisive mistakes and reward. Keep judging model/budget settings marked unresolved until confirmed. |
| 2 | **Submission and license checks.** The recorded platform entry is still the editable Lightlag draft; additional-prize entry status is not verified. No repository `LICENSE` file was found. | Confirm final track/prize selections and any separate forms. The public Junction FAQ says submissions are open-sourced under MIT: confirm the team's submission terms and license treatment before finalizing. |

The new [reward adapter](../harbor/lightlag/tests/grade.py) implements `raw_score / max_available_value`, validates finite values and a positive denominator, and rejects malformed results. This supersedes the older MCP handoff's raw-score suggestion. It is mission-value scaling, **not reference normalization**: keep matching-reference ratios as a separate scientific metric, and validate the denominator against any future dynamic mission rules. A missing result, failed tool or broken verifier should remain an execution error, not evidence that the model failed to reason.

Harbor's upstream verifier supports text or JSON rewards and prefers `reward.json` if both exist. Follow the challenge's more specific single-number `reward.txt` instruction and keep diagnostic metrics elsewhere. Its separate-verifier mode can start a fresh environment without the agent's filesystem state, so persistence must be tested deliberately. [Official verifier documentation](https://docs.harborframework.com/tasks/verifier)

The public event schedule currently lists final submission at **10:00 Sunday 15 November**, in the event's local schedule. Treat that as the submission cutoff, and recheck the platform before final submission. The same public page states that tech challenges can accompany any main track and describes MIT licensing for submissions. [Junction overview, schedule and FAQ](https://2026.hackjunction.com/)

## Coordination and next steps

1. **Continue the Harbor integration under Kristján's existing claim.** His task landed during this audit; preserve it and coordinate runtime work with that owner and Manh's dynamic wrapper. This document claims no implementation files or new teammate assignments.
2. **Prove the minimum path on the existing profile.** On a machine with working Docker and authorized API access, build and run the reference/no-op through Harbor, then obtain one real model log and score. A new noise model is not needed to test packaging. After changing original simulator/service/reference sources, run `python3 harbor/sync_task.py` and its stale-copy checks; the task carries generated copies.
3. **Use that run to choose the next difficulty experiment.** Keep scripting available. Manh's new profiles remain experiments until a reference, sensible baselines and a real agent have been compared fairly.
4. **Collect prize evidence alongside delivery.** Follow the [prize-evidence log](prize-evidence.md); do not make sponsor integrations a competing project. Training remains optional in the recorded announcement.

Still unknown: exact judging model/version/effort and resource limits, actual team API balances, current extra-prize entry/form details, and whether later organizer messages change the contract. Nothing in this audit redeems credits, spends money, posts messages, changes the submission or chooses the final rules.
