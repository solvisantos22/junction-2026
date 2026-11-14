# Claude information-choice pilot

**Claude made the optimal information and route decisions in all four frozen
cases, with optimal commitment timing.** Every realized reward matches the
same-seed reference. This small prototype is solvable; the pilot exposes no
reasoning gap and does not yet supply a difficult benchmark.

| Context | Claude's actions | Claude reward | Same-seed reference | Reported cost |
|---|---|---:|---:|---:|
| Uncertain | Probe, observe soft signal, then detour | 0.325 | 0.325 | $0.1124056 |
| Likely firm | Skip probe, shortcut immediately | 0.900 | 0.900 | $0.0359776 |
| Likely soft | Skip probe, detour immediately | 0.400 | 0.400 | $0.0375582 |
| Costly probe | Skip probe, shortcut immediately | 0.000 | 0.000 | $0.0406700 |

Total reported model cost: **$0.2266114**. Four planned sessions, four completed;
no retries, replacements, infrastructure failures, invalid public service calls
or observed budget truncations. Mean realized reward is 0.40625 for both model
and reference. That small-sample mean is distinct from the exact expected value
0.5596875 across these contexts.

## Why a zero score can follow a good decision

In the expensive-probe context, the shortcut has expected reward 0.45, the
safe detour 0.40, and the best probe policy 0.4125. Probing costs three energy,
leaving seven: too little for the detour. Claude correctly took the shortcut
at tick zero. The sampled ground was soft, so both Claude and the reference
failed and scored zero. The objective is expected reward, not guaranteed
survival. This is a stochastic loss, not evidence of a reasoning error.

In the uncertain context, probing is worth 0.53375 in expectation versus 0.45
without it. Claude probed at tick zero, received the soft signal at tick three,
and immediately committed to the detour. After that signal, the shortcut's
expected reward is 0.0825 versus 0.325 for the detour. A hindsight decision to
skip probing and detour would score 0.40 on this terrain, but the agent did not
know the terrain when choosing whether to inspect.

## Frozen setup and evidence

The [protocol](lightlag-runs/information-claude-pilot-v1/protocol.json) was
committed in `a7f72ef` before any model call. It fixes one fresh session per
context, no retries, hidden-seed commitments, clear instructions and permission
to script. No optimal policy was supplied to Claude. Actual harness: Harbor
0.25, OpenCode 1.19.5, `anthropic/claude-opus-5-5`.

The pilot used OpenCode's 12-step prompt guard, an 8,192-token per-response
output limit and Harbor's 1,800-second timeout. The 12-step setting is not a
hard call cap. The dollar target was $1.50, with serial launches stopped once
reported pilot usage reached $1.00 or became unknown. These are spending
controls, not experimental difficulty constraints. Reported cost is not an
independently checked invoice.

The simulator and hidden state run in a separate container; grading is in a
separate verifier. Actual agent-container checks found no simulator source,
evaluator result, evaluator token or reference policy at their expected paths.
An unauthenticated evaluator finish request returned 404. Real Harbor preflight
reference and no-op controls scored 0.325 and 0.0. Their generated task predates
the clean freeze and records `source_dirty: true`; it is retained as preflight
evidence, outside the four clean model/reference pairs.

Forty information-package tests and three packaging tests passed before the
pilot. Independent audit reconstructed all eight model/reference public service
transcripts and protected replays, checked generated task hashes and grades,
and verified all four seed commitments after completion. Root independently
compared every accepted probe/commit action and commitment tick against the
public-information reference. Every choice and timing matches. The final
offline audit is saved alongside the evidence and can be rerun:

```sh
python3 -m tools.information_experiments.audit_pilot \
  docs/lightlag-runs/information-claude-pilot-v1
```

- [Complete result ledger](lightlag-runs/information-claude-pilot-v1/summary.json)
- [Offline audit](lightlag-runs/information-claude-pilot-v1/audit-summary.json)
- [Seed and salt reveals](lightlag-runs/information-claude-pilot-v1/assignments-reveal.json)
- [Trial artifacts](lightlag-runs/information-claude-pilot-v1/runs/)
- [Exact generated tasks and source hashes](lightlag-runs/information-claude-pilot-v1/tasks/)

Exports retain protected replays, public tool traces, verifier output, reported
usage and original/export hashes. Provider state, raw provider logs and
trajectory message fields stay private; public actions, observations and
metrics suffice for the decision audit. The [earlier mechanism study](lightlag-information-choice.md)
and the continuous rover, canonical Harbor task and teammates' work are unchanged.

## Decision and handoff

Keep the mechanism and protected test harness as a foundation. This pilot does
not justify presenting it as a model-breaking task. Four hand-designed
development contexts with one session each cannot establish population
reliability. The only actual probing trial received a soft signal; Claude's
reaction to a firm signal remains untested. The model chose whether to buy one
available observation; allocation among competing information sources is open.

The next bounded experiment should ask **which uncertainty is worth inspecting
when only one inspection is available**. Give two consequential unknowns and
vary which observation can change the best plan. Retain an exact reference,
a no-information control and a control that inspects an irrelevant unknown.
Freeze cases and decision criteria before running models, and preserve successes.
This is a proposed next slice, not implemented or a decision to change the
final project rules. Avoid adding further mechanics until that comparison
shows what the added decision actually measures.
