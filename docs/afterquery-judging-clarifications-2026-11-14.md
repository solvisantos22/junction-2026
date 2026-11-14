# AfterQuery judging clarifications — Saturday 14 November

**Latest guidance, 16:54 Helsinki, verified directly in the [AfterQuery channel](https://discord.com/channels/1268184974784336004/1564622313893404883):**

- **Judging models will not be disclosed.** The earlier offer to consider README model preferences is not a guarantee of the model or provider the judges will use. Record our tested configuration and any preference separately from the unknown judging configuration.
- **Harbor format and the OpenCode harness are expected.** This is the later wording to follow when packaging the submission.
- **Difficulty gap and realistic failure modes are valued roughly equally.** Treat this as qualitative guidance alongside the published rubric; Ved supplied no replacement numerical scoring table.

At **15:56**, Ved said the submitted demo video will be a large part of judging and referred the live-demo timing, eligibility and Q&A questions to the hackathon organizers. At **15:55**, he said teams with a post-trained model should show its performance against the baseline and that AfterQuery will trust their reported results. These replies do not make training compulsory. The separately verified submission guide still limits the public video to **two minutes**, with FINAL due **Sunday 15 November at 10:00 Helsinki**. Prioritize a clear task demonstration, the measured comparison and the real-world significance and limits of the failure.

Earlier replies were also verified directly in the channel: Ved's **14:01 Helsinki** reply answers Zhen1234's **07:39** questions about rerunning tasks; his **14:02** follow-up covers timeouts. These do **not** answer the separate 13:05 questions about the ten-minute judging demo.

## Earlier 14:01–14:02 answers

- **Models:** Ved offered to use model(s) specified in the team's README if the team has a preference. Read this together with the later 16:54 statement that judging models cannot be revealed; the actual judging choice remains unconfirmed.
- **Backend:** judges will use **local Docker**. Ved explicitly confirms Harbor's Docker Compose support and expects locally working rollouts to be portable to their setup. This supports our sidecar design; it is not a guarantee that an untested package will run.
- **Timeouts:** put the agent timeout configuration in **`task.toml`**. He did not give a numerical cap or a new time budget.
- At **13:59**, Ved said the team was at the booth and invited quick questions.

## What this means for us

Keep the tested model explicit in the final README. Our existing run instructions use `anthropic/claude-opus-5-5`; state the exact provider/model, tested Harbor and OpenCode versions, configuration and reproducible command for the final package. Label that as our tested configuration or preference, and keep the package usable with a different judge-selected model/provider. This is a reproducibility recommendation, not a requirement to use that particular model. Any claim about difficulty should retain the model's successes as well as failures.

Historical repository check at `bc677a2`:

| Item | Observed state | Handoff |
|---|---|---|
| Agent timeout | [`harbor/lightlag/task.toml`](../harbor/lightlag/task.toml) has `[agent] timeout_sec = 1800.0` (30 minutes). | Already explicit. Check the final exported task and any run-time overrides; a ten-minute presentation and an agent execution timeout are different limits. |
| Compose | [`docker-compose.yaml`](../harbor/lightlag/environment/docker-compose.yaml) adds a `lightlag` simulator service alongside Harbor's agent service. | Matches the backend Ved described. Validate the selected final package from a clean checkout. |
| Model command | [`docs/lightlag-harbor.md`](lightlag-harbor.md#run-it) names OpenCode with `anthropic/claude-opus-5-5`. | Put the tested model, any preference and exact entry point prominently in the final README. Judging models remain undisclosed. |
| Actual judge task | Canonical `harbor/lightlag` still contains the original seed-7 core mission; dynamic experiments and other prototypes are separate. | The team must choose and package its final task. These mentor answers do not choose it for us. |

The existing [Harbor, reward, run-log and README requirements](afterquery-update-2026-11-14.md) remain relevant. This clarification supplies no credits and announces no replacement starter kit. No task files, model settings, credentials or paid runs were changed for this note.

## Remaining questions

1. When and where is the ten-minute demo: peer-review table or a separate slot?
2. Does every team get it, or only shortlisted teams?
3. Does the ten minutes include questions?
4. Are judging rollouts run separately from the live demo, and is our declared 30-minute agent cap suitable? Any expected reasoning/token limits or resource limits beyond the declared configuration?

Ved referred the first three to hackathon organizers at 15:56; they are still unresolved for a separate AfterQuery ten-minute demo. The fourth is our execution-budget follow-up for AfterQuery, prompted by the recorded task configuration. Nothing was posted to Discord by this update.
