# One reusable model policy: prospective transfer experiment

Declared during Block B, after its first three paired outcomes and before
any synthesis request, fresh-map construction or result inspection. The user
authorized autonomous overnight development/research and a $15.70 remaining
Claude budget. Existing [spending guards](lightlag-overnight-evaluation.md)
remain in force. No paid synthesis request starts until all B assignments are
finished and reconciled; stop if cumulative overnight cost has reached $12.

## Question and scope

Can the same frontier model write a reusable controller that performs well
across new maps? The team's reference reuses an engineered policy, while each
online model session reconstructs its approach. The seed-500 model wrote a
route helper; that does not yet establish autonomous policy transfer.

This is a distinct controller-synthesis condition, not a replacement for the
online OpenCode experiment, an attribution test for B, or a qualifying new
Harbor model playthrough. A good result would narrow claims about intrinsic
task difficulty. A poor one-shot program would not establish that the model
cannot construct a better policy with feedback or more attempts.

Choose one response and freeze it without repairs. More online repetitions
would add less breadth; testing a frozen program provides many fresh episodes
without paying inference on each map. Do not choose the best of several
programs or tune the policy after any evaluation result.

## Fixed synthesis request

- Claude API `claude-opus-5-5`, one Messages response, adaptive thinking,
  `output_config.effort = high`, `max_tokens = 24000`, no sampling overrides,
  no external tools or prompt caching. Use the standard endpoint, not fast
  mode or a batch. Set SDK/network retries to zero.
- Publish the exact system/user messages, request settings and hashes before
  launching. Supply only public rules for rush and rush_noisy at delay 3,
  horizon 50, noise level 1 and bumpiness 0, the public instruction and generic
  accounting aid, and the five-call interface/schema. No simulator/controller
  source, seed values, prior outcomes, reference routes or saved trajectories.
- Request a complete standard-library Python module with `play(tools)`, which
  may call only `rules()`, `map()`, `telemetry_log()`, `uplink(commands)` and
  `advance(ticks)`. The policy starts with no map and receives only actual
  public responses. Explain delayed discoveries, noisy reported movement and
  early-stop grading accurately. It may keep internal state within an episode.
- Extract the returned text verbatim; permit only removal of a single outer
  Markdown code fence and terminal whitespace. Retain the exact response text,
  extracted module, request/response IDs, model, usage and hashes. No human or
  second-model syntax fixes, parameter adjustments or algorithm edits. If the
  response is truncated, incompatible or invalid, preserve that outcome and
  do not replace it.

Reserve **$1 maximum** for this single request. Before generation, use the
provider's token counter. Because it is an estimate, allow **25% extra input
tokens plus 1,000 tokens** and require the resulting input cost plus the complete
24,000-output-token allowance to be **at most $0.90**, while reserving the full
$1 within the remaining overall ceiling. The
[token-count endpoint is free and returns an estimate](https://platform.claude.com/docs/en/build-with-claude/token-counting).
Current published standard prices are $4/million input and
$20/million output; thinking is included in output usage. Record a calculated
estimate from the actual provider token counts separately from Harbor-reported
costs and from an independently verified account balance. Unexpected prices,
unknown usage or provider errors stop further paid work; no automatic retry.
[Official model/prices](https://platform.claude.com/docs/en/models/opus-5-5/overview),
[thinking and hard output limits](https://platform.claude.com/docs/en/build-with-claude/thinking),
[API migration/settings](https://platform.claude.com/docs/en/models/opus-5-5/migration-guide).

## Fixed evaluation before outcomes

Use **seeds 60000–60019 on both rush and rush_noisy**: 40 cells, selected
before constructing any of their maps. Repository search found no earlier
use of these exact seeds. The model is not given the list. Run exactly one
generated policy and the original `kf_mpc` on every cell: **80 primary
episodes** if synthesis succeeds. No replacement cells or additional
candidates. These maps become used after this experiment.

Freeze the simulator, public-call service and original reference from
`02e4f7062ec3feaca14d9cc2eeb953af870ba769` in a separate source tree. Record
every imported source hash and dependency version. The later MCP-description
correction is separate; this experiment supplies correct public documentation
directly and does not depend on those descriptions. Settings remain delay 3,
horizon 50, noise 1 and bumpiness 0. No scenario factors, real-time clock,
privileged logger or changed scoring.

Run each generated-policy episode in a fresh, constrained Docker process:
read-only controller/runner files, no repository, evaluator state, credentials
or reference code mounted; no network, dropped capabilities, unprivileged
user, fixed memory/CPU/process limits and a small temporary filesystem. Pin
the resolved Python image digest before generation. A host-side broker owns
the frozen episode and forwards only the five public calls and their JSON
responses over standard input/output. The program sees neither seed nor truth.
Cap an episode at **500 calls and 60 seconds after process launch**. Record
these limits, even though online-agent budgets differ. Return or policy error
triggers the normal trusted finish to tick 50; already accepted commands run.

The trusted original reference receives the same public-call response shapes
and information; it may run locally without the generated-code container.
Record that runtime asymmetry and make no speed/cost-efficiency claim from
those timings. Before fresh evaluation, require exact reproduction of all
eight historical Harbor reference scores and full trajectories through this
broker's public service. The model never receives those checks or outcomes.

## Reporting and verification

Report every planned row, protected terminal reward, raw/maximum value,
alive/home, policy execution status/error, call count and elapsed time. Keep
policy failures separate from broker/container failures. Preserve any real
terminal grade produced after a policy error; never manufacture zero for
missing grading. If synthesis fails before evaluation, report the 40 cells as
unrun with null scores. Report incomplete comparison bounds rather than
silently dropping failures.

Primary summaries: mean normalized reward per profile for each policy,
paired differences, wins/ties/deficits, and deaths/home status out of all 20
cells per profile. Keep these separate from A/B and reference-selection data.
Publish complete public transcripts and protected replays with source hashes;
independently reconstruct every recorded call and final state. Re-run exactly
four cells for verification only: seed 60000 and 60019 on each profile. These
are not additional independent samples or replacement primary runs. These
forty cells measure transfer of **one sampled program**, not forty independent
code-generation trials. Ask for deterministic policy behavior in the frozen
request. Do not repair randomness if the returned code ignores that request;
retain differing verification repetitions separately and mark the policy as
not exactly reproducible under the declared runtime. Truncation, incompatibility
or timeout characterizes this budgeted condition, not general incapability.

Verify the broker with public protocol/error cases, unchanged source/input
guards, safe output ownership, no key/personal-path leakage and actual Docker
isolation before generating the policy. Independent review precedes any paid
request and final integration. Root controls credentials, generation, cost
reconciliation and Git pushes. Project, final task and reference choice remain
provisional.

## Recorded outcome

The one declared request ended at `max_tokens`, reporting 5,989 input and
24,000 thinking tokens with no controller text. Calculated usage is $0.503956.
No retry, repair or replacement followed. The evaluator records all 40 cells
(80 planned policy/reference episodes) as unrun/null, with no fresh map
construction. This leaves the transfer question unanswered; it is not evidence
of zero task performance or general model incapability. See the
[complete record and verification](lightlag-runs/overnight-synthesis/README.md).
