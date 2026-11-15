# Greedy-prior follow-up: descriptive evidence only

We ran six new PPO experiments on Modal: three with a programmed greedy prior
and three matched plain controls. Five completed 4096 missions; one prior run
was interrupted after 1760 and was retained without resuming or replacing it.
On 64 reused development worlds, plain PPO improved from its zero-score
deterministic initialization to a three-seed mean of 0.370550; greedy scored
0.363980. The two completed prior seeds scored 0.365150 and 0.363492. Because
the required six-run comparison was incomplete, we left fresh evaluation maps
unopened. The study retains 22,240 training missions, all declared checkpoints
and a learning curve; it does not establish a fresh-world greedy-prior gain.
The six wrappers estimate $2.40437 running CPU/memory, excluding ancillary costs.

Use the completed original learning experiment for the headline submission
claim. This follow-up records the attempted improvement and its limitation.

Figure: [PNG](descriptive/learning-curves.png), [SVG](descriptive/learning-curves.svg).
Evidence and exact limits: [report](descriptive/report.json), [handoff](README.md).
