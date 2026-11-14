# Learning before committing: first experiment

This is a small executable route-choice abstraction. It tests whether selective
information acquisition is useful before we add it to the continuous rover.
It does not replace the current task, demonstrate Claude difficulty, or select
final project rules. The user chose this direction after reviewing real missed
samples and queue gaps, and asked us to evaluate before expanding.

One route leads to a high-value target across uncertain terrain; the other
reaches a smaller target by a known detour. A single soil inspection costs
energy and returns an imperfect signal after a delay. Accepted route choices
cannot be changed. All probabilities, costs and timing rules are public;
only the sampled ground condition and unrevealed signal are private.

## Run

From the repository root, with standard-library Python:

```sh
python3 -m unittest discover -s tests/lightlag_information -v
python3 -m lightlag_information.study --output /tmp/new-information-choice-study
```

Use a new output path: existing evidence is never overwritten. The local
five-method callback interface is for development, not a security boundary.
The [protected Claude pilot](lightlag-information-pilot.md) now supplies a
separate simulator service and Harbor verifier.

## What the comparisons mean

- `never_probe`: choose the best route using the public prior.
- `always_probe`: inspect, wait for its signal, then choose using the posterior.
- `selective`: acquire the signal only when its expected benefit exceeds its
  opportunity cost. It has the same information and resources as the others.
- `blind_probe`: inspect and wait exactly as `always_probe` does, but ignore the
  signal and choose from the prior with the remaining energy. This separates
  the use of information from the expense and delay of acquiring it.

Reward is realized target value minus published completion-time decay, divided
by ten. A failed or incomplete trip scores zero. It is not normalized against
the reference. The uncertain condition stays fixed throughout an episode.
Exactly one physical inspection is available; rereading a result cannot create
new independent evidence.

The exact reference considers the finite alternatives with and without that
one observation. This is a small Bayesian decision problem, not a claim of an
optimal controller for full Lightlag. Expected results weight every hidden
state/signal pair by its public probability. Seeded realized outcomes are
reported separately, never substituted for exact expectation.

## Evaluation and decision

The four contexts were frozen before execution: uncertain terrain, likely
firm terrain, likely soft terrain, and an expensive probe. They are deliberately
constructed development cases, not a representative or unseen mission sample.
The same public model should sometimes choose to inspect and sometimes decline.

The first gate is selective performance above both fixed strategies across
the four contexts, with both behaviors used. Verify every weighted branch
against the analytical value, then retain all 0–39 seeded episodes separately.
The saved results and verification follow below.

The next gate is actual model behavior with clear instructions and scripting
allowed. Success by Claude would be useful evidence that this small task is
solvable; it would not justify quietly changing the test until Claude fails.
Only after that test should we decide whether to integrate terrain probing into
the rover or add another interacting decision.

Continuous integration must preserve legitimate learning from movement:
battery, local terrain and odometry already reveal information in Lightlag.
Those signals should count as available evidence, rather than be suppressed to
force the new tool. Manh's biome and controller experiments remain separate.

## Recorded result

The structural gate **passes**. These are exact expectations over the declared
terrain and sensor probabilities, with equal weight across the four contexts:

| Context | Never probe | Always probe | Selective | Blind probe |
|---|---:|---:|---:|---:|
| Uncertain | 0.45000 | 0.53375 | 0.53375 | 0.41250 |
| Likely firm | 0.85500 | 0.78375 | 0.85500 | 0.78375 |
| Likely soft | 0.40000 | 0.32500 | 0.40000 | 0.32500 |
| Costly probe | 0.45000 | 0.41250 | 0.45000 | 0.41250 |
| Mean | 0.53875 | 0.51375 | **0.5596875** | 0.4834375 |

Selective probes only in the uncertain context. Its aggregate gain is
**0.0209375** over never probing and **0.0459375** over always probing. The
uncertain-context comparison with the timing-matched blind control attributes
0.12125 expected reward to using the signal under that fixed sensing strategy.
These deliberately small constructed gains are not evidence of model failure.

The separate 640 seeded smoke episodes average 0.51515625 selective,
0.4825 never, 0.4725 always and 0.431875 blind. Those finite seeded results differ
from the exact expectations and are not substituted for them. Seeds are paired
across policies, not independent replications of an agent.

[Protocol and source hashes](lightlag-runs/information-choice-v1/protocol.json),
[full summary](lightlag-runs/information-choice-v1/summary.json),
[64 weighted branches](lightlag-runs/information-choice-v1/exact_rows.jsonl),
[640 seeded rows](lightlag-runs/information-choice-v1/seeded_rows.jsonl), and
[all 704 replays](lightlag-runs/information-choice-v1/replays.jsonl) are retained.
Root reconstructed every transcript/replay, checked all nine source hashes,
and independently enumerated legal relevant probe/commit timings and contingent
route choices using exact rational arithmetic. All 29 package tests pass;
independent review found no remaining blocker. Existing evidence is untouched.

**Handoff:** the [subsequent protected Claude pilot](lightlag-information-pilot.md)
is complete: all four information/route decisions and timings match the exact
reference. Total reported pilot cost is $0.2266114; this original scripted slice
cost $0. The mechanism works, but these four model trials expose no reasoning
gap. The pilot page records limitations and a proposed next experiment on
choosing between competing observations. Expansion and final task selection
remain open. The current canonical Harbor task and continuous rover are unchanged.
