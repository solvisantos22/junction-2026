# AfterQuery research

Research started Friday 13 November 2026, 22:33 Helsinki. Purpose: understand prior approaches, their successes and failures, and what they imply for a small, convincing AfterQuery environment. This is decision support; no project direction has been selected or implemented.

Start with the [decision brief](afterquery-research.md): our provisional ranking, what worked and failed, the smallest fair experiment, and explicit conditions for dropping each idea. It also maps the evidence to judging and checks Harbor compatibility.

Published deep dives:

- [Agent benchmark landscape](benchmark-landscape.md): ten benchmark families, recent successes, older failures and what changed.
- [Control, routing and optimization](control-and-optimization.md): successful solver/controller approaches, closest prior art and a proposed early falsification test.
- [Reward integrity and evaluation](reward-and-evaluation.md): specification gaming, recovery benchmarks, fair comparisons and proposed exploit probes.

The three deep dives and combined recommendation are published. A final independent evidence audit is in progress.

The review covers three independent areas: agent benchmarks and long-horizon environments; planning, routing and process control; reward integrity and evaluation design. Findings are pushed as verified sections are ready, then combined into the decision brief.

Evidence standard: use primary papers, official repositories and project documentation; identify model/version and evaluation conditions when citing scores; distinguish measured findings from our proposed applications. Older benchmark failures do not prove that today's frontier models will fail. Search cutoff: 13 November 2026; this is a focused review, not a systematic or exhaustive survey.

Our working ideas remain ColdChain, BatchPilot and RecoveryRoom. Read the [shortlist](../../afterquery-ideas.md) and [challenge](https://hackjunction.app/participate/45/challenges/328) alongside this review. The central question is whether we can show a fair, reproducible gap against a credible reference while protecting the reward from shortcuts.
