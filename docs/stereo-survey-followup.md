# Stereo follow-up: can an agent build the solver?

**Final result: retire this configuration as an agent-difficulty candidate.** Both unhinted Opus 5.5 programs and the solver-hinted control reach the proved optimum on **48/48 unseen missions each**. All 144 model-case evaluations are valid, with no timeout or runtime error. Total reported API cost: **$1.023160**. The missing solver-construction question is answered: the model can derive and implement a winning planner from the public rules. The reusable result is the compatible-observation objective and the checked evaluation machinery, not a model failure.

14 November 2026. Kristján asked to continue investigating stereo survey and assess whether it is a good lead. The [v1 result](stereo-survey.md) remains unchanged: a small generic-search portfolio attains every fresh optimum. That establishes easy search **once an appropriate program exists**. It does not measure whether a coding agent will formulate and implement that program from the public rules.

This follow-up targets that missing evidence before constructing a larger environment. It is a different, explicitly stated question, not a reinterpretation of the failed v1 screening gate. No LLM weakness is established at the start of this follow-up.

## Why the research does not settle it

[AstroAgentBench](https://aclanthology.org/2026.aacl-long.72.pdf), §§3 and 5 and Appendix C, asks stereo agents to choose observation times and pointing angles and derive useful products from them. Our v1 instead supplies finite image opportunities and rectangular footprints. The paper separates task formulation from solution construction, and reports specification-related failures as well as genuine planning failures. Its procedure/memory interventions are reported for Regional Coverage and Relay, not a clean current-model stereo replication. These differences justify a limited agent test; they do not justify claiming the paper's gap for our easier task.

## Intended test

Package the public rules, geometry helper, independent validator and development missions in an isolated workspace. Do not expose reference/search code, solutions or fresh outcomes. Invite code, solver use and local validation. Freeze the returned program and evaluate it on new missions against the same exact reference, retaining every outcome and any resource/error limit.

Start with a cheap falsification: if a generated general solver already matches the reference, retire this version as a difficulty candidate. A failure from one generation is weaker evidence and would require a proper feedback-enabled coding-agent run before any positive claim. A solver hint should also be tested before treating a failure as robust.

The protected checks, source/task hashes, execution limits, prompts, exact model configuration and spend limit must be concrete before a model call. No API spend is authorized by this document, and no unrelated session's budget is reused. Preparation and offline validation are within the user's approved continued investigation.

## Frozen falsification package

[Runner](../tools/stereo_survey_experiments/pilot.py), [plain prompt](stereo-survey-followup-results/pilot-02/plain.md), [hinted prompt](stereo-survey-followup-results/pilot-02/hinted.md), and [machine-readable protocol](stereo-survey-followup-results/pilot-02/protocol.json).

- Three independent requests to `claude-opus-5-5`: two plain, one with a concrete enumeration/coverage hint. Adaptive thinking, high effort, 64,000 maximum output tokens including thinking, no tool feedback, no retry or fallback. The SDK is Anthropic 2.8.0. This measures **one-generation program synthesis**, not a full Harbor/OpenCode coding session.
- Public geometry and replay source plus two already-used development missions (compact seed 0, expanded seed 1). No reference/search source, winning plan, optimum or held-out mission enters a request. Python standard library and those helpers are available at execution; additional solver packages are absent. These restrictions make success useful falsification but make failure weak evidence.
- Freeze all three responses/program hashes before any fresh evaluation. Use seeds **62000–62023**, compact and expanded: 48 missions per program, with the same missions across programs. Retain all generations, syntax/extraction failures, invalid plans, runtime failures and timeouts. No manual repair or best-run replacement. Correlated profiles and repeated programs are not 144 independent missions. This range avoids a teammate's separately reserved rover seed labels; it was selected before any check mission was generated.
- Each program gets a fresh unprivileged, network-disabled Docker container with one CPU, 512 MiB RAM, read-only files, 16 MiB scratch and a 30-second total limit including startup. Output is capped at 64 KiB. The local Python 3.12 image is pinned by digest. Mount only the submitted program, worker and public helpers; never the repository, credentials or reference. The host separately verifies the returned plan against an untouched mission.
- Reference proof limits remain 10,000 local plans and 10 million joint checks. Report raw science, validity, exact-match count and mean fraction of certified nonzero optimum per program/profile. A capped, invalid or inconsistent reference is retained and excluded explicitly from normalization; it prevents a clean difficulty conclusion. A Docker infrastructure failure also prevents interpreting a low score as model failure.

**Prospective interpretation:** a plain program attaining at least 95% of optimum in both profiles, with every plan valid and every reference certified, is enough to stop pursuing this configuration as a large model gap. Exact 48/48 success is stronger negative evidence. A successful hinted program means the apparent difficulty is readily repaired by an algorithmic hint. If all three fall short, inspect failures and run a feedback-enabled coding agent with solver access before arguing for promotion. This threshold is a follow-up decision rule, separate from the already-failed scripted-control gate; neither establishes a universal reference win on larger missions.

## Offline verification and spend

The [six-case preflight](stereo-survey-followup-results/pilot-02/preflight.json) passes through the actual container interface. Empty plans are valid with zero science; unknown-image plans are invalid with zero science. The reference reaches its proved optima, **44 compact / 57 expanded**, in **under two seconds each** including container overhead on this machine. These are used development cases, not fresh model results.

Six focused checks cover bundle isolation, source tampering, freezing all generations before evaluation, safe extraction, public imports/read-only execution, input mutation isolation, and timeout/output/runtime failures. The 12 existing geometry, replay and reference tests also pass. The cached SDK import was verified without making a model request.

Maximum spend for this three-request batch: **$5 total** for all three generations. [Official standard global pricing](https://platform.claude.com/docs/en/models/opus-5-5/overview), checked 14 November, is $4 per million input tokens and $20 per million output tokens. The runner counts input tokens and reserves the full possible output charge plus a margin before each call. It records provider usage and stops on unknown prior usage. No automatic retries, caching, fast mode or regional-price override is requested. A request interrupted before usage is recorded blocks the next launch pending reconciliation.

**Status: complete; all three frozen programs evaluated and audited.** Kristján explicitly authorized Anthropic API use and asked that useful findings be committed and pushed in Markdown. The agent has set a $5 ceiling for this batch. Before any stereo model request, protocol v2 raises the output allowance from 16,000 to 64,000 tokens because a separate [rule-transfer attempt](rule-transfer-results/README.md) exhausted 16,000 tokens on reasoning and returned no code. Everything else—prompts, three attempts, fresh seeds, runtime and decision rule—remains fixed. This change precedes all stereo generations and fresh outcomes. The original unused [v1 preparation](stereo-survey-followup-results/pilot-01/protocol.json) and preflight remain intact; its source is available at commit `655adef`. At that pre-generation checkpoint no fresh check seed had been evaluated. Seeds 62000–62023 are now used for this stereo version; any revised task needs a new protocol and unused cases.

To verify the prepared bundle without model calls:

```sh
python3 -m tools.stereo_survey_experiments.pilot check docs/stereo-survey-followup-results/pilot-02
STEREO_DOCKER_TESTS=1 python3 -m unittest discover -s tests/stereo_survey_experiments -v
```

For the authorized batch, run `ask` for `plain-1`, `plain-2` and `hinted-1` with the approved total budget, then `evaluate` for each. `ask` requires `--approved-budget-usd` and an API credential supplied through the environment; never put a key in command arguments or repository files. The runner refuses to overwrite attempts or evaluations.

## Generation checkpoint, before fresh evaluation

All three Opus 5.5 requests completed normally (`end_turn`) and returned syntactically valid `solve(mission)` programs. No generated code ran on the host, no program was edited, and no fresh mission has been evaluated at this checkpoint. [Frozen program hashes](stereo-survey-followup-results/pilot-02/frozen-generations.json) precede the fresh check.

| Attempt | Output tokens, including thinking | Thinking tokens | Reported cost |
|---|---:|---:|---:|
| Plain 1 | 9,298 | 5,103 | $0.225392 |
| Plain 2 | 15,335 | 10,425 | $0.346132 |
| Hinted 1 | 20,573 | 14,930 | $0.451636 |

Total reported generation cost: **$1.023160**. All three receive the same 48 held-out missions next; quality is not known yet. The hinted response exceeded the original 16,000-token allowance, so increasing the allowance prospectively avoided truncating that trial.

## Unhinted solver behavior

The protocol was published in [`792109b`](https://github.com/solvisantos22/junction-2026/commit/792109b), and all three generated programs were published in [`269217a`](https://github.com/solvisantos22/junction-2026/commit/269217a) before opening any fresh mission. [Plain 1 results](stereo-survey-followup-results/pilot-02/attempts/plain-1/evaluation.json): **24/24 compact and 24/24 expanded optima**, no invalid schedule, timeout or runtime error. Every reference completed its proof and replayed correctly. Mean raw science is 45.2083 compact / 50.5417 expanded. The submission's median container execution was about 0.61 / 0.58 seconds, maximum 1.09 seconds across the 48 cases; these are machine-specific observations, including startup.

Independent host replay regenerated all 48 missions and verified every saved reference/model plan. The unhinted program precomputes pair-coverage bitmasks, enumerates feasible per-camera schedules, removes some dominated schedules and combines the survivors under coverage bounds. It also calls the supplied validator before returning a plan. Those mechanisms are visible in its submitted code, not inferred from hidden reasoning. It received no reference or search source and no example winning schedule.

The first result closed the missing program-construction question for this bounded version. The second unhinted program and hinted control independently reproduced 48/48 optimum scores on the same missions. No program was repaired or regenerated after seeing an outcome.


## Final comparison and audit

| Frozen program | Compact optima | Expanded optima | Mean fraction of optimum | Median / maximum container seconds | Reported API cost |
|---|---:|---:|---:|---:|---:|
| Plain 1 | 24/24 | 24/24 | 100% | 0.59 / 1.09 | $0.225392 |
| Plain 2 | 24/24 | 24/24 | 100% | 2.57 / 5.70 | $0.346132 |
| Hinted 1 | 24/24 | 24/24 | 100% | 0.59 / 1.44 | $0.451636 |

Every reference is proved, valid and nonzero; no normalization exclusion is needed. All three requests ended normally and all 144 executions returned valid plans. There are **48 unique missions, not 144 independent missions**; compact and expanded cases sharing a seed are correlated. The three generated programs are a small pilot, not a model-population reliability estimate. Container runtimes include startup and describe this laptop; they are not a controlled comparison against reference speed. No more model spend is warranted for this configuration.

Full retained evaluations: [plain 1](stereo-survey-followup-results/pilot-02/attempts/plain-1/evaluation.json), [plain 2](stereo-survey-followup-results/pilot-02/attempts/plain-2/evaluation.json), [hinted 1](stereo-survey-followup-results/pilot-02/attempts/hinted-1/evaluation.json). The [audit report](stereo-survey-followup-results/pilot-02/audit.json) reproduces source/task/prompt/response/program hashes, all mission inputs, both reference and submission replay results, per-profile summaries, token usage and the $1.023160 total. It does not execute model code on the host. Run it with:

```sh
python3 docs/stereo-survey-followup-results/audit.py
```

## What is useful elsewhere

- **Mission design:** reward a useful combined product. In the original scripted study, collecting image coverage without compatible views produced only 18–28% of the stereo optimum. A multi-view rock or terrain survey could make rover position, camera direction, storage and return transmission relevant to science quality. Applying that to Traverse is a proposal, not a tested transfer or an automatic difficulty increase.
- **Small planning and training datasets:** the generator, independently replayed exact reference and public validator supply instances with known achievable targets. They can support planner regression tests, error diagnosis or training examples. Certification is bounded by the reference's search limits; it does not extend automatically to large missions.
- **Agent evaluation:** this batch separated a difficult-looking objective from actual difficulty for program synthesis. Both unhinted programs found the appropriate optimization structure. Freezing programs before unseen cases and using protected scoring makes that result reusable across other planning tasks. A one-shot failure would have required a feedback-enabled coding-agent follow-up; the observed one-shot successes already disprove a robust gap here.
- **A different research hypothesis:** the motivating paper asks agents to construct observation times and pointing angles, while this prototype supplies a small finite image menu and rectangular footprints. Observation construction, terrain visibility or uncertain measurements could be investigated separately, with a clear contract and a checked reference. This experiment gives no evidence that any of those variants will defeat current models.

**Handoff:** preserve the prototype and these negative findings; do not promote or enlarge v1 merely to obtain a failure. No canonical environment, rover controller or demo was changed by the stereo experiment. User-requested integration of separate Claude Code work was a Git coordination task, not a stereo research contribution.
