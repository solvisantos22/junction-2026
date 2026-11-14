# Stereo survey: a bounded mission experiment

14 November 2026. Owner: Kristján / Codex. The user approved testing the stereo-survey idea after [the scheduling probe](research/2026-11-14-certified-challenges.md). This experiment does not replace the canonical task or modify the existing demo.

## Hypothesis and public contract

The mission is to return useful three-dimensional terrain coverage. A ground cell earns its published weight only when **two returned images** cover it with a sufficient difference in viewing direction, acceptable pixel-scale ratio and bounded time separation. A single image can contribute to multiple pairs; covering a cell twice does not double its reward. This tests complementary observations and shared resources, not merely independent delivery jobs.

The first prototype uses two camera platforms on public, fixed flight tracks above a flat ground plane. It is a discrete photogrammetry planning abstraction, not an orbital dynamics simulator. All opportunities, positions, orthorectified rectangular footprints, pixel scales, budgets and communication windows are public. Coordinates are metres: x east, y north, z up; the ground is z=0. Angles are degrees. A provided geometry helper defines the calculation and a worked example tests the convention.

At each opportunity the platform can take at most one of two offered images or skip. Images require energy and memory; changing camera orientation requires slew time and energy. A fixed, public FIFO downlink service transmits stored images during known windows. Every selected image must be returned within the horizon, so a submitted plan must fit the whole resource timeline. There is no noise, hidden seed, real-time clock or privileged reference observation.

This is deliberately small enough for an exact reference: enumerate all feasible observation sequences for each platform, then examine their joint plans with a valid upper bound. A completed exhaustive search proves the optimum; a resource cap must be reported as an incomplete reference. The submitted plan is checked separately by reconstructing the chronological timeline and science products. A feasible plan alone is not a proof of optimality.

## Test order and stop conditions

1. Check geometry against analytically known examples, resource boundaries, and a tiny exhaustive oracle that does not use the optimized search.
2. Compare a single-image coverage heuristic, pair-aware greedy policies, a greedy portfolio and a generic pair-aware beam search. Do not call scripted controls model agents. Compare with a matched monocular version that rewards the same cells from one returned image.
3. Development may change the generator or algorithms. Freeze sources, exact-search limits and fresh seeds before opening check cases; retain every case and all failed/capped reference results.
4. A free screening gate requires all reference results to be proved and replay-valid, with the best greedy portfolio at most 90% and the strongest generic beam control at most 95% of the stereo optimum on average. Also report the monocular control, absolute science, exact-optimum frequency and run cost. The thresholds are engineering screening choices, not statistical proof of a model weakness.
5. If generic search nearly saturates the ceiling, reject this configuration for a full environment build. If a model pilot is justified, package public rules, geometry and validation with code/solver access; freeze the strongest available model configuration, prompts, held-out cases and bounded spend before launching. Do not infer permission to consume an unrelated session's API budget.

The source inspiration is [AstroAgentBench](https://aclanthology.org/2026.aacl-long.72.pdf), particularly its stereo products and the specification issues it reports. This is a new, simplified experiment, not a reproduction of its results, physics or benchmark.

Implementation and results will be recorded here. No new model failure is established by this design.
