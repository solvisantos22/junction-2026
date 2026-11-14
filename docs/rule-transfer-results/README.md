# Rule-transfer results

The [protocol](../rule-transfer.md) was published in `9850c80`; the verified
runner was published in `2b482f3` before the full replay. This first result is a
free transfer screen of an unchanged saved Opus program, not a new model call.

## Free replay

Already-used seeds 3200–3239, `rush_noisy`, delay 3, horizon 50, noise level 1;
one process per episode. Scores are mean raw reward divided by available target
value, not optimality fractions. Home counts require the rover to be alive.

| Condition | Prepared score | Saved Opus score | Prepared home | Saved Opus home | Opus deaths |
|---|---:|---:|---:|---:|---:|
| Unchanged | .744712 | .757111 | 40/40 | 40/40 | 0 |
| Ground | .625895 | .705716 | 40/40 | 40/40 | 0 |
| Turning cost | .655286 | .302649 | 40/40 | 17/40 | 23 |
| Lost telemetry | .636440 | .757111 | 38/40 | 40/40 | 0 |
| Relay windows | .661816 | .749194 | 40/40 | 40/40 | 0 |
| Four changes pooled | .644859 | .628668 | 158/160 | 137/160 | 23 |

The pooled score hides the failure: the saved program beats Prepared in three
kinds, but ignores the new turning cost and loses 23 rovers in that condition.
Its mean sampled science there is 7.95, versus Prepared's 6.9625; after the
survival penalty, its mean raw reward is 3.09375. The problem is preserving the
mission's value while returning safely, not collecting enough samples.

All 200 reference cases return normally with no invalid calls. The saved program
has no process exceptions or protection-limit interruptions; two relay cases
make three invalid public calls, which it catches internally. Those cases are
labelled `invalid_calls` and retained, not relabelled as clean successes.

The frozen retirement screen fails on turning reward, deaths/home and the
invalid-call criterion. This warrants inspecting the specific failures and
considering the authorized bounded adaptation step. It does not establish that
Opus, when told the new rules and allowed to revise its program, cannot solve it.

## Verification and artifacts

- [Full report](free/report.json): policy/source/image pins, all 400 results,
  descriptive summaries and every gate condition.
- [Independent audit](free/audit.json): all 400 complete replays, grades and
  **47,414 public calls** reconstruct; all three rejected calls are reproduced.
  All 69 declared source/document hashes and the original policy hash match.
- `free/cases/`: compressed complete transcripts, replays, result metadata and
  worker stderr. No case is filtered out. Seeds are reused development evidence,
  and four kinds share each seed; no independent-trial confidence claim.
- **14 focused tests pass**, eight with actual Docker and six exercising audit
  integrity, including forged responses/rewards even after artifact rehashing.

Python 3.12.16 and NumPy 2.3.4 were used by the trusted reference/auditor. The
generated policy uses a pinned `python:3.12-slim` image and the standard library.
Simulation time pauses during reasoning; container limits only protect the
runner and would be classified separately if reached.

```sh
python3.12 -m unittest discover -s tests/rule_transfer -v
python3.12 -m tools.rule_transfer.study --output /tmp/new-rule-transfer --start 3200 --count 40 --parallel 2
python3.12 -m tools.rule_transfer.audit docs/rule-transfer-results/free/report.json
```

Use the pinned source revision for exact reproduction; the frozen protocol is
hashed and stays unchanged. No API call or spend has occurred in this free
screen. Existing environments, controllers, model-generated policy and teammate
studies are unchanged. Failure analysis and any bounded continuation are recorded
as separate increments below.

## Failure analysis and continuation

All 23 lost rovers finish inside the base; 19 die on idle ticks. The original
program forecasts translation, sampling and idle drain but omits angular energy
cost. It reads an unexpectedly large public battery drop before death in 22/23
cases and sends further drives after that signal in 11. Near-base corrections
can consume the remaining reserve: reaching base alone does not stop the clock
or idle drain. These are reproducible program failures, not a measured inability
of the model to repair its code.

The relay rejections are also correct: requests at ticks 44/45 wait for relay
transmission at 48, then would execute at 52 beyond the horizon of 50. The saved
program honors acknowledged execution times but initially assumes it can still
send those late corrections.

[Detailed diagnostics](failure-analysis.json) include both public signals and
explicitly labelled evaluator-only counterfactuals. The latter assume queued
commands could be cancelled (the API has no cancellation), so they are not proof
of an executable rescue policy. Reproduce without new episodes or model calls:

```sh
python3.12 docs/rule-transfer-results/analyze_failures.py --output /tmp/failure-analysis.json
cmp /tmp/failure-analysis.json docs/rule-transfer-results/failure-analysis.json
```

The [bounded adaptation protocol](adaptation-protocol.md) reserves fresh seeds
52000–52039 before opening them. It gives Opus the full rules and original code,
one practice evaluation and a final submission, with a $1 usage guard. This is
a repair diagnostic, not a full interactive-agent benchmark. The final program
must be frozen before the 600-episode local comparison starts.


Adaptation preparation also verifies the new NumPy-enabled image against the
previous unchanged-control replay on used seed 3200: the entire replay and grade
match. API dry-run validates the prompt, source/image pins and explicit local
credential setup without contacting the provider. Neither check opens fresh
cases or spends credits. The launch tooling and its focused error/budget tests
are published in the next increment before the paid request.

The first provider token-count request rejected a tool schema unsupported at
the API boundary. It made **zero generation requests and spent no generation
credits**. The [retained preflight](adaptation/adaptation.json) and
[declared correction](adaptation-preflight-correction.md) document the adapter
fix before the corrected launch; this is not a failed model attempt.


## Context from the four new teammate pilots

Kristján's separately authored [four direct-agent runs](../lightlag-shift.md)
landed in `afbb89f` while this experiment was running. The saved grades match
verifier rewards (rounding aside): .613636, .775, .555556 and zero. They are four
single attempts, not a replicated estimate, and no pilot is folded into our
fresh comparison or cost ledger.

One agent correctly inferred the turning coefficient and tied Prepared, so the
old program's turning failures do not establish inability to detect that rule.
The ground pilot's first missed sample preceded the change, complicating
attribution of its score deficit; its final relay diagnosis was wrong. The relay
pilot made an unaffordable late detour and depleted at home without extra relay
scheduling delay. The acknowledgement's newly present `transmit_tick` field was
still a public cue even when equal to `sent_tick`.

These observations make reliable energy and queue accounting worth testing.
They do not justify assuming that a larger mission or harder diagnosis will
produce a robust gap. Pilot metadata acknowledges stale task hashes and omits
some change-module sources; reference comparisons are reported in the write-up.
This was a read-only trace/grade review, not a fresh replay audit of those runs.

## Bounded adaptation result: incomplete

The corrected launch from `e7bbc73` made **one** Opus 5.5 request. The provider
reported 17,914 input tokens and 16,000 output tokens, all 16,000 classified as
thinking. It stopped at `max_tokens` with no text or tool submission. Therefore
there is no candidate program, no practice result, no final freeze and no fresh
evaluation. The runner stopped exactly as declared; it did not retry or fall
back to an earlier policy.

Reported cost is **$0.391656**, below the first request's $0.402920 reservation
and the $1 total launch guard. Request ID: `req_011Ch36m4zEyZ6hS7RUffiaY`.
[Public response/usage](adaptation-v2/response_1-public.json),
[complete public metadata](adaptation-v2/adaptation.json),
[verification](adaptation-v2/verification.json). Private thinking/signatures
remain outside the repository. The first rejected token-count preflight made
zero generation requests and adds no generation cost.

The 16,000-token response cap was our experimental resource limit. It prevented
a submitted program here, so this is **censored evidence, not a failed repair or
a capability gap**. We should not increase mission difficulty based on this
result. The held-out range **52000–52039 remains unused**; a future run needs a
new declared protocol before consuming it.

Historical possibly shared usage rises from $13.882161 to $14.273817 when adding
this request; this is bookkeeping, **not a live balance**. Kristján's separately
approved calls are not silently charged to this ledger.

```sh
python3.12 docs/rule-transfer-results/verify_incomplete_adaptation.py
```

## Decision and handoff

Keep the four-rule mission provisional. The free transfer establishes a concrete
energy-accounting weakness in a saved program, and the new direct-agent pilots
show that an agent can diagnose turning cost correctly. Neither establishes a
reliable strong-agent gap. The latest stereo and sample-chain experiments also
fail their own difficulty gates; those are not proven alternatives to promote.

The next useful test is an adequately resourced full coding-agent attempt on the
existing rules, with scripting and practice intact, before any bigger build.
Its key question is whether budgeting for queued actions, return and idle drain
removes the failures. Choose its generation budget against the available credit
balance before launch; this bounded experiment made no such additional request.
If a strong code-generating agent removes the deficit, retire this configuration
for gap hunting. If it leaves a repeatable deficit under fair resources, inspect
that specific failure before extending the environment.

Published runner, protocols, prompt, incomplete attempts and audit tools are
ready for reuse. **34 focused tests pass**; free replay audit remains valid.
Existing simulator, reference, original policy, teammate studies and canonical
Harbor task are unchanged. No final project/rules choice or prize submission.
