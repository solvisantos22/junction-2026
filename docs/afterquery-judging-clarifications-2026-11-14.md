# AfterQuery: model, Docker and timeout clarifications

Verified directly in the [AfterQuery channel](https://discord.com/channels/1268184974784336004/1564622313893404883) on Saturday 14 November. Ved's **14:01 Helsinki** reply answers Zhen1234's **07:39** questions about rerunning tasks; his **14:02** follow-up covers timeouts. These do **not** answer the separate 13:05 questions about the ten-minute judging demo.

## Confirmed by Ved

- **Models:** judges can use the model(s) the team specifies in its README if the team has a preference. No single mandatory model was named in this reply.
- **Backend:** judges will use **local Docker**. Ved explicitly confirms Harbor's Docker Compose support and expects locally working rollouts to be portable to their setup. This supports our sidecar design; it is not a guarantee that an untested package will run.
- **Timeouts:** put the agent timeout configuration in **`task.toml`**. He did not give a numerical cap or a new time budget.
- At **13:59**, Ved said the team was at the booth and invited quick questions.

## What this means for us

Keep the tested model explicit in the final README. Our existing run instructions use `anthropic/claude-opus-5-5`; state the exact provider/model, tested Harbor and OpenCode versions, configuration and reproducible command for the final package. This is a recommendation to preserve reproducibility, not a new organizer requirement to use that particular model. Any claim about difficulty should retain the model's successes as well as failures.

Repository check at `bc677a2`:

| Item | Observed state | Handoff |
|---|---|---|
| Agent timeout | [`harbor/lightlag/task.toml`](../harbor/lightlag/task.toml) has `[agent] timeout_sec = 1800.0` (30 minutes). | Already explicit. Check the final exported task and any run-time overrides; a ten-minute presentation and an agent execution timeout are different limits. |
| Compose | [`docker-compose.yaml`](../harbor/lightlag/environment/docker-compose.yaml) adds a `lightlag` simulator service alongside Harbor's agent service. | Matches the backend Ved described. Validate the selected final package from a clean checkout. |
| Model command | [`docs/lightlag-harbor.md`](lightlag-harbor.md#run-it) names OpenCode with `anthropic/claude-opus-5-5`. | Put the intended judging model and exact entry point prominently in the final README. |
| Actual judge task | Canonical `harbor/lightlag` still contains the original seed-7 core mission; dynamic experiments and other prototypes are separate. | The team must choose and package its final task. These mentor answers do not choose it for us. |

The existing [Harbor, reward, run-log and README requirements](afterquery-update-2026-11-14.md) remain relevant. This clarification supplies no credits and announces no replacement starter kit. No task files, model settings, credentials or paid runs were changed for this note.

## Still worth asking at the booth

1. When and where is the ten-minute demo: peer-review table or a separate slot?
2. Does every team get it, or only shortlisted teams?
3. Does the ten minutes include questions?
4. Are judging rollouts run separately from the live demo, and is our declared 30-minute agent cap suitable? Any expected reasoning/token limits or resource limits beyond the declared configuration?

The first three are Zhen1234's unanswered 13:05 questions. The fourth is our follow-up prompted by the current task configuration. Nothing was posted to Discord by this update.
