# AfterQuery update: Ved's required stack and credits

**Later clarifications through 16:54 Helsinki:** Harbor + OpenCode is expected; judging models will not be disclosed; difficulty gap and realistic failure modes matter roughly equally. The earlier README model-preference offer does not guarantee the judge's choice. Ved also emphasized the submission video at 15:56; the 14:01–14:02 local Docker/Compose and `task.toml` timeout guidance remains recorded. See the [verified judging notes](afterquery-judging-clarifications-2026-11-14.md). The repository table below is the historical 01:35 snapshot; use [readiness](afterquery-readiness.md) for later implementation evidence.

**Source:** VED | AFTERQUERY, two posts at **01:35 Helsinki, Saturday 14 November 2026**, read directly in the [AfterQuery Discord channel](https://discord.com/channels/1268184974784336004/1564622313893404883). This note records the new announcement and our implications; it does not change Lightlag's rules or implement the integration.

## What Ved announced

- **Harbor is required** to evaluate submissions consistently. Package the environment with `instruction.md`, `task.toml`, `environment/Dockerfile`, `tests/` and `solution/`.
- **OpenCode is strongly encouraged** as the agent harness. His example is `harbor run -p ./my-task -a opencode -m [provider/model]`; replace the provider/model placeholder before running it.
- **The verifier must write one number in [0, 1] to `/logs/verifier/reward.txt`.** Partial credit is allowed.
- **Include at least one Harbor run log and its score**, showing an actual model playing the environment. Showing a playthrough in the demo video is also encouraged.
- **Include a short README** explaining the objective, difficulty and scoring. Generated prose is acceptable, but the value of the environment should be clear.
- **AfterQuery will not provide inference credits**, citing greater-than-expected demand and other sponsors' offers. Ved directs participants to Google, OpenAI and Modal.
- The track emphasizes research, creative simulations/environments and post-training experiments. This post does **not** say that model training is compulsory.

The linked [Harbor repository](https://github.com/laude-institute/harbor) currently redirects to [harbor-framework/harbor](https://github.com/harbor-framework/harbor). It is the upstream framework, not a separately published Junction starter kit.

## Immediate implications for Lightlag

Our recommendation is to proceed with the standard Harbor task integration instead of treating an event-specific starter repository as a prerequisite. Pin a version and prove the complete path with a real model run. The exact evaluation model and resource limits remain unspecified in these messages.

| Area | Current repository evidence | Next step |
|---|---|---|
| Task packaging | The [MCP handoff](lightlag-mcp.md) reports working local/HTTP adapters, but no built container, Harbor task or model playthrough. | The integration owner should package the existing service, reference and verifier as a Harbor task; this note claims no implementation files. |
| Reward scale | The current [evaluator](../lightlag/environment.py) returns mission-value `raw_score` and `max_available_value`. The MCP handoff proposes writing `raw_score` directly, which can exceed 1. | Normalize at the Harbor boundary and retain raw values as diagnostics. A candidate is `raw_score / max_available_value`, requiring a positive denominator and range/finite checks; document and validate the chosen semantics for the final mission set. |
| Run evidence | Scripted policy comparisons and MCP tests do not constitute a model's Harbor playthrough. | Preserve the actual Harbor log, model/configuration, normalized score and replay. The new one-log minimum does not cancel the earlier judging reruns/reference/baseline requirements. |
| Isolation | The handoff identifies evaluator-token and sidecar-lifetime questions. | Keep simulator truth, evaluator credentials and reward output inaccessible to the agent. Prove that verification sees the completed episode rather than a newly reset sidecar. |

Harbor's upstream verifier documentation accepts text or JSON rewards and prefers `reward.json` if both exist. For this challenge, follow Ved's explicit single-number `reward.txt` contract and keep other metrics in separate diagnostic artifacts. The upstream docs also distinguish shared verification from a new verifier environment; the implementation must resolve that lifecycle deliberately. [Harbor verifier documentation](https://docs.harborframework.com/tasks/verifier)

Do not remove code execution or scripting to create a gap. A real OpenCode pilot still needs to establish whether the current Lightlag mechanics remain difficult for a capable agent.

## Credit distinction

Ved's cancellation supersedes the earlier AfterQuery promise of frontier API credits. Do not wait for an AfterQuery inference-credit allocation.

His sponsor suggestions do not establish that every sponsor credit pays for the same service. Our **Friday 22:10 verification** recorded OpenAI's participant pack as Codex usage credits, explicitly excluding API credits, and Modal's offer as CPU/GPU compute credits. Google offered Gemini API credits; Anthropic separately listed Claude API credits. These are previously verified offers, not a new check of redemption availability or team balances. See [sponsor details](../SPONSOR_OPTIONS.md).

Use a provider for which the team actually has authorized API access and budget. Confirm the qualifying frontier model/settings before calling the final comparison complete. No accounts, redemptions or paid inference runs were initiated by this update.

## Still unresolved by these messages

- Exact judging model/version, reasoning effort, token/time budget and OpenCode configuration.
- Whether a later event-specific example, scoring skeleton or pinned harness version will be supplied.
- Whether the team has usable API credits now; the announcement itself does not grant them.

**Priority:** one honest, complete Harbor model playthrough before spending more time on presentation or optional training.
