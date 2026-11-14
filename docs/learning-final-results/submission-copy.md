# Learning evidence for the README and video

## Reusable paragraph

We trained small goal-selection controllers above a fixed navigation scaffold on Modal. On 40 fresh worlds, mean reward rose from 8.3% initially to 35.9% with PPO and 36.3% with a replay learner, averaging three training seeds. On the exact three-mission submission campaign, they scored 36.6% and 33.4%; every latest trained seed exceeded the best recorded Opus attempt (26.7%) and Sonnet attempt (29.3%). Greedy scored 36.7% and the reference 47.6%, so we retain the reference. This is a hybrid-controller comparison with recorded agents, not LLM post-training: the LLM runs retain exit errors, replay's latest checkpoints have unequal budgets, and PPO lost three of 120 rovers on the separate fresh-world check. Training used an estimated $7.26 of Modal CPU/memory, excluding ancillary costs.

## Figure and caption

Use [learning-curve.png](figures/learning-curve.png) at 1920×1080 or [learning-curve.svg](figures/learning-curve.svg). Caption:

> Small-controller learning on 32 reused development worlds, averaged over three initializations. Thin lines retain every seed; bold means appear only at checkpoints reached by all three. Most improvement occurs by 2048 missions. Replay's third seed hit its deadline before the 8192 checkpoint. Fresh-world and submission-campaign comparisons are reported separately.

For a short spoken line, with the fuller limits visible in the README:

> On the same three-mission campaign, every frozen trained controller outscored our recorded Opus and Sonnet agents. PPO averaged 36.6 percent, against the best Opus run's 26.7 percent. Greedy scored 36.7 percent and our reference scored 47.6 percent.

Do not describe this as a neural controller independently beating Opus, a new clean LLM benchmark, full Rainbow, or a learned replacement for the reference. [Campaign evidence and exit caveats](campaign/README.md) · [fresh-world results and PPO deaths](evaluation/README.md) · [training cost](fit/README.md).
