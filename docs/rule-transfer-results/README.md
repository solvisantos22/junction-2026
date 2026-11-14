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
