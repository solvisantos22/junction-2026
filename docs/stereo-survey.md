# Stereo survey: a bounded mission experiment

14 November 2026. Owner: Kristján / Codex. The user approved testing the stereo-survey idea after [the scheduling probe](research/2026-11-14-certified-challenges.md). This experiment does not replace the canonical task or modify the existing demo.

**Complete free experiment: this configuration fails the difficulty gate.** The reference proves the optimum on all 48 fresh missions, and the predeclared beam-search portfolio also reaches every optimum. Stereo pairing is a real requirement, but small generic search solves it. No LLM was run, and no API spend was incurred.

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

## Initial development

The implementation is in [stereo_survey](../stereo_survey/README.md), with 12 focused tests. The retained [development run](stereo-survey-results/development.json) covers seeds 0–11 at 24 and 32 candidate images, both stereo and matched monocular scoring. No performance filtering occurred.

Coverage-only greedy reaches approximately 15–17% of the proved stereo ceiling, while pair-aware greedy portfolios reach approximately 96%. The beam portfolio matches all **23 proved** stereo optima. Expanded seed 11 hit the two-million-joint-plan cap: reference and beam both scored 36, but that is only a best-known value until the exhaustive search finishes. The incomplete case stays in the report. All 24 monocular references prove optimal.

This validates complementary images as a real requirement, but the planning problem is currently easy for generic pair-aware search. Complete the bounded reference proof and one fixed fresh check before the final decision. No new model failure is established, and no API/model call has been made.

## Reference completion and frozen fresh check

The capped development case was rerun with a ten-million-joint-plan allowance; the unchanged exact algorithm completed after **2,348,648** evaluations and proved science **36** optimal. The original capped report is preserved, alongside [the completion run](stereo-survey-results/development-reference-completion.json). It is the same development instance, not new evidence. All 24 development stereo optima are now known, and the beam portfolio reaches every one.

Before opening fresh results, freeze this protocol:

- Generator `stereo-survey-v1`, unchanged geometry and algorithms; compact and expanded profiles.
- Seeds **41000–41023** for each profile: 48 new missions, each scored under stereo and matched monocular objectives.
- Exact caps: 10,000 feasible local schedules per platform and **10,000,000** joint-plan evaluations. Retain capped cases; no retry or subset selection on check data.
- Controls: coverage-only greedy, pair greedy, pair density, image beam 64, pair beam 64, best-of-three greedy and best-of-two beam portfolios. The portfolios can use the public checker, never the optimum.
- Gate remains unchanged: every reference proved/replay-valid/nonzero, greedy portfolio at most 90%, beam portfolio at most 95%. Development already fails the difficulty thresholds; the cheap check validates that outcome rather than searching for a favourable seed.
- Preserve all source hashes, plans, raw science and exclusion counts. Profiles sharing a numeric seed are correlated; report descriptive means, not independent-trial confidence intervals.

The initial run predates a command-line-only improvement that exposes search caps and returns exit code 2 for incomplete proof. Its exact original `__main__.py` is retained by hash under `stereo-survey-results/source-archive/`; generator, geometry, study, search and replay source are unchanged. This wrapper was not used by the study.

## Fresh results and decision

The protocol was published in [`845cac7`](https://github.com/solvisantos22/junction-2026/commit/845cac7) before opening the fresh cases. The full [check report](stereo-survey-results/check.json) retains every mission and policy plan. No capped, invalid or zero-optimum case occurred on check, and no case was retried or filtered.

| Fresh stereo check | Compact: 24 candidate images | Expanded: 32 candidate images |
|---|---:|---:|
| Reference proved optimal and replayed validly | 24/24 | 24/24 |
| Reference mean raw science | 42.5833 | 50.4583 |
| Coverage-only greedy, fraction of optimum | 28.05% | 18.63% |
| Best greedy portfolio | 92.10% | 93.67% |
| Image beam 64 | 100.00% | 99.62% |
| Pair beam 64 | 100.00% | 99.81% |
| Predeclared beam portfolio | **100.00%** | **100.00%** |
| Beam portfolio reaches the exact optimum | 24/24 | 24/24 |

The two beams miss different expanded cases. Choosing the higher raw science using the public checker recovers all 24 expanded optima; this portfolio was declared before the check and has no access to reference scores. Even either beam alone nearly saturates the ceiling. Both profiles fail the unchanged greedy and beam thresholds.

The monocular control confirms the mechanism: coverage-only greedy gets **99.57% / 100.00%** of its monocular optimum, versus **28.05% / 18.63%** of the stereo optimum on the same missions. It is good at collecting coverage and poor at assembling stereo products. All 48 monocular references and beam portfolios attain their own optima. This is an objective ablation, not evidence that an LLM misunderstands stereo.

For a concrete example, the **first** compact check mission, seed 41000, gives coverage-only greedy science **6** from four frames and one useful pair. The reference gets **46** from six frames and seven useful pairs; pair-aware greedy gets **43**. The mechanism is visible, but it is largely solved once the policy understands pairs.

All 48 fresh stereo proofs completed within 2,748,437 joint evaluations; the slowest took 1.62 seconds on this machine. These are diagnostic timings with shared compilation/cache effects, not a fair speed comparison. Reference success here means reaching the achievable optimum, not mapping every listed cell. There is no claim that a capped solver would always finish on arbitrary larger instances.

**Decision: keep this as a reproducible prototype and reject this configuration for a full replacement environment or a paid difficulty pilot.** Making the option list larger is not supported by these results. The experiment does not rule out richer stereo tasks: it supplies finite candidate frames and rectangular ground footprints rather than asking an agent to construct observations with continuous pointing, orbital geometry or terrain occlusion. Those would be different hypotheses requiring their own transparent contract and reliable reference.

## Verification and handoff

- Twelve focused tests pass. The tiny independent oracle checks every image subset on six missions under both objectives (3,072 subset/objective checks); geometry conventions and boundary conditions are separately tested.
- A command-line generate → solve → verify round trip succeeds with science 44 and a proved optimum.
- The post-write audit verifies current/archived source hashes, regenerates all **72 distinct missions**, replays all **1,168 saved policy records**, checks product counts and covered cells, and reconstructs every summary. Counts include portfolio copies and the repeated development completion case; they are not 1,168 independent trials.
- The original capped development result remains intact. The check seeds 41000–41023 are now used for this experiment; any changed generator or follow-up requires a new protocol and fresh check data.
- No model/API call, model failure, canonical-task promotion, rover/shift modification or demo change occurred. No model-pilot files were created after the free gate failed.
