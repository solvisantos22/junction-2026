# Submission copy — final RL–greedy comparison

## Copy-ready paragraph

On 256 previously unused Traverse worlds, an ensemble of six trained policies
guided by a greedy shortlist scored **39.31%**, versus **38.40%** for greedy.
The paired gain was **+0.91 percentage points** (95% interval **+0.32 to +1.52**),
and every hybrid mission returned home alive. This is a small measured gain,
just below our predeclared 1-point target. The frozen reference scored
**51.27%** and remains the reference.

## Short spoken version

“Combining six trained policies with greedy guidance gave a small improvement
on 256 unseen worlds: 39.31% versus 38.40%, with every rover home alive. It
missed our one-point target and still trails the stronger reference.”

## Figure and caption

[1920×1080 PNG](completed/figures/comparison.png) ·
[Vector SVG](completed/figures/comparison.svg) ·
[Full result and audit](completed/README.md).

**Caption:** Final comparison on the same 256 untouched worlds (612000–612255).
The hybrid is an all-six rank ensemble with a fixed 90% greedy-efficiency
shortlist. Mean reward improves by 0.907 percentage points over greedy; the
paired 95% map-bootstrap interval is +0.323 to +1.518 points. The registered
1-point minimum is not met. All 2560 cases across ten arms finished home and
alive, with zero invalid calls. Policies and selection were published before
the final worlds; the reference is unchanged.

## Keep these distinctions when editing

- This experiment combines **existing trained weights**. It is not another
  training run, an LLM fine-tune, or evidence that RL beats all LLM agents.
- The trained policies use the team's hand-written navigator and feasibility
  logic. All six retained policy roles are used; there is no best-seed choice.
- The interval is conditional on the fixed learned policies and uses 20,000
  paired map resamples. Report the small gain and missed target together.
- For a learning-curve/before–after story, use the separately audited
  [original learning figure and copy](../../learning-final-results/submission-copy.md).
  Those are different matched map sets; do not combine their scores with this
  final table or imply a 39.31% training endpoint.
- Sölvi requested no further experiments with 3–4 hours left. The remaining
  work is integrating these verified assets into the team's submission.
