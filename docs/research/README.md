# AfterQuery research

Assessment: [The two teammate prototypes](2026-11-14-prototype-assessment.md)
— independent local reproduction confirms shelving the current sample-chain
version. Ground change has a measurable effect, but its comparator still assumes
the original slip bounds; a simple broader-prior diagnostic makes it worse.
Incorporates the newly landed three-run Opus pilot and four-rule variant: the
pilot is mixed, and the variant's safe reference does not diagnose the change.
This assessment made no paid calls or environment changes. Read this
assessment after the research below before choosing the next experiment.

Latest: [After the survey: which failure should we test next?](2026-11-14-next-mechanism-review.md)
— 14 November, after the completed six-region check. Reviews current evidence
for long-horizon memory, delayed consequences, experiment design and recovery,
including counterevidence from strong coding agents. Recommends testing diagnosis
of changed dynamics versus faulty sensing before building a long campaign;
this remains a hypothesis. No implementation, paid call or team decision.

Companion: [A challenge the reference can reliably solve](2026-11-14-certified-challenges.md)
— Kristján's parallel review proposes a complete collection-to-downlink mission
and an isolated exact-solver probe. Read both before choosing the next mechanism.
The [ground-change prototype](../lightlag-shift.md) is another existing teammate
effort to assess; neither candidate has yet demonstrated a current-model gap.

The earlier reviews below are retained as historical decision support. Their
candidate rankings predate the implemented Lightlag experiments.

## Original 13 November review

Research started Friday 13 November 2026, 22:33 Helsinki. Purpose: understand prior approaches, their successes and failures, and what they imply for a small, convincing AfterQuery environment. This is decision support; no project direction has been selected or implemented.

Start with the [decision brief](afterquery-research.md): our provisional ranking, what worked and failed, the smallest fair experiment, and explicit conditions for dropping each idea. It also maps the evidence to judging and checks Harbor compatibility.

Published deep dives:

- [Agent benchmark landscape](benchmark-landscape.md): ten benchmark families, recent successes, older failures and what changed.
- [Control, routing and optimization](control-and-optimization.md): successful solver/controller approaches, closest prior art and a proposed early falsification test.
- [Reward integrity and evaluation](reward-and-evaluation.md): specification gaming, recovery benchmarks, fair comparisons and proposed exploit probes.

The three deep dives and combined recommendation are complete and published. Independent reviews checked factual scope, comparison fairness and consistency; local document links and Git whitespace checks pass. Primary-source checks did not include executing external benchmark artifacts. The project decision and a measured agent/reference gap remain pending.

The review covers three independent areas: agent benchmarks and long-horizon environments; planning, routing and process control; reward integrity and evaluation design. Findings were pushed in verified increments, then combined into the decision brief. Additional evidence there covers delayed consequences, supply-chain reliability, failure localization and inference latency.

Evidence standard: use primary papers, official repositories and project documentation; identify model/version and evaluation conditions when citing scores; distinguish measured findings from our proposed applications. Older benchmark failures do not prove that today's frontier models will fail. Search cutoff: 13 November 2026; this is a focused review, not a systematic or exhaustive survey.

Our working ideas remain ColdChain, BatchPilot and RecoveryRoom. Read the [shortlist](../../afterquery-ideas.md) and [challenge](https://hackjunction.app/participate/45/challenges/328) alongside this review. The central question is whether we can show a fair, reproducible gap against a credible reference while protecting the reward from shortcuts.
