# Claude information-choice pilot

Three of the four frozen Claude trials are complete and independently checked.
All three make the expected-value-optimal information and route decisions with
optimal execution timing. The expensive-probe trial is still running. This is
a diagnostic test of the isolated prototype, not a difficulty claim about the
continuous rover or a final task choice.

| Context | Claude's actions | Claude reward | Same-seed reference |
|---|---|---:|---:|
| Uncertain | Probe, observe soft signal, then detour | 0.325 | 0.325 |
| Likely firm | Skip probe, shortcut immediately | 0.900 | 0.900 |
| Likely soft | Skip probe, detour immediately | 0.400 | 0.400 |
| Costly probe | Running | — | — |

The uncertain result is not a reasoning failure: after the soft signal,
shortcut expected reward is 0.0825 versus 0.325 for the detour. Before the
signal, probing is worth 0.53375 in expectation versus 0.45 without it.
Choosing a detour without probing would have scored more on this realized
terrain, but the agent did not know the terrain before deciding.

The [protocol](lightlag-runs/information-claude-pilot-v1/protocol.json) was
committed in `a7f72ef` before any model call. It fixes one fresh session per
context, no retries, hidden-seed commitments, clear instructions and scripting
permission. Actual harness: Harbor 0.25, OpenCode 1.19.5,
`anthropic/claude-opus-5-5`. Model cost reported so far: **$0.1859414** for
three completed trials. Final cost and seed reveals follow after the last case.

The simulator and hidden state run in a separate container; grading is in a
separate verifier. Real Harbor preflight reference and no-op controls scored
0.325 and 0.0. Agent-container source, evaluator result, evaluator token and
reference policy paths were absent, and an unauthenticated evaluator finish
request returned 404. Forty information-package tests and three packaging
tests passed before the pilot. Independent audit reconstructed every completed
public transcript and protected replay, checked task hashes and matched grades.

[Trial artifacts](lightlag-runs/information-claude-pilot-v1/runs/) retain
protected replays, public tool traces, verifier output, reported usage and
export hashes. [Generated tasks](lightlag-runs/information-claude-pilot-v1/tasks/)
retain exact task files and source hashes. Provider state, raw provider logs
and trajectory message fields stay private; public actions, observations and
metrics are sufficient for the decision audit. Earlier prototype results are
[unchanged](lightlag-information-choice.md).

**Handoff in progress:** retain the last result even if it succeeds. Four
hand-designed development contexts with one session each cannot establish
population reliability. Finish the last case, reveal/check commitments and
publish the complete audit before deciding whether to expand the mechanism.
