# Prize evidence log

Started 14 November 2026. **Maintain this alongside meaningful shipped work, not every prompt or bookkeeping commit.** Its purpose is to make actual sponsor use easy to demonstrate and accurately attributed. A log entry is not a prize entry or proof of eligibility.

## Prize focus and source freshness

Recommendation: AfterQuery as the primary challenge, Best Use of Codex as the natural additional entry, and at most one compute provider if it becomes useful. A model prize is conditional on a substantive integration. Tech challenges can accompany the main track. [Official Junction overview](https://2026.hackjunction.com/)

The detailed sponsor briefs were last read directly on the logged-in platform on **13 November, about 22:10 Helsinki**, as recorded in [SPONSOR_OPTIONS.md](../SPONSOR_OPTIONS.md). Direct Chrome/Discord access was blocked during this 14 November audit, and the authenticated prize pages were unavailable through web search. The table below carries that freshness limit; it does not imply a fresh confirmation of eligibility, balances, separate forms or entry status.

| Prize / opportunity | Current decision and actual evidence | What to retain if pursuing it | Entry status |
|---|---|---|---|
| **AfterQuery — Break the Agent** | Primary provisional challenge. Kristján delivered original-task model evidence (Opus 1.0); Codex integrated the dynamic task and ran fresh Opus trials on `rush` and `rush_noisy`, both 1.0. All match their reference: no model gap demonstrated on these examples. [Requirements and gaps](afterquery-readiness.md). | Harbor task/version, real model logs/configuration, 0–1 verifier score plus raw diagnostics, fair reference/baseline comparisons, exploit probes and demo. | Lightlag draft recorded; final submission not verified. |
| **[Best Use of Codex](https://hackjunction.app/participate/45/tech-challenges/49)** | Recommended additional entry; substantial development/review work is evidenced below. Last-read brief asks for meaningful use to build, iterate and ship. | Concrete task/prompt summary → Codex change → review/test → commit/result. Keep a few safe genuine session captures and one concise development story. | Selection/submission and any evidence/form specifics still need a live check. No mandatory screenshot format is established by this log. |
| **[Modal](https://hackjunction.app/participate/45/tech-challenges/40) OR [Verda](https://hackjunction.app/participate/45/tech-challenges/56)** | Conditional infrastructure candidate. Sölvi's Modal grant is confirmed in the [credit notes](../SPONSOR_OPTIONS.md). **Modal jobs are now recorded:** Kristján's Traverse rollout farm (about 6,000 missions, about 105 core-hours; app IDs in its entry below) and Sölvi's RL training (R19 and the learning campaign). Batch jobs only so far: no live deployed endpoint, which is 15% of the Modal score. | Actual deployment/job ID and configuration, what ran, logs/metrics, live demo or results, and why the service mattered. Verda's last-read brief also asks for a process summary link in its Discord channel; capture that requirement, but do not post automatically. | Not verified entered; choose based on real infrastructure needs. |
| **[Gemini](https://hackjunction.app/participate/45/tech-challenges/48)** | Conditional if it meaningfully operates/evaluates the environment and fits AfterQuery's permitted-model requirements. User confirms the team credit application is submitted; no Gemini run or approved balance is verified. | Exact model/API configuration, role in the system, actual usage/run artifacts, outcome and a visible explanation of its value. Verify that benchmark use satisfies the current prize brief. | Not verified entered; usable API funding remains unknown. |
| **[Gemma](https://hackjunction.app/participate/45/tech-challenges/47) / [Nemotron](https://hackjunction.app/participate/45/tech-challenges/46)** | Parked unless open-model evaluation or training becomes part of the actual project. Training is not a prerequisite for the new AfterQuery minimum. | Exact qualifying model/version/endpoint, real integration and measured results. The previously noted Nemotron model-name mismatch must be resolved before claiming eligibility. | Not verified entered. |
| **Other sponsors** | Keep the full [sponsor inventory](../SPONSOR_OPTIONS.md) available; no extra database, audio, web-data or hardware feature is proposed just for a checkbox. | Add a row only when the service has a useful implemented role; record any separate submission requirement. | No entry inferred from tool availability or redeemed credits. |

The OpenAI participant pack was previously recorded as **Codex usage credits, not API inference credits**. AfterQuery's [credit cancellation](afterquery-update-2026-11-14.md) does not change that distinction. Using a provider and having an API budget are separate from prize selection.

## Backfilled Codex evidence

These rows were reconstructed from repository commits, designs, tests, handoffs and the project conversation on 14 November. They are **task summaries, not preserved verbatim prompts or a complete session recording**. Product attribution is Codex; an exact underlying model/version was not recorded here and is not inferred. Verification counts refer to the recorded increment, not fresh test runs during this documentation audit.

Human direction: the user requested development on the provisional draft, approved the reference/evaluation block, required public claims and small verified pushes, and retained the final project choice. Codex performed implementation and separate Codex-agent specification/quality reviews. Those agent reviews are not represented as human line-by-line review.

| ID / date | Task / prompt summary | Codex contribution and outcome | Verification and concrete proof |
|---|---|---|---|
| C01 · 13–14 Nov | Start the submitted Lightlag draft with a testable headless environment. | Implemented deterministic delayed commands/telemetry, terrain movement, energy, hazard safety, true-position sampling and fixed-horizon reward; added JSON-lines execution and evaluator replays. | [Movement core](https://github.com/solvisantos22/junction-2026/commit/d6de7ef), [scoring/safety](https://github.com/solvisantos22/junction-2026/commit/6fad400), [runner/handoff](https://github.com/solvisantos22/junction-2026/commit/92652eb). Recorded 34 simulator/CLI tests; [design](superpowers/specs/2026-11-13-lightlag-core-design.md), [handoff](lightlag-handoff.md). |
| C02 · 14 Nov | Run controllers through only the published tools and retain auditable episode evidence. | Built `PublicTools` and `run_episode`; completed the horizon after early returns and preserved copied transcripts. Review caught a case where a policy could catch an invalid request and still receive a score; this now fails visibly. | [Public-runner commit](https://github.com/solvisantos22/junction-2026/commit/73098c6), [regression tests](../tests/lightlag/test_evaluation.py). Recorded 47 tests at that increment. |
| C03 · 14 Nov | Build a reference and diagnostic baselines using public information. | Implemented slip learning, queued-command prediction, routing and return budgeting. Fixed delayed sample confirmation and escape from an inflated hazard margin. Measured the conservative reference's 3/4 ceiling and documented its limitations. | [Controller commit](https://github.com/solvisantos22/junction-2026/commit/6e580fc), [controller regressions](../tests/lightlag/test_controllers.py), [design/decisions](superpowers/specs/2026-11-14-lightlag-reference-design.md). Recorded 73 core/controller tests. |
| C04 · 14 Nov | Reconcile overlapping controller work and produce one reproducible comparison path. | Preserved Kristján's implementation, adapted both families into shared batch execution, added explicit reference ratios and deterministic score/replay exports. Selected his stronger controller as the current fixed-map denominator based on evidence; did not tune physics to force a gap. | [Batch evaluator](https://github.com/solvisantos22/junction-2026/commit/934735e), [published evidence](https://github.com/solvisantos22/junction-2026/commit/36536de), [480-episode results/raw CSVs/manifest](lightlag-reference-results.md). Recorded 99 core/evaluation + 25 teammate tests; 480 episodes/replays verified. |
| C05 · 14 Nov | Let the dynamic pilot use the shared evaluator without replacing a module global. | Added an evaluator-only environment factory while preserving the five-tool interface, default behavior and full-horizon grading. | [Integration commit](https://github.com/solvisantos22/junction-2026/commit/ae112ba), [API example](../lightlag/README.md#run-a-policy-through-public-tools). Recorded 105 core + 12 dynamic + 25 teammate tests; the seed-3 dynamic episode's complete result/replay matched the pilot runner. |
| C06 · 14 Nov | Continue after obtaining model credits; test the delivered time-pressure profiles while preserving teammates' canonical task. | Built an external Harbor task generator and a public-tool-only controller entry point, with explicit parameters and source/task hashes. Chose seed 500 before inspecting results; preserved the original model's 1.0 result and kept final rules provisional. The user supplies a key through a Git-ignored local file; no secret is part of these artifacts. | [Generator commit](https://github.com/solvisantos22/junction-2026/commit/0bc0d43), [regression tests](../tests/lightlag_experiments/test_prepare.py), [results and handoff](lightlag-experiments.md). Four generator tests and all 11 Harbor tests with MCP 2.3.0 passed; independent Codex review found no blockers. Four real Docker/Harbor runs on `rush`, seed 500, delay 3 matched direct results: KF + MPC 1.0, blind 0.571429, whole-leg waiting 0.535714, no-op 0.0. Direct delay-0 waiting scored 1.0. Initial scripted evidence; the subsequent real model run is recorded separately as R01 below. |

Supporting collaboration evidence: [shared workflow skill commit](https://github.com/solvisantos22/junction-2026/commit/d2f3be6), [public task claims](../TEAM_STATUS.md), [increment/review plan](superpowers/plans/2026-11-14-lightlag-reference.md), and the preserved teammate commits. Avoid claiming time saved, an autonomous-development percentage or a frontier-agent performance gap without corresponding measurements.

### Strong examples to capture for the submission

1. **A real debugging improvement:** the invalid-call regression in C02, or the sample-confirmation/hazard-margin regression in C03. Show the problem, specific change and passing check. Existing tests prove the behavior; preserve a genuine project-session excerpt or a clearly labelled later demonstration rather than inventing an original failure screenshot.
2. **Evidence changed the plan:** C04 showed that the teammate's reference was stronger; Codex integrated it and recorded negative findings about its own planner instead of hiding them.
3. **Shipping with concurrent teammates:** a public claim, reviewed diff, test result and main-branch commit from one coherent increment.

These are recommended evidence choices, not newly asserted official entry requirements. A short demonstration of two strong examples is more useful than an unfiltered chat dump. Preserve only project-relevant, safe excerpts; credentials and private conversations do not belong in this repository.

### Attribution boundary

- **Kristján / Claude Code:** the adaptive `lightlag_controllers/` family, `lightlag_mcp/` service, `harbor/` task/reward adapter (`d2dee96`), first real model run and replay viewer (`180e504`). Codex integrated, inspected and tested these; it did not author them. Also the 3D Mars demo (`viewer/mars/`, `viewer/mars-demo.html`), built in Kristján's Claude Code session at his request.
- **Manh / Claude Code:** `lightlag_dynamic/`, noisy-sensing/Kalman/MPC work and the dynamic MCP entry point (`fb9ae07`, results `b4bdd2e`). C06 uses those delivered components unchanged. The additional controller collection (`b867839`) landed during publication and is outside C06's frozen comparison.
- **Codex:** the specific implementations/reviews/integration work listed above. Collaboration is part of the story; it does not justify crediting every repository file to Codex.

## Recorded model use

### R01 — 14 November — Claude solves the time-pressured pilot

- Sölvi supplied local API access and authorized the run. Codex orchestrated and
  checked the experiment; **OpenCode 1.19.5 / Anthropic Claude Opus 5.5** played
  the mission. Simulator/service/controller authorship stays with the team
  attribution above.
- One attempt on the exact frozen `rush`, seed 500, delay 3, horizon 50 task from
  `0bc0d43`; no retries. Reward **1.0**, all six targets on time, alive at base.
  Reported API cost **$0.4821436**, 30 public rover tool calls, trial 236.54 s.
- Codex checked verifier/replay consistency, exact task identity, agent/version
  metadata and credential-free exports, and preserved the negative finding:
  this setting did not expose a model gap.
- Evidence: [complete run](lightlag-runs/rush-seed500-delay3-opus-5-5/),
  [comparison and observations](lightlag-experiments.md),
  [machine-readable summary](lightlag-runs/rush-seed500-summary.json).
- Relevant to AfterQuery's real model evidence and an accurate Codex development
  story. This is not Gemini/Modal use or a claim of extra-prize eligibility.

### R02 — 14 November — Claude solves the matched noisy pilot

- Sölvi / Codex continued the authorized evaluation using **OpenCode 1.19.5 /
  Anthropic Claude Opus 5.5**. Claim `7c2c98d` fixed seed 500, delay 3, horizon
  50, `rush_noisy`, noise level 1 and bumpiness 0 before results were inspected.
- Codex verified identical map/source bytes to R01 and only the declared task
  name/profile configuration changes. Four scripted Harbor controls matched
  direct runs, including the unchanged KF + MPC at 1.0.
- One fresh model attempt, no retries: **1.0**, all six targets on time, alive at
  base, 29 public rover tool calls, trial **246.31 s**, reported cost
  **$0.4642194**, no execution exception. R01 + R02 report **$0.946363** total.
- Evidence: [model run](lightlag-runs/rush-noisy-seed500-delay3-opus-5-5/),
  [matched controls and interpretation](lightlag-noisy-experiment.md),
  [summary](lightlag-runs/rush-noisy-seed500-summary.json). Export checks cover
  credentials, manifest identity and score/cost consistency. An independent
  Codex evidence review found no blocking issues.
- The team has successful model examples, not a demonstrated deficit. The
  handoff recommends additional predeclared seeds and decision auditing before
  choosing final rules. No Modal/Gemini use or additional-prize entry is implied.

### R03 — 14 November — Eight fixed-seed model attempts and decision audits

- The user approved the additional comparison. Sölvi / Codex published protocol
  `02e4f70` before outcomes: seeds 501–504 on both profiles, unchanged rules,
  original KF + MPC, one fresh attempt per cell, no retries. Codex orchestrated
  **OpenCode 1.19.5 / Anthropic Claude Opus 5.5**; this does not attribute the
  playing model's decisions to Codex or Claude Code.
- Codex froze eight tasks, verified eight Harbor references against 32 direct
  public-tool controls, exported all eight model attempts, and ran Manh's
  delivered decision auditor. All source/task/auditor hashes stayed fixed while
  teammates' other updates were integrated. Each model/reference task pairs
  exactly; every audit replays exactly with zero infrastructure findings.
- Complete outcome: **3 model wins, 2 ties, 3 deficits**. Mean Claude/reference
  reward: rush **0.554808 / 0.724679**, noisy **0.544071 / 0.690224**. No general
  reliability or noise-causality claim: four maps per profile, one attempt each.
- Codex connected two battery deaths and one queue-timing loss to the protected
  traces and published rules. Independent review prompted a check of the
  reference continuation's limits: after call 11 in seed 501, foregoing the
  later return could still salvage 5.25/12. Two explicit post-hoc continuation checks are
  saved; reference-relative attribution is kept separate from optimality.
- Reported API usage **$3.3513574** for the eight attempts; R01–R03 together
  report **$4.2977204** for ten attempts. These are agent usage reports, not
  verified invoices, grant sources or balances. No Modal or Gemini usage.
- Evidence: [complete protocol, per-run table, analysis and handoff](lightlag-fixed-seed-comparison.md),
  [summary](lightlag-runs/fixed-seeds501-504-summary.json),
  [all eight decision audits](lightlag-audits/fixed-seeds501-504/README.md).
  Reference increment `5925236`, seed-501 evidence `ddd650a`, seed-502 `ed1c4fd`,
  seed-503 `8535225`. Independent reviews approved every increment and the complete comparison,
  including the final aggregates, execution checks and both counterfactuals. Credential/path scans, exact task
  pairing, reward/cost checks and local links passed.
- Team components keep their original authorship. Codex's contribution is the
  experiment, verification, interpretation and repo handoff. All mixed outcomes
  are retained; final rules/project choice and prize entry remain team decisions.

### R04 — 14 November — Independent overnight challenge review

- The user asked Codex to continue autonomously, broaden the research and
  challenge the team's direction while they slept. Two independent Codex
  research passes examined current primary literature, real operations,
  alternative ideas and the complete mixed eight-attempt evidence.
- Delivered [evaluation review](research/2026-11-14-lightlag-evaluation-review.md)
  and [direction review](research/2026-11-14-lightlag-direction-review.md).
  They recommend a rule-equivalent accounting aid, separate reference testing,
  fresh confirmation and narrower claims; no final project/rules decision.
- Verification: researchers opened the cited primary sources, checked local
  links and recomputed the score/energy decomposition. Root checked the
  decisive energy contract and sampled primary-source claims. These are
  critical reviews and proposed experiments, not new model results.
- Research used Codex and web sources, with no Claude inference, Modal or
  Gemini usage. Actual paid overnight attempts are tracked separately in the
  [protocol and run ledger](lightlag-overnight-evaluation.md).

### R05 — 14 November — Failure-selected overnight repetitions

- Under the user's overnight credit authorization, Codex declared nine fresh
  attempts at `253b263`, kept original tasks/model/harness fixed, and retained
  every result. The playing agent is **OpenCode 1.19.5 / Claude Opus 5.5**;
  Codex orchestrates and checks it using Manh's delivered auditor.
- First four attempts: rewards **0, 0.461538, 0.75, 0.833333**; reported cost
  **$1.849386**. These are selected-case repeats, not a map-wide failure rate.
  A battery failure recurs, and two later runs match or beat the reference.
- Independent Codex review reproduced all four audits, confirmed fresh task
  identity and sanitized exports, and challenged a heuristic intended-target
  diagnosis. The report preserves that caveat rather than turning a tag into
  a claim about model intent. No simulator or canonical task changed.
- Evidence: [protocol and checkpoint](lightlag-overnight-evaluation.md),
  [machine-readable ledger](lightlag-runs/overnight-a-summary.json),
  [audit index](lightlag-audits/overnight/README.md). Five attempts remain in
  this declared block at that checkpoint. A05–A08 now add **0.769231, 0, 0,
  0.807692**, bringing reported usage to **$3.4394028** for eight attempts;
  all eight replay exactly without infrastructure findings. A09 completes the
  block at **0.6**, alive at base. Final A total: **$3.9709816**, 2 wins, 2 ties,
  5 deficits and 3 battery deaths; all nine exact replays, no infrastructure
  findings. All original selection triggers stay separate from repeat counts.
- Usage reports are not verified balances. No Modal/Gemini use or prize entry.

### E07 — 14 November — Decision-focused offline replay demo

- Sölvi asked Codex to build the decision demo and continue independently
  overnight. Codex wrote a reviewed design, delegated implementation, and
  conducted independent spec/quality reviews and browser verification.
- Delivered [three-case offline page](../viewer/decisions.html) and
  [rebuild/walkthrough](lightlag-decision-demo.md), using the team's existing
  simulator, saved runs and Manh's auditor. It distinguishes protected truth,
  noisy delayed packets, accepted commands, post-hoc continuations and an
  independently played reference. The full mixed comparison stays prominent.
- Verification: all 13 viewer tests; both continuations match saved scores and
  batteries; source replay bytes and original viewer preserved. Chrome checked
  offline loading, controls, keyboard and three viewport widths. Review fixed
  unsafe HTML-tokenizer edge-case escaping and a commanded-heading arrow that
  could be mistaken for true orientation. No paid calls for this demo.
- Human decisions remain provisional; this is evidence presentation, not a new
  model result, final rules choice or prize submission. Author attribution for
  existing teammate components is preserved. Codex model version unrecorded.

### R06 — 14 November — Separate capable-reference study

- Codex predeclared candidate 24 versus the original KF + MPC, froze the source
  independently of teammates' live work, and ran 96 public-callback episodes.
  The policies themselves retain their original team authorship.
- All eight historical reference replays reproduce exactly. Candidate 24's
  fresh rush mean gain is **0.007898**, with 3 wins, 16 ties and 1 loss; all
  noisy-profile scores tie. Every episode survives at base. These results do
  not change the canonical reference or prove general model difficulty.
- Verification: independent review, 96 exact transcript replays / 6,310 calls,
  ten representative policy reruns, 100 byte-identical reproduction files and
  five runner guard checks. Full source hashes, dependency versions, errors
  (none), complete trajectories and the retrospective model comparison remain.
- Evidence: [study and commands](lightlag-runs/overnight-reference-study/README.md),
  [verification](lightlag-runs/overnight-reference-study/verification-final.json),
  [runner](../tools/lightlag_experiments/overnight_references.py). No paid
  inference, Modal or Gemini usage. Project/reference adoption remains a team
  decision; Codex's contribution is experiment engineering and critical review.

### R07 — 14 November — Preserve a negative reference comparison

- Codex separately declared candidate 27 on 48 already inspected cells, then
  ran and checked all episodes against the unchanged earlier reference study.
  The controller remains Manh's work; Codex contributed the isolated study,
  dependency checks, complete evidence and independent critical review.
- Candidate 27 finishes every episode alive at base, but its inspected-set
  means, **0.754040 rush / 0.677788 noisy**, are below both earlier policies.
  The result is retained without tuning, replacement seeds or a reference swap.
- Verification: 48 exact transcript replays / 3,283 calls, 19 frozen sources,
  110 inputs, four predetermined complete policy repetitions, four guard
  checks and five additional reviewer reruns. Root reran the full verifier.
- Evidence: [supplement and commands](lightlag-runs/overnight-reference27-study/README.md),
  [verification](lightlag-runs/overnight-reference27-study/verification.json),
  [runner](../tools/lightlag_experiments/overnight_reference27.py).
  This is selected-policy evidence on inspected cells, not a new model test.
  No paid inference, Modal/Gemini use or final rules/prize decision.

### R08 — 14 November — Prospective accounting-aid comparison

- Codex fixed twelve fresh Claude Opus 5.5 / OpenCode 1.19.5 attempts, original
  prompt versus a generic energy/queue appendix, before outcomes. Claude
  performed the actual task; Codex designed and verified the experiment using
  Manh's decision auditor. No route or automatic safety filter was supplied.
- All twelve are complete: **five paired improvements, one tie**, mean reward
  **0.406571 control / 0.732265 aid**, mean paired gain **+0.325694**. Deaths
  **1/6 versus 0/6**, home finishes **4/6 versus 6/6**. The improvement threshold
  is met; the stricter gap-removal threshold fails on noisy 504. These selected
  diagnostic maps do not establish general reliability or energy-only causality.
- Codex built plan, cost, privacy and exact-replay checks. Review caught
  plan-truncation, duplicate-session and audit-path edge cases. An actual
  post-horizon no-op exposed cached grade-count semantics; the narrow export
  correction preserves every call and raw result. All 23 experiment tests
  pass; all twelve final audits reproduce exactly without infrastructure
  findings. No simulator or canonical-task behavior changed.
- Evidence: [protocol and full results](lightlag-overnight-evaluation.md),
  [twelve-row ledger](lightlag-runs/overnight-b-summary.json),
  [audits](lightlag-audits/overnight/block-b/README.md),
  [tool](../tools/lightlag_experiments/overnight_runs.py).
  Protocol `6e1cfe3` preceded outcomes; tool/first-pair increment `659dd2c`.
  Reported B usage **$5.4645252**, A+B **$9.4355068**; provider balance unverified.
  No retries, result replacement, prize entry or final project/rules decision.

### E08 — 14 November — Reproducible recorded evidence clip

- Codex prepared a 62-second silent first cut from the team's saved noisy-504
  evidence and delivered decision page. The clip labels the actual model run,
  checked post-hoc continuation and selected-case limits; all eight original
  model outcomes remain visible as context. No new model success is implied.
- Verification: independent full Chrome playback and eleven decoded frames,
  exact source/payload/video hashes, independent reconstruction of the branch,
  and root inspection of three key frames plus source/video hash checks. No network
  assets or JavaScript/media errors. The viewer and raw evidence are unchanged.
- Evidence: [clip, narration and reproduction](lightlag-demo-media/README.md),
  [verification](lightlag-demo-media/first-cut-v1/verification.json),
  [recording script](../tools/lightlag_experiments/overnight_demo_video.py).
  WebM/VP9, 1920×1080, 1.48 MB; Chrome verified, external-platform/MP4 playback
  untested. This is presentation work, with no inference cost or external upload.
  The team still chooses the final submission story; no prize entry was made.

### E09 — 14 November — Accurate public tool descriptions

- Codex found and corrected three shared MCP descriptions: dynamic maps can
  disclose targets later, visual odometry may be noisy, and credited science
  follows the episode's sampling rules. Kristján's tool/service implementation
  and Manh's dynamic rules remain unchanged. This is a contract-clarity fix,
  not an explanation assigned retrospectively to model failures.
- Prepared in isolation during paid evaluation, integrated only after all B
  attempts and exports finished. Independent review approved; 18 MCP and 11
  Harbor tests pass, generated copy matches, AST check limits changes to three
  descriptive constants. Historical tasks/manifests are preserved.
- Evidence: code `64fe6db`, [design and verification](superpowers/specs/2026-11-14-lightlag-interface-clarity.md).
  No inference cost, final profile choice or prize entry.

### E10 — 14 November — Correct the 3D reserve explanation

- Codex reviewed Kristján’s new 3D evidence demo and found that its HOME marker
  charged travel to the base centre although grading accepts a radius. The
  narrow correction removes a premature red warning and distinguishes finishing
  home/alive from arriving home, surviving elsewhere, or battery death. Earth’s
  marker is labelled as a delayed/noisy estimate; synthetic truth annotations
  stay outside that feed. Kristján’s visual and interaction work is preserved.
- Verification: actual Chrome counterexample fails before and passes after;
  all eight complete recorded runs are unchanged, 28 viewer tests pass, generated
  artifacts match, and independent Chrome/source review approves. No simulator,
  score, model run or selected mission changed.
- Evidence: [claim/design and verification](superpowers/specs/2026-11-14-mars-reserve-correction.md),
  [corrected demo](../viewer/mars-demo.html). Claim `57862d6` preceded edits.
  No inference cost or prize entry.

### R09 — 14 November — Prepare a fair reusable-policy transfer test

- Codex predeclared a single Claude-written policy across forty fresh map cells
  and built a public-only request, protected broker and constrained Docker
  worker. Eight historical KF trajectories reproduce exactly before any fresh
  map is inspected. One-shot synthesis is separated from online-agent results.
- Preparation and API phases passed independent review; root reran all 15
  preparation tests with real Docker and all 10 offline API tests. Review
  reproduced and fixed missing-terminal-event cost accounting, SDK environment
  header overrides and reservation overruns. No model inference occurred during
  these tests. Exact prompt/worker/source hashes and failures are retained.
- Evidence: [protocol](lightlag-synthesis-experiment.md),
  [published request and checkpoint](lightlag-runs/overnight-synthesis/README.md),
  [preparation manifest](lightlag-runs/overnight-synthesis/preparation-v1/preparation.json).
  Evaluation review is complete: all 42 checks pass, including interrupted
  attempt retention, null-score bounds and non-fabricated reproducibility.
- Actual provider outcome: the one Claude Opus 5.5 response used 5,989 input
  and 24,000 thinking tokens, hit its cap and produced no code. Calculated
  cost $0.503956; all 80 planned episodes remain unrun/null. No retry or repair.
  Independent artifact review confirmed exact request, usage, stream and
  hashes. This leaves transfer performance unknown; no model controller was
  delivered and no Harbor success is claimed. No prize entry.

### R10 — 14 November — Cross-check teammate Rocks evidence

- Codex independently checked Kristján’s three saved Rocks model runs and KF
  reference: exact protected rewards, model/session identity, task/source
  hashes, costs, 147 public calls and 83 model-visible responses. Manh’s auditor
  reconstructs all four full replays with no infrastructure findings.
- Model rewards 0.846154, 0.519231 and 0.692308 versus reference 0.769231;
  all four finish alive/home. Actual model execution belongs to Kristján’s
  OpenCode/Claude work; this review made no provider calls. His saved model
  usage totals $1.4873214, tracked separately from the overnight coordinator.
- Evidence: [reports and explicit limits](lightlag-audits/overnight/team-rocks/README.md).
  Initial installer failures and pre-outcome map selection remain teammate
  reports because the missing launch records cannot be reconstructed from
  these four trials. No prize entry or population-reliability claim.

### R11 — 14 November — Selective-information mechanism prototype

- Human direction: Sölvi chose learning before commitment, informed by actual
  Claude failures, and requested evaluation before expansion.
- Codex implemented an isolated delayed probe/route-choice environment and
  public-only Bayesian reference policies, including a matched control that
  ignores the acquired signal. Independent review checked information exposure,
  atomic commitments, timing, realized grading and probability weighting.
- Verification: 29 tests; 64 weighted outcome branches and 640 seeded episodes;
  root reconstructed all 704 saved replays and checked nine source hashes.
  Selective exact mean 0.5596875 versus never 0.53875 and always 0.51375.
- [Code](../lightlag_information/) and [results/limits](lightlag-information-choice.md).
  Four hand-designed development contexts; no Claude run, sponsor API use,
  continuous-rover improvement, final task choice or prize entry is claimed.

### R12 — 14 November — Protected Claude information-choice pilot

- Human direction: Sölvi requested actual model testing of the approved
  learning-before-commitment prototype before expanding it.
- Codex implemented the isolated MCP simulator and Harbor package, froze four
  context trials with seed commitments, ran controls and container isolation
  checks, and audited public decisions, exact replays, grades and source hashes.
- Claude contribution: four actual `anthropic/claude-opus-5-5` playthroughs using
  OpenCode 1.19.5 / Harbor 0.25. It chose when to probe, used the uncertain case's
  soft signal, and selected the optimal route and commitment timing in all four.
  Scores 0.325/0.9/0.4/0 equal the protected references. The zero is stochastic
  loss under the expected-reward objective, not a reasoning error.
- Verification: 40 package + 3 packaging tests; separate simulator/verifier;
  actual reference/no-op preflight; independent replay, task-hash, grade, usage
  and commitment audit. Four planned sessions completed, no retry/replacement or
  observed truncation. Total **reported API cost $0.2266114**, not a checked invoice.
- Evidence: [protocol/package commit `a7f72ef`](https://github.com/solvisantos22/junction-2026/commit/a7f72ef),
  [results and handoff](lightlag-information-pilot.md),
  [ledger and artifacts](lightlag-runs/information-claude-pilot-v1/summary.json).
- Limits: four hand-designed development cases, one session each; no model
  difficulty gap or population reliability established. Competing information
  sources are proposed next; no final task choice or prize submission made.

### R13 — 14 November — Allocating one inspection between two unknowns

- Human direction: Sölvi approved the next bounded experiment after the first
  information-choice pilot exposed no reasoning gap.
- Codex implemented the two-independent-route abstraction, one shared targeted
  probe, exact public-information reference, fair controls and protected Harbor
  package. Six mirrored cases and twelve model assignments were frozen before
  model outcomes. Matched controls separate choosing a target from buying an
  unnecessary inspection and from using its signal.
- Verification: 38 package + 3 packaging tests; all 864 weighted branches and
  1,080 seeded episodes retained, all 1,944 replays reconstructed. Independent
  enumeration of 2,016 strategy/state outcomes agrees. Selective exact mean
  0.6743 vs skipping 0.63, either fixed probe 0.63245, and matched entropy 0.6647667.
- [Design, protocol and results](lightlag-allocation-experiment.md). Structural
  results plus twelve actual Opus 5.5/OpenCode 1.19.5 sessions: all acquisition,
  route and timing decisions optimal; every score matches its reference (mean
  0.675). All 24 replay/grade/hash audits and 12 commitments pass; no retries,
  invalid calls or observed truncations. **Reported API cost $0.6699462.**
- Limits: 5/8 context/signal branches sampled; a current-leader target heuristic
  remains compatible with the cases. Optimal observed actions do not prove an
  internal reasoning algorithm or a difficult benchmark. No continuous rover
  changes, measured model gap, final rules choice or prize submission.

### R14 — 14 November — Compose scarce information with continuous rover control

- Human direction: Sölvi approved the challenger-information check and requested
  a substantially harder task using the same strong model. Final project/rules
  selection remains with the team.
- Codex closed the prior-leader coverage hole using two new explicit fixtures in
  the unchanged allocation simulator: 672 branches and 54 nearby parameter
  combinations pass. Exact reward .594375 for challenger inspection versus
  .492375 for leader inspection and .51 for skipping; no model calls.
- Codex implemented a separate continuous rover experiment: three shared regional
  qualities, two imperfect delayed inspections, eight targets, discoveries,
  deadlines and return-energy constraints. Physical samples also teach region
  quality; hidden/public-quality modes preserve paired physics and grading.
- Verification: 19 environment/generator tests including 100 map seeds, hidden
  state isolation, atomic queues, quality scoring and all-rich equivalence to
  the existing simulator; five independent challenger tests.
- [Design and developing evidence](lightlag-expedition-experiment.md),
  [package](../lightlag_expedition/). This first increment establishes mechanics,
  not a model gap. The next increment adds a public-only Bayesian KF/MPC
  reference and five controls, isolated MCP/Harbor packaging, full transcripts
  and reported-usage launch guards. All 57 package and 21 packaging/runner
  tests pass; independent review found and fixed nonfinite-input evidence loss.
  Free development comparisons retain all 1,536 episodes: weighted reference
  .453166 vs no inspection .412250, leader inspection .398719 and entropy .447593;
  every episode alive/home. The disclosed-quality heuristic scores .425028, so
  it is demonstrably not an upper bound. Actual isolated Harbor no-op and reference
  pass; an instruction-cache provenance caveat is retained in the design page.
  No canonical task or teammate physics changed.
- Actual strong-model pilot: three Opus 5.5/OpenCode 1.19.5 sessions score
  .55/.5575/.29 against .46/.46/.31 protected references. All alive/home, no
  invalid calls or observed truncation. The fourth planned assignment is unrun
  because **$1.5588192 reported usage** crossed the $1.50 new-launch guard.
  Seven protected replay/grade audits, four no-inspection controls and all four
  commitments verify. Initial live-spend monitoring limitation is retained.
- [Frozen protocol and results](lightlag-runs/expedition-claude-pilot-v1/summary.json),
  [interpretation and next decision](lightlag-expedition-handoff.md). The model
  beats both controls twice and trails by .02 once; this is not a convincing
  strong-model gap. Codex preserved the negative finding and proposes six regions
  with two inspections after repairing comparator limits. No further paid pilot
  or final project/rules selection is claimed.

### R15 — 14 November — Six regions with two inspections

- Human direction: Sölvi approved repairing the reference's inspection scheduling
  and expanding to six science regions, retaining the strong-model requirement.
- Codex implemented a separate fourteen-target survey generator and environment
  with six independent regional qualities and the same two-inspection budget.
  Physical sampling remains informative; existing rover physics and all frozen
  experiments are unchanged. A development/check protocol precedes policy outcomes.
- Verification: 22 environment/generator tests, including 100 geometry seeds,
  six-region hidden-state isolation, delayed learning, atomic reservations,
  constant-36 scoring and physical equivalence without inspections.
- [Contract and developing evidence](lightlag-survey-experiment.md),
  [predeclared gate](lightlag-survey-gate.md), [package](../lightlag_survey/).
  The separate scheduling reference and 16 focused tests now pass independent
  review; three repair-runner checks preserve errors and verify replay fidelity.
  Sample/pose forecasting approximations are explicit and shared across controls.
  The first 128 old-map repair episodes reconstruct exactly but expose a
  regression: adaptive mean raw7.68594→7.225, deaths1→2; no-probe improves.
  All negative evidence is retained while the comparator is diagnosed before
  the six-region matrix. No model gap, new Claude API call, task promotion or
  final project choice is claimed.
- Follow-up: Codex review identified underestimated sand-boundary costs,
  correlated-pose bounds and reuse of pending-drive reserves; the public-only
  correction passes 25 focused tests (38 including runners). [Code `6192e8e`](https://github.com/solvisantos22/junction-2026/commit/6192e8e).
  The complete 128-case rerun removes all new-reference deaths/failed returns,
  but its raw mean 7.17031 remains below the old 7.68594; its no-probe control is
  7.12344. Both versions, full transcripts and replays are retained. The sealed
  six-region runner has 10 tests and independent review; no paid model claim.
- Completed free study: 576 development episodes establish six competitive
  regions and select fixed r5+r6; source/selection seal pushed in
  [`6760d3c`](https://github.com/solvisantos22/junction-2026/commit/6760d3c)
  before the 128 held-out episodes. The check fails every aggregate acquisition
  margin: adaptive 9.96250 versus no-probe 9.79219, entropy 10.09687 and fixed 9.80156.
  All 704 survey episodes return alive/home and reconstruct; all negative outcomes
  retained. Human-approved harder-task direction remains provisional; Codex's
  evidence does not justify a paid call under this protocol. No new API spending.
  [Decision and handoff](lightlag-survey-handoff.md).

### R16 — 14 November — Research before the next mechanism

- Human direction: after the survey failed its information-value gate, Sölvi
  asked for online prior art and alternative directions before committing to a
  long campaign or repeated-mistake task.
- Codex contribution: primary-source searches across memory, continual learning,
  active experimentation, physical identification and workflow recovery; three
  parallel domain reviews and an independently checked synthesis. Current strong
  agent successes are retained alongside failures and scaffold limitations.
- Decision support: the report proposes a short changed-dynamics versus faulty-
  sensing diagnosis test, with unchanged controls, before expanding a campaign.
  This is a recommendation; Sölvi/the team have not selected or implemented it.
- Verification: source versions, model/harness distinctions, outcome denominators
  and local document links checked. No external benchmark reproduction, new
  environment implementation, API spending or prize submission.
- Evidence: [research and handoff](research/2026-11-14-next-mechanism-review.md).

### R17 — 14 November — Assess teammate prototypes before another build

- **Human direction:** Sölvi asked to assess the ground-change and sample-chain
  prototypes, then discuss the direction again before committing to more work.
- **Codex contribution:** two parallel implementation/evidence reviews;
  independent reproduction of all 72 retained sample-chain missions and 504
  policy records, all 400 published ground-controller episodes, and one fixed
  80-episode public-range diagnostic. Integrated the later teammate update:
  reproduced 800 four-rule-variant episodes and all six saved pilot transcripts,
  physical replays and grades. Retained the negative diagnostic and identified
  the ground filter's initial-range assumption, a short-horizon contract edge and
  the sample probe's Python runtime requirement.
- **Human decisions:** assessment was requested; no subsequent mechanism,
  environment expansion or paid model pilot has been selected by this work.
- **Verification:** 10 sample-chain and 18 current shift tests pass in the stated
  runtimes; saved plans, scores, search counts, source hashes and ground replay
  hashes reproduce. Local documentation links and Git whitespace checks pass.
  Original controller checks are scripted; the three newly landed Opus attempts
  are teammate-run exploratory evidence. Their outcomes reproduce, but explicitly
  stale task hashes and an incomplete source manifest prevent claiming complete
  frozen-task provenance. The later variant's safe prepared reference does not
  diagnose which rule changed.
- **Artifact:** [assessment and handoff](research/2026-11-14-prototype-assessment.md),
  [scripts and retained evidence](prototype-assessment/README.md). Current
  sample-chain version should be shelved; ground change remains an unproven
  hypothesis. No API spend, candidate source edit, project selection or prize
  submission. Teammate implementations and attribution are preserved.

### R18 — 14 November — Replay an existing Opus autopilot before another build

- **Human direction:** Sölvi approved testing the previously strongest saved
  Opus program against the four-rule mission, inspecting failures, and adapting
  it only if warranted before a separate fresh check.
- **Codex contribution:** predeclared policy selection and retirement criteria;
  a separate Docker broker with public-only access, full-horizon grading and
  explicit failure statuses; retained per-case evidence and an independent
  transcript/replay/metrics audit. Existing policy and teammate code unchanged.
- **Initial verification:** eight real-Docker integration checks pass, covering
  interface equivalence, isolation, paused simulation time, policy failures,
  invalid calls, limits and cleanup. The full free replay follows this verified
  runner increment; no new model result is claimed by preparation.
- **Artifacts:** [frozen protocol](rule-transfer.md),
  [results and handoff](rule-transfer-results/README.md),
  [isolated tools](../tools/rule_transfer/). No API spend or prize submission.
- **Verified free result:** 400 total episodes and 47,414 public calls
  independently reconstructed; 14 tests pass. Saved Opus beats Prepared on
  ground, link and relay changes, but has 23/40 deaths with turning costs. Its
  changed-case mean .628668 versus .644859 hides that failure. Three rejected
  relay calls are retained. No live-model failure is inferred; inspect before
  the authorized conditional adaptation. Existing model code was not changed.
- **Failure analysis:** all 23 lost rovers end inside base, 19 deplete on idle ticks; public battery discrepancies precede 22 deaths. Reconstructed from retained artifacts with no new cases. Published the bounded adaptation protocol, original-code/full-rules prompt and fresh-seed reservation before spending or opening check maps. Evaluator-only parking counterfactuals are labelled and excluded from model feedback.

- **Adaptation tooling verified before API:** 33 focused tests pass, including 12 fake-provider budget/failure tests and seven fresh-check integrity tests. A real NumPy-image replay matches the prior control exactly. Full prompt and fixed rules independently reviewed; no hidden fresh-instance input. No new spend during preparation.

- **Paid continuation and attribution:** Claude Opus 5.5 received the full original code, published rules and Codex's failure analysis, with adaptive thinking/medium effort and a 16,000-token response cap. The first free token-count request rejected an unsupported schema; Codex fixed and retained that preflight before the corrected launch. The one generated response spent all 16,000 output tokens on thinking and supplied no program. Reported usage: 17,914 input/16,000 output, **$0.391656**. No retry, practice episode or fresh case followed. This is a resource-censored experiment, not a model-capability failure. [Retained usage and verification](rule-transfer-results/adaptation-v2/), [decision/handoff](rule-transfer-results/README.md).
- **Final verification:** 34 focused tests; independent audit confirms all 70 current and declared-revision source pins, prompt/tool hashes, budget calculation, preserved initial preflight and absence of private thinking in public artifacts. Fresh seeds 52000–52039 remain unused. No task promotion, other-team credit attribution or prize submission. Codex's contribution includes identifying that its own generation cap prevented the planned repair evaluation; no improvement is claimed.

### R19 — 14 November — Small-model RL on the existing Traverse mission

- **Human direction:** Sölvi confirmed that the teammate had not started training, chose a small rover-control model and asked how it fits AfterQuery. Codex checked the saved brief: optional smaller-model training supports the submission; the frontier-agent comparison remains separate. Sölvi configured his Modal login.
- **Codex contribution:** a public-observation neural target selector over the unchanged navigator, paired-map policy-gradient training with the official terminal reward, a fixed before/after protocol with separate check maps, a bounded CPU Modal launcher, source/checkpoint provenance and independent audits. The trained model is a 256-parameter NumPy policy, not a language model.
- **Actual Modal use:** one four-core/8 GiB CPU job, [ap-e9VDJ99Y3AAjaY30NcNemX](https://modal.com/apps/solvisantos22/main/ap-e9VDJ99Y3AAjaY30NcNemX), using Sölvi's profile and the published resource/source freeze. Completed 512 missions and 16 updates in 466.74 trainer seconds (468.24 including wrapper); zero retries, no GPU or model API. Running CPU/memory estimate **$0.03285**, excluding build/startup/storage/egress; not a verified invoice. [Retained metadata](lightlag-rl-results/modal/pilot-01/modal-job.json).
- **Verification:** all 30 focused tests pass, including numerical gradient, checkpoint/source-drift and isolated cloud-launch tests. [Training audit](lightlag-rl-results/modal/pilot-01/training/audit.json) reconstructs 21,078 choices and all 16 optimizer updates against 34 source pins. [Fresh audit](lightlag-rl-results/check/audit.json) reconstructs 240 complete physics replays and 8,559 choices from retained features. Training physics and feature extraction were not independently replayed; limitations remain explicit.
- **Result:** initial mean .016744 → trained .024835; paired gain .008091, map-bootstrap 95% interval [.004038, .012592]. The declared screen **fails** the .03 gain and return-count thresholds (62/80 → 58/80); no deaths or invalid calls. Greedy scores .232840 but returns less often. Independent read-only review reproduces the comparison. [Saved-trace diagnosis](lightlag-rl-results/diagnosis.json) motivates testing persistent target choices; no follow-up training or environment edit was made. Check seeds 72000–72039 consumed.
- **Artifacts and scope:** [protocol](lightlag-rl.md), [final decision and reproducible handoff](lightlag-rl-results/README.md), [learning code](../lightlag_rl/), [Modal launcher](../tools/lightlag_rl/modal_job.py). Only target selection learns; navigation and safeguards stay fixed. One training seed, no frontier-gap claim, final task choice, canonical environment change or prize submission. Preparation used eight real smoke episodes and twelve smoke comparison episodes on already-used maps 1/2; those weights were retained only for verification.

### R20 — 14 November — Test persistent goals before more RL training

- **Human direction:** Sölvi approved testing goal persistence, suggested Rainbow as a possible learner and reported $300 total shared team Modal credit. This task used local compute only; that credit figure is user-reported, not a verified balance or allocation.
- **Codex contribution:** an isolated goal-commitment wrapper, fixed paired development protocol, comparison runner, independent replay/choice audit and saved-return diagnosis. Existing environment, navigator, weights and first training experiment remained unchanged. [Protocol](lightlag-rl-persistence.md), [wrapper](../lightlag_rl_persistence/chooser.py), [runner/auditor](../tools/rl_persistence/).
- **Measured result:** all 240 declared missions completed on 24 previously visited training maps. Initial-policy score 1.85% → 7.76%; paired gain .059166, map-bootstrap 95% interval [.048852, .069154], positive on all 24 maps. The **declared screen fails** its extra return condition (33/48 → 29/48). No deaths or invalid calls. Official score already halves credit when away, so the reward improvement includes that penalty. This is a fixed-rule intervention, not new learning or an unseen-map result.
- **Verification:** all 21 focused tests pass, including exact pass-through replay/RNG equivalence. [Twenty-case smoke audit](lightlag-rl-persistence-results/smoke/audit.json); [production audit](lightlag-rl-persistence-results/development/audit.json) reconstructs all physics/grades and 10,479 proposal/effective-choice records against 42 source pins. Independent review reproduces pairing, bootstrap, gates and artifact hashes. Candidate/feature extraction and choice-to-command linkage remain source-pinned, not independently regenerated.
- **Diagnosis and decision:** [reproduced saved-trace analysis](lightlag-rl-persistence-results/diagnosis.json) finds all 94 away cases end below 10 battery; initial persistent misses are a median 36.30 m from home. Recharge delay is a follow-up hypothesis, not established causation. Preserve the failed screen and test public charging-time feasibility separately before scaling training. [Final handoff](lightlag-rl-persistence-results/README.md).
- **Evidence and scope:** runnable source frozen at [e1661e7](https://github.com/solvisantos22/junction-2026/commit/e1661e7); audited production results published in [972bfd9](https://github.com/solvisantos22/junction-2026/commit/972bfd9). **Zero Modal/API spend in this task**, no new training, fresh check maps, Rainbow implementation, canonical change, final project choice or prize submission. A small capped multi-seed training comparison is only a recommendation for the next protocol.

## Keep recording with minimal overhead

At each meaningful delivered increment, its owner adds one entry or extends the matching entry. Bookkeeping-only edits need no new entry. Other tools/providers use the same structure; only describe use that actually happened.

```markdown
### E## — YYYY-MM-DD — short outcome
- Person and tool/provider/model (unknown if not recorded):
- Task / prompt summary (label exact excerpts separately):
- What the tool did; what the person/team decided or changed:
- Verification: command/test/run, observed result and limitations:
- Evidence: commit permalink, artifact/run ID, safe session capture or demo:
- Prize relevance and any remaining entry/form requirement:
```

For paid model/compute work, record the actual provider/model or instance, configuration, run ID, duration/usage/cost **if measured**, artifact location and meaningful contribution. Keep access tokens and redemption links private. For new research or experimental rules, label provisional findings and separate development from check data.

## Before final submission

- [ ] Reopen the current Codex and chosen sponsor briefs; verify required evidence, forms and whether the prize is selected in the platform.
- [ ] Pick two or three genuine examples above and preserve safe session captures/demonstrations. None are claimed captured by this log yet.
- [ ] Add a short, accurate Codex-use paragraph to the submission/development story with commit/artifact links and team attribution.
- [ ] Record real compute/model evidence only for sponsors actually used; keep unused candidates parked.
- [ ] Confirm the main challenge's Harbor run/score evidence using the [readiness checklist](afterquery-readiness.md).

No prize submission, sponsor post, redemption, account change or paid run was performed in creating this log.

### 14 November — Kristján / Claude Code: Lightlag Live, a control experiment for the gap, and the ghost demo

- **Human direction:** Kristján asked Claude Code to research, with the Claude API, a challenge the reference would win essentially every time, and a demo that shows every Claude attempt as a shadow beside the reference with the best one highlighted. He left the design open and asked it not to stop until the result was good. Claude Code told him it would keep paid use under about $10. Kristján had not yet reviewed the result when this was written.
- **Tool:** Claude Code; the session reports its model as Claude Fable 5.2. The models under test were Claude Opus 5.5, Sonnet 5.5 and Haiku 5.5, through the Messages API and through OpenCode 1.19.5 in Harbor 0.25.0.
- **Claude Code contribution:** the campaign service, MCP server, task generator and Harbor task (`lightlag_live/`, `harbor/lightlag-live/`); a sandbox that runs model-written programs in locked-down containers; the one-request generation script; the ghost demo and its three built pages (`viewer/ghosts/`); the fresh-map study; the write-up. It found, fixed and reported three faults in its own task: an unstated session limit (fixed in 0.1.1), a launch example that let OpenCode's shell tool kill the agent's program (0.1.2), and an instruction that did not say a program stops with the session (0.1.3).
- **What it found:** on the task the frozen `kf_mpc` scored 0.664 and all fourteen Claude runs scored less (best 0.610). On 200 fresh maps Opus's one-request autopilot is level with the reference (0.515 against 0.518), so the task's lead over Opus comes mostly from its mission rule; against Sonnet's and Haiku's one-request programs the lead is 0.10–0.31 a map. The same Claude-written autopilots score 0.75–0.92 on `rush` 501 with no rover lost, where Opus playing turn by turn lost the rover in four of six attempts. So this is mostly a negative result for the request, and a control experiment for the turn-based gap. [Results, limits and decisions](lightlag-live.md).
- **Verification:** 38 `lightlag_live` tests (3 need the `mcp` package) and 14 ghost-demo tests pass, and the task's copies are fresh (`python3 -m lightlag_live.make_task --check`). Through Harbor 0.25.0 on task 0.1.0: reference 0.664352, do-nothing 0.000000, stop-early 0.222917; on 0.1.3 the reference scored 0.664352 again and do-nothing 0.000000. Every agent run's saved scores agree with its `reward.txt` (tested). Agent programs replayed without their interruption reproduce the uninterrupted missions exactly. The three demo pages were opened in Chrome. Limits: one campaign per run; only Claude models; no strong model has played 0.1.2 or 0.1.3; one Haiku run lost a mission to a stall of the laptop.
- **Paid use, as reported, not checked against a balance:** about $9.15 on Kristján's key. Twelve one-request generations (Opus two, Sonnet three, Haiku seven, of which one reply was lost before its usage was saved), eight agent runs through Harbor (Opus three, Sonnet one, Haiku four) and one turn-based Opus run. Request ids, token counts and costs are in each run's `meta.json` or `result.json` under `docs/lightlag-runs/`.
- **Evidence:** [package](../lightlag_live/README.md), [task](../harbor/lightlag-live/), [runs](lightlag-runs/) (`live-*`, `turn-noise2-*`, `explore-standard-noise`), [fresh-map scores](lightlag-live-fresh-maps.json), and the pages [`ghosts-demo.html`](../viewer/ghosts-demo.html), [`ghosts-rush-501.html`](../viewer/ghosts-rush-501.html) and [`ghosts-rush-501-control.html`](../viewer/ghosts-rush-501-control.html).
- **Scope:** no change to the simulators, the controllers, the canonical Harbor task, the Mars demo or any teammate's file. No prize submission.

### 14 November — Kristján / Claude Code: Lightlag Traverse, a campaign of three sites, and what Claude did on them

- **Human direction:** Kristján asked for an environment closer to real Mars driving, harder for Claude, and a much stronger reference model; later he lifted the spend limit ("you can use more credits"), asked for the work to be committed so the team could pull it, and, after switching the session's model, asked Claude Code to continue. The design choices were Claude Code's and are proposals: keep the team's five tools and scoring; a 600 m by 400 m height map with slope-dependent slip, solar energy and deadlines; and, when one world proved too easy to get lucky on, a campaign of three worlds rather than a harsher day.
- **Tool:** Claude Code. The session reported its model as Claude Fable 5.2 until about 20:00 Helsinki and Claude Opus 5.5 after Kristján switched it. Models under test: Claude Opus 5.5, Sonnet 5.5 and Haiku 5.5, through OpenCode 1.19.5 in Harbor 0.25.0 and, for one-request programs, the Messages API.
- **Claude Code contribution:** `lightlag_traverse/` (ground model, world generator, environment, planner, reference pilot, MCP server, campaign, task generator, sandbox for model-written programs), the Harbor tasks `harbor/lightlag-traverse/` and `harbor/lightlag-traverse-campaign/`, the demo pages `viewer/traverse-demo.html` and `viewer/traverse-campaign.html`, 75 Traverse tests and 27 demo-builder tests, and the write-up. Kristján's other Claude Code session built the Modal farm that replayed the saved programs on fresh worlds and on the campaign's worlds; it has its own entry.
- **What it found:** on the campaign through Harbor the reference scored 0.476 (home at all three sites); seven Claude agent runs scored below it, the closest by 0.18: Sonnet 5.5 0.293 and 0.213, Opus 5.5 0.267, 0.247, 0.244 and 0.120, Haiku 5.5 0.000. Three of the six Opus and Sonnet runs ran a battery flat at one site or two; the other three came home with 28 to 53% fewer samples. On one site (2026) the reference scored 0.565 and seven Opus and Sonnet runs averaged 0.258, but the best two came within 0.04 and 0.05, and their programs replayed on 300 fresh worlds ran the battery flat on 91 and 157; that is why the campaign exists. A sunrise-to-sunset day was tried and dropped (reference 0.491, Opus 0.407 and 0.425, Sonnet 0.000). [Results and limits](lightlag-traverse-campaign.md).
- **Verification:** 75 Traverse tests and 70 viewer tests pass; both tasks' copies are fresh (`python3 -m lightlag_traverse.make_task --all --check`). Through Harbor: one site, reference 0.564655 (the same replay byte for byte on 0.1.0 and 0.1.1), do nothing 0, stop at tick 105 0.073; campaign, reference 0.476257, do nothing 0, stop after the first site 0.149. On Modal the pilot repeats the campaign's Harbor scores mission for mission. Opus agent 3's program, rebuilt from its trajectory, repeats its Harbor score exactly in the sandbox. Manh's `lightlag_traverse_max` tests (13) pass against this branch. Both demo pages were opened in Chrome with no console errors.
- **Paid use, as reported by Harbor and the one-request script, not checked against a balance:** $11.00 for Lightlag Traverse on Kristján's key: eight one-site agent runs $3.65, three one-request programs $1.30, three harsher-day agent runs $1.90, seven campaign agent runs $4.15. Trials that failed in setup on the venue network made no model call. Request ids, token counts and costs are in each run's `result.json` under `docs/lightlag-runs/`.
- **Evidence:** [write-up](lightlag-traverse.md), [package](../lightlag_traverse/README.md), [campaign task](../harbor/lightlag-traverse-campaign/), [one-site task](../harbor/lightlag-traverse/), [runs](lightlag-runs/) (`campaign-*`, `traverse-*`, `dawn-agent-*`), [campaign demo](../viewer/traverse-campaign.html), [one-site demo](../viewer/traverse-demo.html).
- **Scope:** new files and folders only, plus my own `TEAM_STATUS.md` row; no change to `lightlag/`, `lightlag_dynamic/`, `lightlag_mcp/`, `harbor/lightlag`, the Mars demo or any teammate's file. Defaults of `lightlag_traverse` were kept while teammates' studies read it. No prize submission.

### 14 November — Kristján / Claude Code: the two-minute demo video, narrated

- **Human direction:** Kristján asked for "a very good demo video with voice over" showing what the team did, why Claude struggles, what the reference is, and the Modal work; said not to upload it; and after watching the first cut asked for three things: less "bullet pointy", an explanation of the ground (slip, terrain, pitfalls), and an honest treatment of the worlds Claude's programs won ("battery luck?"). Sölvi's correction to the learning line (a development result, not held out) came through the farm session and was applied. The order of the script, the pictures and the voice are Claude Code's choices and are a proposal.
- **Tool:** Claude Code; the session reported its model as Claude Fable 5.2. The voice is Kokoro-82M, an open-weights text-to-speech model, run locally in Docker with no network; the check uses Whisper `base.en` through faster-whisper, also offline. No model API was called and nothing was paid for.
- **Claude Code contribution:** `tools/demo_video/`, a pipeline that speaks the script, records the real Traverse demo page and six drawn slides frame by frame on a clock it steps itself, places every picture by the time the voice says each word, mixes the sound and writes the subtitles; the page's controls exposed for it at the end of `viewer/traverse/app.js`; and `docs/demo-video/` with the video, subtitles, a poster and a README (the script, the source of every number, what was checked).
- **What the second cut changed:** the rules are no longer listed; the middle of the video is three incidents from the judged campaign runs at site 3 (Opus agent 2 samples 2.53 m from a target that wants 2.5 m; Sonnet agent 1 is stopped on the lip of the scarp, one of its 30 safety stops there; Opus agent 4 runs flat four ticks after the reference stopped to wait for the sun). The 300-world line no longer says "at least 288": it gives the pooled count from the same rows, 1,780 of 1,800 match-ups to the reference, and says who won the rest (15 wins, none by more than 0.041, 13 of them by the two programs that ran flat on 91 and 157 of 300 worlds; 5 ties). The farm session then recorded those 15 missions again: in 5 the rover had dipped below 5% battery, in 10 it never went below 8%, so the video does not call the wins luck.
- **Verification:** 117.5 s against the guide's two minutes. An offline speech recogniser that had not seen the script heard 305 of its 316 words as written; the rest are spellings and near-homophones. −16 LUFS, true peak −1.5 dBFS. Frames from every shot and every cut were looked at. 152 viewer and Traverse tests pass with the page's addition. **Not verified:** how it sounds to a person; Kristján watched the first cut, nobody has yet watched the second from start to finish.
- **Evidence:** [video](demo-video/lightlag-traverse-demo.mp4), [README](demo-video/README.md), [pipeline](../tools/demo_video/).
- **Scope:** new files, one addition at the end of `viewer/traverse/app.js` with its two generated pages rebuilt, and my own `TEAM_STATUS.md` row. Nothing uploaded or submitted.

### 14 November — Kristján / Codex: make the 3D mission demo easier to present

- **Human direction:** Kristján asked Codex to inspect the demo and improve its looks, controls and mission presentation. Claude Code authored the existing 3D scene; this increment builds on it.
- **Codex contribution:** a persistent mission briefing, larger Mars view, explicit playback/step/restart/event controls, camera and panel focus controls, a keyboard-accessible mission menu and guide, and phone layouts with view tabs. Browser testing caught and fixed a slider/step synchronization race. Recorded mission outcomes and simulator/controller behavior are preserved.
- **Verification:** 28 Python viewer tests; 33 Chrome interaction/outcome checks covering two missions, eight runs, 1440/768/390-pixel layouts, keyboard input and all saved end scores; no runtime errors. Local screenshots inspected. [Behavior and verification](../viewer/USABILITY.md), [source](../viewer/mars/app.js), [standalone artifact](../viewer/mars-demo.html).
- **Integrated follow-up:** [UI commit `8c5299c`](https://github.com/solvisantos22/junction-2026/commit/8c5299c). After the reserve correction and Claude Code’s Rocks mission landed, all 29 viewer tests and 38 browser checks passed across three missions and twelve saved outcomes. The standalone file was opened with networking disabled, with no HTTP requests or runtime errors.
- **Scope:** presentation and interaction work only. No model/API spend, new experiment, inferred performance gain or new prize submission.
- **Outcome:** superseded the same day. Kristján found the result too squashed and asked Claude Code to return to the four full-screen views; the briefing strip, transport strip, panel buttons, menu, guide and phone layouts were removed. Event jumping and single-screen zoom were kept as keyboard shortcuts.

### 14 November — Manh / Claude Code: selectable Mars biomes, an early controller test and a biome edition of the 3D demo

- **Human direction:** Manh asked Claude Code to turn the terrain-unit brainstorm into biomes one can choose, to keep today's environment as "Main Mars", to say which controller did best overall, and to add the choice to the 3D demo. Mid-task Manh asked that nothing be pushed before they had reviewed it, so that Kristján's demo would not be disturbed; the work therefore stayed on a local branch until Manh gave the go-ahead to push.
- **Claude Code contribution:** `lightlag_dynamic/biomes/` (catalog, environment, JSON-lines runner, MCP entry, trial runner): Main Mars unchanged plus six published biomes, two of them new mechanics (Troy Crust, Bagnold Dunes); the calibration sweep and its keep rule; the early test and its write-up; `viewer/build_biomes.py` and `viewer/biomes/addon.js`, which add a biome row and biome drawing to the 3D demo without editing any of its files. Claude Code proposed building the demo part as a separate page and add-on after Manh's request not to disturb the main demo.
- **What the early test found:** on 40 unused seeds controller 33 had the best mean share of controllers 1–34. After controllers 35 and 36 were registered the same afternoon they were played on the same seeds (55,440 scripted episodes in all): controller 36 is best overall, 75.2% against 73.0% for the frozen reference (+2.2 points, 95% interval +1.4 to +3.2) and 74.9% for 33 (+0.4, +0.1 to +0.7). [Results, settings and limits](lightlag-biomes.md).
- **Human judgment that changed the write-up:** Manh read the results and said the biomes looked too easy. Claude Code checked: the default settings were kept only where controllers that ignore the biome still score 85% of their Main Mars score, so they cost such a player 2–7 points. A probe on unused seeds 2100–2139 found one hard setting that is fair today (Hidden Valley on `noisy` at slip limit 0.30: the rule-aware controller keeps 79%, `kf_mpc` falls to 33%). The write-up now says so; no setting was changed.
- **Verification:** 24 biome tests (one through a real MCP client) and 11 demo tests; all 95 `lightlag_dynamic` tests and 40 viewer tests pass. Main Mars is identical to `DynamicEnvironment` (rules, map, telemetry, replay). A build of the biome page leaves the main demo's five files byte-identical (hash test). The page was walked through in headless Firefox: title screen, a Main Mars mission, every biome, the compare view and playback, with no script errors. Not checked in Chrome.
- **Evidence:** [package](../lightlag_dynamic/biomes/), [biome tests](../tests/lightlag_dynamic/test_biomes.py), [trial report](lightlag-biomes/trial-report.md), [demo builder](../viewer/build_biomes.py), [add-on](../viewer/biomes/addon.js), [demo page](../viewer/biomes-demo.html).
- **Manh's idea, prototyped:** Manh suggested hiding the rover's pose so that sensors have to be fused, and that a particle filter would suit many sensors. Claude Code first checked the idea with the existing dials (removing the fix alone does not force fusion; a wider heading bias does), then built a no-GPS option (beacon range and sun compass instead of the position fix) and a particle-filter reference on the Manh controllers' filter. On unused seeds 2200–2239 the reference scores 56% and 76% and always gets home; the best player without a filter 37% and 47%. Ten tests. Limits are in the write-up: no model has played it, and the compass does most of the work. Manh then said a GPS could stay if it were very noisy next to the other sensors; Claude Code added that as a setting (2 m fix, 12° compass), chosen on a development grid and confirmed on unused seeds 2300–2339: the fix and the compass are each worth 5–7 points to the reference, and the frozen reference, which leans on the fix alone, is 11–15 below it.
- **Prepared for a model run, not run:** Manh approved preparing the weak-GPS option for a model run. Claude Code made the biome MCP entry serve tool texts that match the episode's sensors without editing `lightlag_mcp`, wrote a task generator after Sölvi's, and dry-ran the generated task without Docker: the simulator's own command, the oracle solution, the collect hook and the verifier give the direct-run reward, and the fusing reference scores the same through the HTTP server as directly. With today's fix the generated instruction is byte for byte the dynamic experiment's. Seeds 2400–2403 were fixed for the pilot before any episode was played on them. Eleven generator tests and five tool-text tests. Not built or run in Docker; no model run and no API spend, which remains a team decision. [Tool texts](../lightlag_dynamic/biomes/wording.py), [generator](../tools/biome_experiments/prepare.py), [dry-run tests](../tests/biome_experiments/test_prepare.py).
- **Manh's next ideas, built and measured:** Manh pasted a list of robot sensors, asked which ones would add to the fusion, and said the rover should be able to overshoot its mark. Claude Code proposed three sensors and two ways to overshoot, each with a one-line reason; Manh chose the gyroscope and a hidden wheel-size error, then asked for the second beacon to be explained and turned it into any number of beacons. Claude Code built all three as settings that are off by default (pushed settings are fingerprint-tested unchanged), extended the particle-filter reference, chose one setting on development seeds and confirmed it once on unused seeds 2500–2539. What it found, reported as measured: the wheel-size error is the largest single effect on today's environment (controller 36 and the frozen reference lose about 20 points), several beacons count (5–9 points), and the gyroscope Manh chose adds nothing measurable to the reference. Manh's question whether beacons need a bigger map was answered from the map itself (40 × 40 m, work within 9 m of the base): no. [Write-up](lightlag-biomes.md), [settings](../lightlag_dynamic/biomes/nogps.py), [players](../lightlag_dynamic/biomes/nogps_players.py).
- **The wheel scale prepared as a model-run task, not run:** Manh approved preparing the wheel-size error on today's environment for a model run. Claude Code made it an option of its own that changes nothing else in today's telemetry, gave it truthful tool texts and a generator switch, dry-ran the generated task without Docker, and fixed six seeds with their scripted scores. While doing so it re-checked one row it had pushed an hour earlier (a filter that had also read a beacon and a compass), found it the same within a point on today's telemetry alone, and corrected the row and its note. No model run and no API spend. [Rule](../lightlag_dynamic/biomes/wheels.py), [tests](../tests/lightlag_dynamic/test_wheels.py).
- **Follow-up the same afternoon:** Manh asked for a slightly different colour palette per biome, so that the screen shows which biome is playing while still looking like Mars. Claude Code added it to the add-on only (ground, sand, rocks, light, haze and sun shifted a little per biome; Main Mars unchanged), with a test that keeps every shift small. Manh looked at a comparison sheet before it was pushed.
- **The max env and a controller for it (Saturday evening):** Manh asked what the environment holds in total, approved letting lost packets and wild fixes work inside the biomes, then asked for the fusing particle filter to be combined with controller 37's tuned layers so that one controller handles every mechanic, and to push once it reached a decent level. Claude Code let the lab's two link faults pass the Mars layer (one line, tested identical to the lab's faults in Main Mars), wrote the max-env preset and built `max_navigator`. It has the particle filter with lost-packet bridging, a robust fix likelihood, crust-aware terrain matching and the wheel scale read off the battery, under 37's planning layers. Five changes came from tracing failed missions on development seeds 0–59 and 1100–1299: dune sand counted as a trap, trip chances from the true slip, no waiting to confirm a landing, an energy reserve of 5 after rovers died at base, and longer back-out drives. Ideas that lost on the same seeds are reported too: routing around crust, marking soft cells, chaining legs across relay passes. **Fresh check on unused seeds 2600–2639, keep rule declared beforehand:** 29.0% of the available value against 11.2% for the fusing reference (+17.8 points, 95% +11.8 to +23.7), 8.5% for controller 37 and 6.4% for `kf_mpc`; one rover in 40 died. Twelve tests; `fused` is fingerprint-identical after the filter hook. No model run, no API spend. [Write-up](lightlag-biomes.md#the-max-env-everything-on-at-once-and-a-controller-for-it), [controller](../lightlag_dynamic/biomes/max_players.py), [preset](../lightlag_dynamic/biomes/maxenv.py), [tests](../tests/lightlag_dynamic/test_max_env.py).
- **Scope and limits:** a sandbox option, not a rules decision. Scripted controllers only; no model has played a biome; no API spend, Harbor change or new prize submission. Only the max-env controller reads any of the new published areas (crust regions and dune faces), and the default settings are mild by the keep rule.
- **A MAX map option for Kristján's Lightlag Traverse (Saturday evening):** Manh asked Claude Code to pull Kristján's new Traverse, add the max env to it as a choice between the normal map and a MAX map, measure four players on both (his best controller, the frozen reference, the greedy controller and the straight-line driver), and push. Claude Code wrote `lightlag_traverse_max/` in new files only. The MAX map is a subclass of Kristján's environment: the same world for a seed, every rule published, and a test that it equals his environment with every setting off. `manh_max` is Kristján's pilot with the max-env controller's layers carried over, plus fixes found by tracing failed missions on development worlds 1–24: stale commands across relay passes, a wider trip check, edges judged by their steepest slope, rules for getting unstuck and earlier homecoming. A runner compares players on both maps. Claude Code checked that `kf_mpc` cannot drive the Traverse and said so rather than substituting it silently, and described the straight-line driver as deterministic, not random. Kristján pushed a beam search for his pilot during the work; Claude Code rebased onto it and re-ran rather than report the older numbers. It also moved the final check off worlds 101–124 after finding them inside the farm's search range. **Fresh worlds 500–523:** on the MAX map `manh_max` scores 0.313 against 0.072 for the reference pilot (+0.241, 95% +0.197 to +0.285, higher on 23 of 24). On the normal map both score 0.498 (the same commands). Weak spot reported: 7 of 24 MAX missions ended away from the lander. 13 new tests and Kristján's 59 pass. No model run, no API spend. [Write-up](lightlag-traverse-max.md), [code](../lightlag_traverse_max/), [tests](../tests/lightlag_traverse_max/test_max_map.py). Manh then asked for a way to watch them. Claude Code wrote [`viewer/build_traverse_max.py`](../viewer/build_traverse_max.py), which feeds Kristján's unchanged Traverse page with the four players, one page per map. It did not run his build script, which would have overwritten his data file and refuses MAX runs (lost packets leave gaps in their telemetry). Both pages were checked in headless Firefox; three tests. Manh then asked for the MAX map's hardest worlds as a frozen baseline for Opus, Sonnet and Haiku, offering his own API key. Claude Code ranked the worlds of 500–523 by `manh_max`'s MAX score and re-scored the candidates after Kristján's pilot changed; Manh picked three superhard worlds (505, 509, 515) and three fair ones near 0.5 (500, 510, 520). Claude Code froze the request, worlds and protocol before any paid call: Kristján's one-request text with the MAX rules, 3 replies per model. Docker was missing, so it ran the programs under bubblewrap instead and checked that this replays Kristján's Docker run byte for byte. A re-freeze is allowed only before any request is sent, and the first freeze is kept in the record. A free dry run played his three saved normal-map programs (superhard / fair: Opus 0.038 / 0.049, Sonnet 0.029 / 0.020, Haiku 0.014 / 0.003, against 0.157 / 0.488 for `manh_max`). 15 more tests. The paid step ($10 cap) waits for Manh's key. [Baseline](lightlag-runs/max-baseline/README.md). Manh then asked that teammates always evaluate on these worlds and that the page they open use them. Claude Code put the list in one module with a check that refuses training on any reserved world (500–523 on both maps, because a seed is the same ground on both, plus Kristján's 2026–2029 and 99991), added the rule to `AGENTS.md`, and built a six-world page on Kristján's unchanged Traverse app (`viewer/traverse-evaluation-max.html`, checked in headless Firefox). It left Kristján's normal-map demo and campaign pages as the submission demo instead of switching them to MAX worlds, and said so. 5 more tests. With Kristján's approval, relayed by Manh, Claude Code then wrote Harbor tasks for the MAX map: two three-mission campaigns on the fair and superhard worlds, generated by importing Kristján's task generator unchanged and putting the MAX map behind his server and campaign. Docker is missing here, so it tested the task by serving its own simulator folder over HTTP and reaching it with the agent's own client, then finishing and grading it; it states that the images were not built. Reference pilot campaign scores: 0.103 fair, 0.036 superhard. 6 more tests. Late on Saturday Manh asked Claude Code to check Kristján's results on his seeded worlds, how `manh_max` does there, whether judges can reproduce the scores, and whether an agent will beat the designated controllers. Manh installed Docker; Claude Code cloned `main` fresh and ran the reference and do-nothing agents through Harbor on four tasks. The campaign reference gave 0.476257 and the one-site reference 0.564655, with every replay file identical to Kristján's committed ones; the first run had failed without a score on a DNS timeout, which Claude Code reported instead of hiding. It wrote a replay check that plays every saved run again from its command log (24 of 24 reproduce, on Python 3.12 and 3.14) and measured, from the farm's saved rows, how often a saved program beats a designated controller per world and per simulated three-world campaign. It found that `manh_max` equals the reference on the normal map except for Kristján's newer way-home rule, that the reference with its reserves off scores higher on the campaign's worlds (0.487 against 0.476), and that Opus's one-request programs are level with `manh_max` on the MAX map, so the MAX tasks' reference solution is too weak for a gap task. It also found that Kristján's farm session had sent the frozen MAX request with his own key; it kept Manh's six replies as a second, labelled set and stopped spending. Manh then asked why Claude comes closer to his controller on the MAX map than to the reference on the normal map. Instead of guessing, Claude Code played the four MAX-request Opus programs on the normal map too (150 sandbox missions on 30 fresh worlds, 40 more on Kristján's worlds). It found that the two comparisons had used different programs: the four newer ones score 0.342 to 0.453 on the normal map against the reference's 0.500 and the older program's 0.326, so with the same programs Claude gets 81% of the reference on the normal map and 88% of `manh_max` on the MAX map. It reported, unasked, the result that cuts against the team's own claim: one of those programs scores 0.474 on the campaign's worlds against the reference's 0.476, checked by two more runs and by replaying its command logs. 3 more tests. Manh then asked for Kristján's way-home rule in his MAX controller. Claude Code added it as a separate player, `manh_max_home`, so that `manh_max`'s published scores and the farm's rows stayed valid, and checked that `manh_max` still sent the same commands. It tested the step directly against the pilot at 58 battery levels, then on 24 development worlds on each map before touching fresh or held-out worlds, which it played once. The result did not support its own suggestion: the rule makes the controller the pilot's equal on the normal map (24 of 24 worlds) but changes 2 of 100 fresh MAX worlds, one for the better and one for the worse. Claude Code reported that, traced the worse world to an end-game slip and the other away endings to time and stop loops, not the battery, and did not present the new player as a stronger reference. 1 more test. [Write-up](second-machine-check.md), [tools](../tools/second_machine_check/).


### 14 November — Kristján / Codex: certified challenge research

- **Human direction:** Kristján asked for recent research and a cooler challenge where agents struggle while a reference reliably succeeds, including whether to change or enlarge the environment.
- **Codex contribution:** audited the latest live/autopilot, information-choice and survey results; read recent primary research on space planning, production scheduling, generalized planning and optimization agents; proposed a complete sample-to-downlink mission with a publicly specified exact reference. Explicitly retained counterevidence, older-model limits and task-specification confounds.
- **Artifacts and finding:** [research and decision](research/2026-11-14-certified-challenges.md), [isolated exact-solver probe](../tools/certified_challenge_probe/README.md), [fresh results](../tools/certified_challenge_probe/results/check.json). Reference proves the optimum on all 48 fresh missions, but generic beam search reaches 99.35% / 97.29% at eight/twelve jobs. Both fail the declared difficulty gate; the simple scheduling candidate is rejected for promotion. This is useful negative evidence, not an LLM failure. Compatible-observation products remain a research hypothesis; no environment is selected for the team.
- **Verification and scope:** ten focused tests, independent tiny brute-force comparisons, and a post-write audit of all source hashes, 72 generated missions, 504 policy records and summaries pass. Protocol and source were published before the check in [465d91e](https://github.com/solvisantos22/junction-2026/commit/465d91e). Paper claims checked against primary abstracts/tables and evaluation conditions. No API/model spend, simulator changes, demo changes or prize submission.


### 14 November — Kristján / Codex: stereo-survey experiment

- **Human direction:** Kristján approved testing the stereo-survey mission proposed in the certified-challenge research.
- **Codex contribution:** a separate public-geometry mission, chronological replay, bounded exact reference, pair-aware greedy and beam controls, and a matched monocular comparison. The objective counts useful stereo coverage rather than photographs taken.
- **Initial verification:** 12 focused tests, including known-angle geometry and all-subset comparisons on six tiny missions under both objectives. The [development study](stereo-survey-results/development.json) retains 24 missions: beam matches all 23 proved stereo optima, with one reference capped at two million joint plans; all 24 monocular references prove optimal. No LLM failure is inferred from weak coverage-only controls.
- **Final result:** [fixed fresh check](stereo-survey-results/check.json), with protocol published first in [845cac7](https://github.com/solvisantos22/junction-2026/commit/845cac7). All 48 stereo and 48 matched monocular reference optima proved and replayed. On stereo, coverage-only greedy reaches 28.05% / 18.63%, greedy portfolio 92.10% / 93.67%, and the predeclared beam portfolio 100% / 100% (compact / expanded). Both difficulty gates fail, so this configuration is rejected for promotion or a paid pilot. No LLM failure is claimed.
- **Final verification:** source-hash, regeneration, replay, product and summary audit covers 72 unique missions and 1,168 saved policy records, including derived portfolio copies and one repeated development case. The original capped proof remains intact; the unchanged algorithm later completes that development case after 2,348,648 joint evaluations. CLI generate/solve/verify round trip passes. A CLI-only pre-change source is archived by hash.
- **Artifacts and scope:** [design, results and handoff](stereo-survey.md), [package](../stereo_survey/README.md). Scope complete. Existing rover, shift experiment, demo and canonical task untouched; no model/API spend or prize submission.

### 14 November — Kristján / Codex: stereo program-synthesis follow-up

- **Human direction:** Kristján asked to continue the stereo investigation and assess whether it remains a good lead. Codex distinguished the existing negative search-difficulty result from the unmeasured question of whether an agent can formulate and implement the solver.
- **Delivered preparation:** [frozen protocol and interpretation](stereo-survey-followup.md), two public-rules prompts, a protected Docker evaluator, source/program hashes, fixed fresh seeds, strict failure retention and a bounded three-request launcher. The paper's observation-construction setting and older-model/feedback limitations are stated explicitly; no difficulty is inferred from a toy baseline or a one-shot failure.
- **Verification:** six boundary tests and all 12 existing stereo tests pass. Six free container preflight cases accept empty plans, reject invalid plans and reproduce reference optima 44/57 on two used development missions. Timeout, output flooding, private imports and attempted public-file mutation are checked. No generated program executes on the host.
- **Authorization and protocol update:** Kristján subsequently authorized Anthropic API use and asked for committed/pushed Markdown findings. Before any stereo request or fresh evaluation, [v2](stereo-survey-followup-results/pilot-02/protocol.json) raises the output allowance to 64,000 tokens and sets a $5 batch ceiling after a separate task exhausted 16,000 thinking tokens without code. Same prompts, three attempts and 48 fixed fresh missions; old unused preparation retained. Four protocol/extraction checks and all six free Docker preflight cases pass for v2. No paid call or new model result at this checkpoint; environment and demo unchanged.

- **Final paid result:** user-authorized three Opus 5.5 generations cost $1.023160 in total; every response ended normally and all programs were frozen/pushed before fresh evaluation ([269217a](https://github.com/solvisantos22/junction-2026/commit/269217a)). Both plain programs and the hinted control reach **48/48 proved optima each**, with all 144 model-case records valid and no timeout, runtime error, retry or manual repair. [Audit](stereo-survey-followup-results/pilot-02/audit.json) reproduces hashes, missions, reference/submission replays, summaries and reported usage. The bounded version is retired as a difficulty candidate; [final Markdown findings](stereo-survey-followup.md) identify reusable objectives, exact targets and evaluation tools without claiming an untested transfer. Scope released; no canonical task, rover controller or demo change.


### 14 November — Kristján / Codex: five-minute local main-push watcher

- **Human direction:** Kristján requested an agent every five minutes to check this computer for committed work missing from main and push it.
- **Codex contribution:** configured a dedicated Codex task and macOS LaunchAgent using an unchanged copy of the existing Junction Watch adapter; wrote instructions for local-branch/worktree inspection, isolated verification and integration, normal pushes, remote confirmation and blocker reporting. The adapter itself is prior team work, not newly authored here.
- **Human decisions and limits:** five-minute cadence and publishing committed work are Kristján's request. No automatic end date was requested. Uncommitted work, active Git operations, unfinished checkpoints and uncertain conflicts are preserved; no project/rules decision or paid experiment is authorized by the watcher.
- **Verification:** all 26 existing adapter tests pass; installed adapter bytes match the repository version; private file modes, plist validation and matching 300-second config/loaded timer are checked. A real launchd dispatch resumed the dedicated task, which found all seven local branch tips and seven worktree HEADs already on `origin/main` at `269217a`. The agent atomically acknowledged completion and delivered its setup report. No candidate needed publishing, so no automatic project-code push is claimed.
- **Artifact:** [operation, limitations and pause/stop commands](main-push-watch.md). Runtime configuration, task identifiers and logs remain private on Kristján's Mac.
- **Alert timing follow-up:** two real verified integrations exceeded the five-minute dispatch interval and raised premature health alerts. Codex separated the installed private adapter's alert threshold (900 seconds) from dispatch (300 seconds), preserving pending reservations and existing acknowledgements. All 26 inherited tests plus five focused timing/validation tests pass. Live status confirms enabled scheduling and the second integration's completed acknowledgement; shared event-watch source/runtime unchanged.
- **Archived-source check follow-up:** the watcher correctly preserved but deferred farm commits because three saved Sonnet source lines have trailing spaces. Parent Codex verified each exact line in the original trajectory, confirmed both complete archive files still matched the inspected bytes, parsed them without execution, and found no whitespace issue in the other candidate files. The watcher now records a narrow archival-format exception and continues focused tests, preserving original model evidence rather than formatting it. No authorship of the farm code or model programs is claimed.
- **Immediate push check, campaign records:** at Kristján's request to check and push again, Codex separated the completed baseline records from a campaign implementation that still failed retained-source compatibility. All 53 files from Claude Code's `b5b7ee7` are exact original blobs. Nine missions, 39 JSON files and 3,221 transcript rows pass saved-artifact consistency checks; original scores and authorship remain attributed to their source. [Scope, results and verification](campaign-baselines.md). No new physics replay, model call or cloud job, and no claim that the blocked runtime was promoted.
- **Retained harsher-day agent evidence:** the watcher independently published the 45 exact saved-run files from Claude Code's `b846b63`: two Opus 5.5 runs scored 0.407328 and 0.424569, and one Sonnet 5.5 run scored 0, on the sunrise-to-sunset day that the Traverse owner tried and did not adopt. Codex used the existing reference-review auditor to reproduce all three physics replays and grades from accepted commands, parsed 27 JSON files and 3,605 transcript rows, and passed 22 existing viewer tests. All three nonzero agent-exit exceptions remain in the records. [Source hashes, verification and limits](dawn-runs-verification.json). Original experiments belong to their source authors; no new model call, cloud job, archived-program execution or rules change was made.
- **Explicit full-branch integration:** Kristján then specifically requested `git merge worktree-claude-gap-research` on `main`. Codex coordinated a watcher handoff, merged current remote work and the full branch in [`0130fa6`](https://github.com/solvisantos22/junction-2026/commit/0130fa6), and updated the earlier pending-publication notes. All 75 Traverse and 28 viewer tests pass; farm runs 38 tests with one optional skip; all seven feasibility tests pass. Historical RL checks retain one source-pin failure (30 tests) and one persistence class-setup error (12 tests run): the pilot, task generator and server differ from both original 34-file source manifests. Frozen hashes/results remain unchanged; this integration does not claim those compatibility checks pass. Traverse code and saved experiments retain their original authorship. No new training, model call or cloud job.
- **Contextual results publication:** Codex integrated the completed research evidence from [`5557935`](https://github.com/solvisantos22/junction-2026/commit/55579352b027fc5e0c1ad1bf4f132dcc4fa5375b), preserving the source author and the separate paused-training claim. Six existing contextual tests pass; 405 source files remain byte-identical, all 724 saved physical trajectories and grades replay, the paired-map summary/bootstrap reproduce, and all 120 feasibility score decompositions match 240 hashed source cases. All 56 historical source pins match the original `55654bb` study version; the explicitly merged main has the already documented three changed Traverse files plus the campaign module. [Verification and reproduction limits](lightlag-rl-feasible-results/publication-verification.json). Frozen evidence is unchanged. This check does not claim to repeat optimizer reconstruction or teacher/controller audits; no new training, model call or cloud job was run.


- **Point-of-no-return evidence publication:** under Kristján's standing watcher request, Codex verified Claude Code's [saved analysis and demo-script increment](https://github.com/solvisantos22/junction-2026/commit/7f804632e551025a1c666685950209138074221c). All 2,100 rows cover seven players on worlds 600–899 exactly once; the analysis summaries, evaluation tables and paired bootstrap comparisons reproduce exactly, including all 526 recorded program errors. The 1,500 deterministic comparison rows match the earlier comparison, and the saved source fingerprint matches its original code version. Three existing analysis tests and unrestricted whitespace checks pass. The source authors retain credit for the experiments and script; Codex checked the saved evidence without rerunning archived programs or cloud jobs. The demo's campaign figures remain explicitly provisional pending the owner's final table; no rules decision or independent replay of every home analysis is claimed.

- **Final campaign evidence publication:** under the same standing watcher request, Codex integrated Claude Code's [seven campaign runs and completed report](https://github.com/solvisantos22/junction-2026/commit/62e4afb71435ab8f6d6d7ee97a3f895a67c7259c) with the [final demo script and farm usage correction](https://github.com/solvisantos22/junction-2026/commit/0b04a44a7b24c80b52c3482e47f90fc7fb1f4cc3). All 140 archived files remain byte-identical to their source. All 21 physical trajectories and grades reconstruct from accepted commands; 98 JSON files and 18,794 transcript rows parse, and all seven recorded agent-exit exceptions remain. Twenty-eight existing Traverse viewer tests pass, including byte-exact regeneration of the campaign page; unrestricted whitespace and local document-link checks pass. The saved farm rows total 5,971 missions and 105.08 core-hours, and the campaign records report $4.153 in model cost; neither is a billing-account audit. The original authors retain experiment and viewer credit. Codex ran no model program, new training, cloud job or rules change; the campaign's final numbers now replace the earlier provisional demo figures.

- **Controller comparison and submission-draft publication:** under Kristján's standing watcher request, Codex verified Claude Code's [submission draft and campaign comparison](https://github.com/solvisantos22/junction-2026/commit/1c48d9a622ba5421f9e6ebe727b55ab5e12f0279) and [300-world controller comparison](https://github.com/solvisantos22/junction-2026/commit/2a92f569c600632524d6e40586784630edfefe11). All 1,212 saved rows have complete player/world coverage and match the frozen source fingerprint; both evaluation tables and paired bootstrap comparisons reproduce exactly, as does the fresh-world analysis summary. Three existing analysis tests, unrestricted whitespace checks and 18 local document targets pass; all eight source files remain byte-identical. The original authors retain experiment and draft credit. The README remains a draft for team agreement, and the separate video claim includes no unfinished implementation. No new experiment, model program, training or cloud job ran; individual hidden home analyses and external submission-platform requirements were not independently rechecked.

- **Manual inventory and video publication:** at Kristján's request to check for work needing a push, Codex found and integrated the completed [nine-program MAX comparison](https://github.com/solvisantos22/junction-2026/commit/5ede8e8) and [narrated demo video](https://github.com/solvisantos22/junction-2026/commit/0d35606), with the author's shared-document correction `3cd67f0`. Parsed five saved JSON files, 1,200 JSONL rows and three new archived Python programs without executing them. The merged viewer suite runs 94 tests with one skip; video tooling syntax checks pass, and the complete 118.37-second, 1080p/30-fps H.264/AAC video decodes successfully. All 37 subtitle cues are ordered and within the video. The subtitle file's final blank cue separator is retained intentionally; the remaining diff passes whitespace checks. Original experiment/video authorship is unchanged. This publication check does not claim a new statistical audit, listening review, video rebuild, model call or cloud job. The source worktree's newer storyboard edit was preserved until its author committed opening fix `72d25f8`; Codex then integrated that follow-up and verified its Python syntax and a successful full decode of the updated video (still 118.37 seconds).

- **Battery evidence verification:** under Kristján's standing watcher request, Codex verified and integrated Claude Code's [battery summary for the 15 fresh-world wins](https://github.com/solvisantos22/junction-2026/commit/c0b4eb7f05c77bc1a209241a8890767456f92d45). Recomputed all 1,800 program/reference comparisons from the 2,100 saved farm rows: 1,780 reference wins, five ties and 15 Claude wins. Every winning pair and its reward, home/alive status and sample count match the original rows. The saved battery summaries support the reported five excursions below 5, ten wins never below 8 and 13 reference worlds all home and alive; repeated reference-world records agree. Both source files and the comparison data remain byte-identical, and unrestricted whitespace checks pass. Claude Code retains experiment and report authorship; Codex checked saved evidence without executing archived programs or starting cloud jobs. The tick-by-tick battery traces were not independently regenerated, and no rules or reference change was made.

- **Same-program comparison correction:** under Kristján's standing watcher request, Codex verified Claude Code's [normal-map comparison correction](https://github.com/solvisantos22/junction-2026/commit/055877b6f7192360e8cb5a844ceaf331b42efbc4) against Manh's saved second-machine evidence. The 150 saved rows and 2,100 original farm rows reproduce the stated means, two wins in 120 normal-map comparisons, and the older program's separate 300-world gap. The three saved judged-world scores give 169.75 / 358 = 0.474162, rounding to the reported 0.474. The cited section resolves and unrestricted whitespace checks pass. Original experiment and report authors retain credit; no archived program, simulator, model or cloud job was rerun, and the unchanged live-agent claim was not independently re-audited.

### 14 November — Kristján / Codex: RL-reference and Traverse failure review

- **Human direction:** Kristján asked whether to train an RL reference, inspect Sölvi’s existing work, and investigate mechanisms that references handle more reliably than Claude. Training and rules decisions remain with their existing owners.
- **Codex contribution:** independently reran Sölvi’s retained training/evaluation audits, reviewed the learner and active persistence wrapper, and wrote a read-only command-replay auditor for all eight saved Traverse model runs plus the reference and two controls. Derived an arithmetic score-gap breakdown and a bounded next-training/confirmation proposal. Sölvi’s model, learner and prior auditors and Claude Code’s simulator, pilot and original agent runs remain their contributions.
- **Verification:** 16 optimizer updates, 512 recorded training episodes and 21,078 draws reconstruct; all 240 RL evaluation physics replays and 8,559 recorded-feature choices reproduce. Eight existing persistence tests pass. All 11 Traverse replays/grades reconstruct; independent arithmetic, document links and injected wrong-grade rejection pass. Process-exit exceptions, Haiku output-length truncation and the one-map/post-tuning limits are retained.
- **Result and human decisions:** the RL learning screen still fails; the seven completed Opus/Sonnet runs’ mean score gap decomposes into 69.14% sample-value difference and 30.86% terminal penalties, an accounting identity rather than a causal rescue. Recommends using the existing persistence diagnostic and its missed-return follow-up before further learning, preserving the beam reference and confirming any mechanism on fresh full-agent runs. No new model generation, training, cloud spend, rules promotion or prize submission.
- **Artifacts:** [review and handoff](research/2026-11-14-rl-reference-and-failures.md), [reproducible auditor](../tools/reference_gap_review/audit.py), [retained review data](reference-gap-review/review.json), [rerun training audit](reference-gap-review/rl-training-audit.json), [rerun check audit](reference-gap-review/rl-check-audit.json).

- **Persistence follow-up in the same review:** as Sölvi’s result landed, Codex independently recomputed all arm means, paired home outcomes, the 24-map primary gain/bootstrap and failed return gate; reran all 240 physics/grade and 10,479-choice checks and all 21 published tests. The score gains are from unchanged weights under a commitment rule, not new RL learning. Initial-policy home transitions include 12 home-to-away and eight away-to-home cases. Sölvi retains the missed-return diagnosis and training scope. [Independent statistics](reference-gap-review/persistence-summary.json), [replay audit](reference-gap-review/persistence-audit.json).

### 14 November — Kristján / Claude Code: Traverse rollout farm on Modal

- **Human direction:** Kristján asked Claude Code to use his Modal credit to create an RL model that would do very well at Lightlag Traverse. Claude Code proposed starting with a rollout farm that plays many missions in parallel, to measure the reference pilot against Claude's saved programs on fresh worlds and to search the pilot's options. Kristján said to build it, asked for frequent commits, and logged in to Modal himself. The Traverse owner's session asked for the paired comparison first, then for Opus agent 3 and Sonnet agent 1 to be rebuilt from their trajectories and added, then for a pilot-only run under its proposed harsher day.
- **Tool:** Claude Code (the session reports its model as Claude Opus 5.5), with the Modal 1.6.4 client. No model API calls: the Claude programs replayed were written in earlier, already recorded runs.
- **Claude Code contribution:** [`tools/traverse_farm/`](../tools/traverse_farm/): one mission per job, a Modal app and a local process pool, paired comparison with bootstrap intervals, a ledger that saves part by part and resumes, missions on changed rules, and per-program diagnostics (where it stopped, when the battery ran out, the end of its output). It also has an option search with selection and confirmation on unseen worlds, not yet run. 31 tests. The two agent programs were rebuilt from their trajectories, with a labelled wrapper repeating Opus agent 3's by-hand setup. Before any result was used, Claude Code found and fixed its own bug: saved program rows shared one key, so programs dropped out of tables and would have been mixed up on a rerun.
- **What it found:** on 300 fresh worlds (600–899), paired, the reference pilot (0.502) beats all six saved Claude programs on 288–300 of the 300 worlds and never loses a rover. The programs score 0.321 (one-request Opus), 0.309 (Opus agent 1), 0.265 (Sonnet agent 1, 91 rovers lost), 0.221 (Opus agent 3, 157 lost), 0.094 (one-request Sonnet) and 0.039 (one-request Haiku). Under the owner's proposed harsher day the pilot scores 0.435, never lost, and is stranded on 2 worlds. These replay programs without their agents, so they measure the programs, not the agents. [Results and limits](traverse-farm.md).
- **Modal jobs:**
  - smoke against the laptop `ap-kew5v67eaVvOdeMDDAbtzZ`
  - task-world replays `ap-GnrGDGApXmzHdabvZmKkJ7` and `ap-xv5BaJGa8rfv96Cl9sx7ZQ`
  - comparison `ap-gBRd5446NAlbSopK5sdrI4` (1500 missions in 7 minutes) and `ap-758nYv4YvdQRCYPMuSAv1V` (600 in 23 minutes)
  - harsher day `ap-T2EvbsPSpwUE9Jy1mFCOiH`
  - farm check on the owner's worlds 1–8 `ap-aXFI1zwa4J4dBGGioCveZx`
- **Modal configuration:** CPU functions with 1 core and 1 GiB each, up to 100 containers (the workspace limit, reached; further missions queued), a 30-minute timeout, and a Debian-slim Python 3.12 image holding the repository's `lightlag`, `lightlag_traverse` and the farm. Model-written programs run only inside these containers; the local command refuses them.
- **Usage, not checked against a bill:** about 6,000 missions and 105 core-hours of mission time by 21:15 (the sum of per-mission times over every saved row, including the point-of-no-return run `ap-HeqHK3dHG5bKO0hFzbv9lU` and the stopped option search; container start-up and idle time not included), roughly $6 at Modal's published CPU and memory rates.
- **Why Modal mattered:** the 2100-mission comparison took about 30 minutes of wall time instead of hours on a laptop, and it kept model-written code off the laptop.
- **Verification:**
  - 16 missions scored identically on Modal and on the laptop.
  - Opus agent 3's rebuilt program reproduces its Harbor score on the task's world (0.515), and the owner's eight scores on worlds 1–8.
  - Missions in containers that Modal preempted were replayed from the start; a mission is deterministic per world, so this changes no result.
- **Evidence:** [write-up](traverse-farm.md), [comparison rows](traverse-farm/programs-1/), [harsher-day rows](traverse-farm/sun-margin-0/), [code](../tools/traverse_farm/), [tests](../tests/traverse_farm/).
- **Live deployed demo (added 22:15, at Kristján's request):** `modal deploy tools/traverse_farm/live_app.py`, app `lightlag-traverse-live`, https://kristjansolvi03--lightlag-traverse-live-web.us-east.modal.run. A visitor picks any world; Modal drives the reference, a textbook controller (terrain graph + Kalman filter, greedy targets) and two Claude-written autopilots on it in parallel containers and serves the Traverse demo page for that world, cached in a Modal Volume. Only fixed code from the repository runs; the visitor supplies only the world number. Checked: the landing page, a cached world, a new world built live, and a refused malformed request.
- **Controller ladder (22:00):** on 300 fresh worlds a textbook controller (terrain graph + Kalman filter, greedy targets) scores 0.314 and strands 140 rovers, like the best saved Claude programs; route planning lifts it to 0.489; the reference's reserve adds 0.013 and prevents 10 flat batteries (app `ap-Z31svlFPlHs0F1fT95mFf7`).
- **Scope:** no change to `lightlag_traverse/`, the Harbor task or any teammate's file; no Harbor run, model API spend or prize submission.

### 14 November — Kristján / Codex: charging-aware RL follow-up

- **Human direction:** Kristján approved the review’s next steps: check charging-aware visit/return feasibility, then conditionally try contextual planner-initialized learning and fair model comparisons.
- **Codex contribution:** an isolated public-information candidate filter using the existing reference route model, a frozen paired development protocol, a bounded local runner with complete traces and a physics/scaffold re-execution auditor. Sölvi’s policies, persistence wrapper and original experiments, and Claude Code’s navigator and route model retain their original attribution.
- **Verification at implementation checkpoint:** seven focused tests pass; 20 smoke missions complete with no deaths or invalid calls. All 20 physics replays and 879 choices/features/commands re-execute exactly; all 21 inherited persistence tests pass. Production comparison has not yet run; no new learning or frontier-model claim.
- **Artifacts:** [protocol](lightlag-rl-feasible.md), [helper and runner](../lightlag_rl_feasible/adapter.py), [results and reproduction](lightlag-rl-feasible-results/README.md). No canonical rule change, cloud job, model API spend or prize submission.

- **Completed fixed feasibility comparison:** protocol/helper published first at `5b5dcb2`; all 240 missions and 10,659 choices/features/commands reproduce, including exact equivalence of all 120 old controls. Charging-aware runs return alive/home120/120 versus70/120; fixed final weights score .093678 → .115034, paired gain .021355 with map-bootstrap95% [.010901,.031750]. Initial and greedy controls also improve; no deaths/invalid calls. This passes the declared development screen on reused maps. It is an interface improvement with unchanged policy weights, not new learning or a fresh Claude result. [Full result/audit](lightlag-rl-feasible-results/README.md).

- **Contextual learning implementation:** [fixed three-seed protocol](lightlag-rl-contextual.md), public candidate/route context, planner teacher collection, imitation-only checkpoints and terminal-reward RL delivered in isolated packages. Reuses Sölvi’s gradient/Adam math and the unchanged reference navigator. Six focused tests and the 54-mission used-map smoke pass: all physics replay, all three optimizer updates and 536 training draws reconstruct, all 42 teacher/evaluation scaffolds re-execute. Production code is published before any reserved training/check map is opened. [Reproduction and scope](lightlag-rl-feasible-results/contextual.md).

- **Completed contextual pilot:** code/smoke published at `55654bb` before 20 teacher missions, three fixed initializations, 600 total imitation epochs and 384 RL missions / 24 updates. On 16 matched fresh worlds (320 evaluations), untrained .092619 → imitation .282207 → RL .279219; greedy .326323, unchanged reference .509094. Every evaluation returns alive/home. The primary RL-minus-imitation gain is −.002988, 95% [−.014367,.006583], so the declared promotion screen fails and the original planner remains the reference. All seeds/checkpoints and negative results retained; no post-check tuning.
- **Final verification and handoff:** all 600 imitation epochs, 24 RL updates and 18,380 training draws reconstruct; all 724 teacher/training/evaluation physics replays and all 340 teacher/evaluation scaffolds reproduce. Six new focused tests, the 54-mission smoke and all frozen input/source checks pass. [Full results, audit, checkpoints and limits](lightlag-rl-feasible-results/contextual.md). Check maps 74000–74015 are consumed. Sölvi’s larger scratch-learning campaign is separate; no fresh full-agent Claude claim, new rule, cloud/API spend or prize submission.

### 14 November — Sölvi / Codex: contextual learning campaign

- **Human direction:** Sölvi asked to investigate Rainbow and alternatives, then use Modal credits for meaningful training before submission; reported $300 shared team credit.
- **Codex contribution:** researched original Rainbow/PPO/demonstration-learning papers; implemented a public candidate-context model, scratch PPO and Double DQN with prioritized replay and three-step returns, persistent goal options, reproducible training/resume and bounded Modal launcher. Reuses Kristján’s newly published charging-feasibility helper and Claude Code’s original Traverse environment/navigation; does not claim those contributions.
- **Verification:** 36 focused tests pass, including exact optimizer/replay checkpoint continuation, masks, terminal reward and launch deadline/duplicate-job guards. Both algorithms completed a 32-mission smoke on already-used maps 1/2; these are engineering checks, not fresh learning evidence.
- **Decisions/evidence:** [frozen protocol](learning-campaign.md), [code](../lightlag_learning/train.py), [preflight](learning-campaign-results/preflight/). Three initialization seeds, explicit validation gates, fresh final maps and bounded CPU phases; no GPU/LLM API or project promotion. Cloud receipts/results will be appended only after actual execution.

- **Actual campaign launch:** source `d13bcd7` and freeze `e8a8acb` published before six2048-mission Modal jobs were submitted. [Receipt](learning-campaign-results/pilot-receipt.json), [live handoff/app](learning-campaign-results/README.md). First three PPO workers confirmed running, replay jobs queued; no completed production learning result or billed-cost claim yet. Independent preflight action/update reconstruction and32→64 replay resume pass.

- **Verified continuation/evidence increment:**61 tests pass; [preflight audit](learning-campaign-results/preflight/audit.json) exactly reconstructs96 smoke missions,705 training choices,88 validation choices and3updates, with full archives retained. Published bounded continuation supervisor and final evaluation/audit tools. [Early PPO validation](learning-campaign-results/early-validation.json) at512 missions improves across all3seeds (.0874→.3440 averaged); [64 matched control missions](learning-campaign-results/validation-controls/report.json) are fully physics-audited: greedy .3806, beam .5143, allhome. These are reused validation, not final wins or frontier-model gaps. Supervisor actually started from frozen code and checked alive/monitoring; final maps remain unopened, costs await terminal receipts.


### 14 November — Manh / Claude Code: a PPO + ICM baseline tester for the max env

- **Human direction:** Manh asked Claude Code for a PPO + ICM reinforcement-learning agent as a baseline tester, while another of Manh's chats was building the max environment for the traverse. As before, Manh reviews before anything is pushed, so the work stayed on a local branch until Manh gave the go-ahead to push.
- **Claude Code contribution:** `lightlag_ppo_icm/`, new files only. PPO and an Intrinsic Curiosity Module written in NumPy with hand-derived gradients, each checked against finite differences; an adapter that turns the five public tools into observations, actions and rewards (one decision per execution slot across relay passes, a four-number Kalman filter for position, wheel scale and heading bias, a battery guard, the official score cut into per-decision rewards that add up to it exactly); training on several processes; a check that plays a trained policy beside the scripted players on the same seeds; and a report of how a policy spends its commands. Claude Code chose NumPy over installing a deep-learning framework, found Sölvi's `lightlag_rl/` on `main` before starting and kept clear of it, and reserved its seeds in `TEAM_STATUS.md` before any run.
- **What the measurements changed on the way:** the first runs scored nothing because an untrained agent drives the battery flat and a dead rover scores 0, so a battery guard was added; a replay showed the first curious agent bumping a hazard because the observation echoed its own last command, so the curiosity module now sees only where the rover is; a run on `rush` stalled at 4% until the drive lengths were made to fit the sampling disc; and a count of the trained agent's commands showed why it never comes home (it has spent its energy by mid-mission), which an optional reward for approaching the base did not fix in three further runs.
- **Results, as measured:** on 40 fresh missions of the max env (seeds 2700-2739, used once) the PPO + ICM policy scores 11.0%, level with three scripted players, above the frozen `kf_mpc` (6.2%), below a hand rule of a few lines on the same adapter (15.3%) and below `max_navigator` (28.2%); random actions on the same adapter score 0.1%. PPO without curiosity scores 10.7%: no measurable difference. One training run per setting. [Tables, logs and limits](../lightlag_ppo_icm/README.md).
- **Verification:** 47 tests (gradients, a bandit the learner must solve, curiosity fading on seen transitions, the adapter's slots, rewards and belief against the simulator's replay, the guard, a two-update training run, the check and the player), passing on Python 3.14 with numpy 2.5 and Python 3.12 with numpy 1.26. The tests of the max env it reads still pass.
- **Evidence:** [package](../lightlag_ppo_icm/), [tests](../tests/lightlag_ppo_icm/), [trained policies, run logs and check rows](../lightlag_ppo_icm/policies/).
- **Scope and limits:** a sandbox baseline, not a rules or reference decision. No model or API call, no cloud compute, no Harbor change, no prize submission. The adapter is hand-written and carries part of the result; the write-up says how much by playing a hand rule and random actions through the same adapter.

### 14 November — Sölvi / Codex: final Traverse training compatibility

- **Human decision:** Sölvi paused larger training for the final task; Kristján froze normal Traverse and the final home-return controller. Keep the submission reference unchanged and resume only a separately pinned experiment.
- **Codex contribution:** recovered the completed six-run pilot, distinguished unchanged physics from changed controller behavior, implemented isolated final-version training/launch/staging/evaluation tools, and ran a matched112-mission compatibility study with full physics and controller audits. All56 paired grades match;28 home-return traces change. Both declared compatibility gates pass.
- **Verification/artifacts:** [protocol](learning-final.md), [compatibility and verification](learning-final-results/compatibility/README.md), [preflight and handoff](learning-final-results/README.md). Both algorithms complete32-mission local smoke runs on worlds1/2; source/runtime pins, checkpoint recovery, bounded reservations, pause handling and evidence tampering are tested. Final82000–82039 maps remain unopened.
- **Limits:** engineering/used-map evidence only; no fresh generalization, planner superiority or LLM-training claim. The new larger Modal run is pending publication of its source freeze. Old pilot cost/results belong to its original navigator and remain separately labelled. No model API call or prize submission in this increment.

- **Published launch follow-up:** implementation `becbf3e`, source/runtime freeze `2257871`, [six-job receipt](learning-final-results/fit-receipt.json), [Modal app](https://modal.com/apps/solvisantos22/main/ap-GGkMI4eQi8N9MVVuTef5Au). All six fresh final-version jobs verified running. Codex prepared and verified 51 tests, compatibility evidence and the bounded all-seed continuation monitor; Sölvi authorized larger training after the team finalized the task. Maximum running-compute envelope $18.185472 plus ancillary charges, not measured spend. Old completed-pilot estimate $1.592405 is separately retained in its [closure evidence](learning-campaign-results/pilot/README.md). Final checks and any campaign showcase remain pending.

### 14 November — Sölvi / Codex: continue after training

- **Human direction:** Sölvi asked whether Codex would continue once training finishes.
- **Contribution:** added a separate one-time completion watcher using the installed Codex CLI to resume this same chat for final policy freezing, evaluation, audit and publication. It observes the existing monitor, preserves the frozen training setup, respects pauses, and reserves dispatch before attempting it so crashes cannot cause repeated prompts.
- **Verification:** 13 focused tests pass; an independent review found no duplicate-dispatch or pause-bypass blocker. A live local poll returned waiting, and the detached watcher process is active. [Implementation](../tools/learning_final/wake.py), [tests](../tests/learning_final/test_wake.py), [operation and limits](learning-final-results/README.md#continue-this-chat-when-training-settles). No actual test prompt or new cloud job was sent. Future resume requires the Mac, Codex and usage allowance to remain available.

### 14 November — Sölvi / Codex: visible training checkpoints

- **Human direction:** Sölvi asked for checkpoints their teammates could follow while working on the demo and submission, then relayed a 07:30 Helsinki request for a clean comparison, paragraph, figure and Modal evidence.
- **Contribution:** implemented read-only collection of immutable policy/validation pairs with receipt, hash, map and reward-arithmetic checks; retains all six runs and compares methods only at a common checkpoint for all three initialization seeds. [Timestamped team progress](learning-final-results/progress.md) distinguishes observed batch-file coverage, validated checkpoints and rough estimates.
- **First published snapshot:** final-version PPO mean .087395 → .380123 at2048 missions, all96 validation cases home/alive, zero invalid calls. Replay's matched three-seed512 checkpoint is .276713, also96/96 home/alive. These are reused validation worlds, not a final-test result or reference win. Seven collector tests pass, with independent review.
- **Handoff correction:**72000–72039 were already consumed by the earlier experiment; this campaign reserves82000–82039 for the once-only final comparison after policy freezing. No new training or model API call is introduced by progress reporting.

- **Automatic publication verified:** reporter implementation `73b84fc`; first live update `637764d` adds the complete three-seed replay2048 mean .369464 alongside PPO .380123, each96/96 home/alive and zero invalid calls on reused validation. All24 collector/publisher tests pass. The separate fixed-runtime process publishes narrow verified commits every15minutes or on common checkpoints/status changes, and stops by03:40UTC. No training change, new model API call or final-map evaluation.

### 14 November — Manh / Claude Code: a home guard for the PPO + ICM tester

- **Human direction:** Claude Code proposed the home guard (the first pick of its learning-methods brainstorm for the Lightlag environments) as a follow-up task for the PPO + ICM tester; Manh started it in the same chat. Manh reviews before anything is pushed, so the work stayed on a local branch until Manh gave the go-ahead to push.
- **Claude Code contribution:** an opt-in home guard in `lightlag_ppo_icm/` (new `home.py`, a cost-to-go field on a half-metre grid of the published map; the guard in `task.py`, which checks before every command whether the way home still fits in the energy and the time left and sends a drive home or a wait in its place); `--home-guard` in training, `plain_home` and `--also-home` in the check, the guard's count in `habits`; 13 new tests; two training runs with the settings of `max.npz` (with and without curiosity); the fresh check; a README section. A diagnosis on the development seeds (reading the simulator's truth for diagnosis only) showed that most rovers the first version left away were trapped in sand that trips the onboard slip check, one 6 cm step per relay pass, which changed the guard to keep off such sand from the start (55 of 64 development missions home, against 49).
- **Results, as measured:** on 40 fresh missions of the max env (seeds 2800-2839, reserved before any run, used once) the learned agents with the guard come home in 34 to 36 missions (none without it) and score 15.7 to 16.9%, against 12.8% for `max.npz` without it; switching the guard on for `max.npz` with no retraining adds 4.1 points (95% +1.7 to +6.6); training with the guard was level with switching it on (-0.8, -4.9 to +3.2); the hand rule scores 18.2% without the guard and 10.5% with it; `max_navigator` 32.6%. One training run per setting. [Tables and limits](../lightlag_ppo_icm/README.md).
- **Verification:** 60 tests (the 47 earlier ones and 13 for the guard: it is off by default, brings rovers home, fires when the slack is down to about one more drive out and not at the start, never lengthens the way home with its own drives, keeps the rewards adding up to the official score, leaves a rover waiting at base alone, changes only the two margins in the observation, and plans around hazards and sand) pass on Python 3.14 with numpy 2.5 and Python 3.12 with numpy 1.26. With the guard off, the 120 earlier check rows of `max.npz`, `plain` and `random` on seeds 2700-2739 replay exactly, and the final code reproduces the 320 rows of the new check exactly.
- **Evidence:** [guard](../lightlag_ppo_icm/home.py), [tests](../tests/lightlag_ppo_icm/), [policies, run logs and check rows](../lightlag_ppo_icm/policies/).
- **Scope and limits:** a sandbox baseline, not a rules or reference decision. No model or API call, no cloud compute. Flat 40 m family only. The guard trusts the belief, which can be off by more than the base radius at the end; crust, which hides soft cells, is only priced at twice its cost. Training with the guard did not teach the agent to pace itself: the guard does the pacing.

### Kristján / Codex — reference component ablations (14–15 November)

Kristján asked Codex to modify each part of the reference a little and collect
more numbers. Codex implemented an isolated 15-configuration sweep, including
cubature heading propagation, with pinned sources, paired maps, frozen candidate
selection and fresh confirmation. It builds on the team's existing pilot and
simulator; those and Sölvi/Manh's learning packages were not edited. Kristján set
the experimental scope. The evidence supports retaining the frozen reference.

Seven focused tests pass. All 180 development and 128 fresh confirmation missions
finish home/alive with no invalid calls or controller exceptions. Fresh baseline
0.523064; selected combination 0.524087: +0.001023, paired 95% interval
[-0.003556, +0.005227], failing the predeclared improvement criteria. Cubature
matches all 12 development scores; 50% more search costs 45% more CPU for only
+0.000109 reward. The negative findings are retained. All 323 archived physics
replays (including 15 smoke missions), 129,185 commands and 135,983 states verify;
four full controller repeats match exactly. No cloud job or evaluation model API
call. The study does not make a new Claude-performance claim.

[Implementation commit](https://github.com/solvisantos22/junction-2026/commit/815688b),
[development/selection published before fresh evaluation](https://github.com/solvisantos22/junction-2026/commit/ca558c9),
[protocol](reference-ablation.md), [results and raw data](reference-ablation-results/README.md),
[verification](reference-ablation-results/verification.json).
