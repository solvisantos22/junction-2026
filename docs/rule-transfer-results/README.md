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
