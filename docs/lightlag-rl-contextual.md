# Planner-initialized contextual RL: bounded pilot

14 November 2026. Conditional stage two of Kristján's approved follow-up.
The charging-aware development comparison passes its declared screen; training
starts only after its full physics/scaffold audit passes. This branch complements
Sölvi's separately owned scratch PPO/replay campaign. No canonical rules change.

## Fixed interface and data split

Use the unchanged Traverse mission, official normalized terminal reward and
reference navigator. Keep the verified one-visit-and-return charging mask and
persistent science goals. The actor has only public candidate features; no world
seed, hidden state, reward or teacher choice enters its inference input.

Each candidate has the original 14 features, four charging-model features
(visit/return duration, sample duration, battery after sampling, remaining
return slack), and two onward-route features (nearby remaining value weighted
by public travel time, nearest other feasible site's travel time). Append the
science candidates' mean and maximum of these 20 features, giving 60 inputs.
Use a shared 32-unit tanh scorer and softmax: 1,984 parameters. The pooled context
can change the relative ranking of otherwise unchanged candidates. It is not a
full route representation or a learned driving policy.

Reserve **73000–73127 for training**, including teacher rollouts on
**73000–73015** and teacher-label validation on **73016–73019**. RL may use the
entire training range, including those validation maps; label validation is
only a pre-RL imitation diagnostic. Reserve **74000–74015 for the final check**;
do not instantiate or inspect these maps before all checkpoints are fixed.
These ranges are disjoint from Sölvi's 80000/81000/82000 campaign. Already-used
maps 1 and 2 serve implementation smoke tests only.

## Teacher, imitation, and RL

At a new goal decision, run the existing full reference planner on the teacher
pilot's public beliefs and choose the first still-feasible site in its route,
or home. Keep that goal until unavailable. This is a teacher adapted to the
one-goal persistent interface; report its score separately from the unchanged
full-route reference. No teacher search runs during learned-policy inference.
Save all teacher rollouts, features, labels, commands and grades. Train on new
goal decisions only; retained proposals are not independent executed actions.

Train three fixed initializations, **17, 29, 43**, preserving untrained,
imitation-only and final RL checkpoints for each. For imitation, use 200 shuffled
epochs, batches of 32 decisions, cross-entropy, Adam ascent on log likelihood,
learning rate .01 and gradient norm cap 5. Record training and validation loss
and top-one accuracy before and after. The imitation precondition for RL is
at least 20% lower training cross-entropy for each initialization; report held-out
teacher-label accuracy without using it to tune or choose checkpoints. If a
precondition fails, retain it and stop before RL/fresh checking.

For each seed, use **8 updates × 16 complete missions = 128 RL episodes**,
two independent action draws per sampled training map, sampled without replacement
within a batch. Use terminal-reward REINFORCE, the existing within-map pair-mean
baseline and batch advantage standard deviation floor .01. Apply gradients only
to proposals that actually select a new goal; keep retained draws in the audit.
Use learning rate .003, entropy coefficient .005 and gradient norm cap 5.
Do not add shaping rewards, change weights by hand, or select the best seed.

This is a small learning pilot, not a claim that eight updates are sufficient.
Budget: local CPU only, at most four worker processes, 20 teacher missions,
384 RL missions and 320 final-check missions. Limit the whole production run to
3,600 seconds; preserve incomplete progress and do not silently retry. Smoke
tests and deterministic audit replays are additional verification, not extra
optimization. No cloud job or model API call is authorized by this protocol.

## Fixed matched final check and interpretation

On each of the 16 check maps, evaluate all nine fixed neural checkpoints
(three stages × three training seeds) with two action draws, plus one greedy
and one unchanged full-route reference mission: 320 complete 420-tick missions.
Action RNG seed is `1000003 * map_seed + draw`, paired across checkpoints.
The greedy chooser uses the same persistent, charging-aware interface. The
full-route reference uses its unchanged default options and native cadence.
Retain every result, failure, complete replay and decision trace.

Primary comparison: RL minus imitation, averaging action draws and all three
training seeds within each map; report a paired-map 10,000-draw percentile
bootstrap interval, seed 17, and each seed's separate result. A positive pilot
screen requires mean gain at least .02, lower interval bound above zero, no
fewer alive/home outcomes and no extra deaths or invalid commands. Separately
report untrained, greedy and original planner comparisons. Keep the original
reference unless the learned mean also reaches the planner and matches its
return reliability. These engineering screens are not judging requirements.

Publish code/protocol before production; hash all sources and inputs before
teacher collection, checkpoint every update, and freeze every checkpoint before
opening final-check maps. Audits must reconstruct imitation and RL optimizer
updates, choices from recorded features, full evaluation physics and the policy
scaffold. Preserve the distinction between imitation, RL improvement and gains
from the fixed feasibility rule. A learning result alone establishes no Claude
failure; full-agent confirmation remains a separate matched experiment.
