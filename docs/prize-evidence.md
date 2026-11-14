# Prize evidence log

Started 14 November 2026. **Maintain this alongside meaningful shipped work, not every prompt or bookkeeping commit.** Its purpose is to make actual sponsor use easy to demonstrate and accurately attributed. A log entry is not a prize entry or proof of eligibility.

## Prize focus and source freshness

Recommendation: AfterQuery as the primary challenge, Best Use of Codex as the natural additional entry, and at most one compute provider if it becomes useful. A model prize is conditional on a substantive integration. Tech challenges can accompany the main track. [Official Junction overview](https://2026.hackjunction.com/)

The detailed sponsor briefs were last read directly on the logged-in platform on **13 November, about 22:10 Helsinki**, as recorded in [SPONSOR_OPTIONS.md](../SPONSOR_OPTIONS.md). Direct Chrome/Discord access was blocked during this 14 November audit, and the authenticated prize pages were unavailable through web search. The table below carries that freshness limit; it does not imply a fresh confirmation of eligibility, balances, separate forms or entry status.

| Prize / opportunity | Current decision and actual evidence | What to retain if pursuing it | Entry status |
|---|---|---|---|
| **AfterQuery — Break the Agent** | Primary provisional challenge. Kristján delivered original-task model evidence (Opus 1.0); Codex integrated the dynamic task and ran fresh Opus trials on `rush` and `rush_noisy`, both 1.0. All match their reference: no model gap demonstrated on these examples. [Requirements and gaps](afterquery-readiness.md). | Harbor task/version, real model logs/configuration, 0–1 verifier score plus raw diagnostics, fair reference/baseline comparisons, exploit probes and demo. | Lightlag draft recorded; final submission not verified. |
| **[Best Use of Codex](https://hackjunction.app/participate/45/tech-challenges/49)** | Recommended additional entry; substantial development/review work is evidenced below. Last-read brief asks for meaningful use to build, iterate and ship. | Concrete task/prompt summary → Codex change → review/test → commit/result. Keep a few safe genuine session captures and one concise development story. | Selection/submission and any evidence/form specifics still need a live check. No mandatory screenshot format is established by this log. |
| **[Modal](https://hackjunction.app/participate/45/tech-challenges/40) OR [Verda](https://hackjunction.app/participate/45/tech-challenges/56)** | Conditional infrastructure candidate. Sölvi's Modal grant is confirmed in the [credit notes](../SPONSOR_OPTIONS.md), but no Modal deployment/job evidence is recorded. The new experiment ran in local Docker. | Actual deployment/job ID and configuration, what ran, logs/metrics, live demo or results, and why the service mattered. Verda's last-read brief also asks for a process summary link in its Discord channel; capture that requirement, but do not post automatically. | Not verified entered; choose based on real infrastructure needs. |
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
- **What the early test found:** on 40 unused seeds (52,080 scripted episodes) controller 33 has the best mean share over all biomes, 74.9% against 73.0% for the frozen reference (+1.9 points, 95% interval +1.0 to +2.8). It equals controller 24 everywhere except Hidden Valley, and the 24 family lies within 0.3 points, which is noise. [Results, settings and limits](lightlag-biomes.md).
- **Verification:** 24 biome tests (one through a real MCP client) and 11 demo tests; all 95 `lightlag_dynamic` tests and 40 viewer tests pass. Main Mars is identical to `DynamicEnvironment` (rules, map, telemetry, replay). A build of the biome page leaves the main demo's five files byte-identical (hash test). The page was walked through in headless Firefox: title screen, a Main Mars mission, every biome, the compare view and playback, with no script errors. Not checked in Chrome.
- **Evidence:** [package](../lightlag_dynamic/biomes/), [biome tests](../tests/lightlag_dynamic/test_biomes.py), [trial report](lightlag-biomes/trial-report.md), [demo builder](../viewer/build_biomes.py), [add-on](../viewer/biomes/addon.js), [demo page](../viewer/biomes-demo.html).
- **Follow-up the same afternoon:** Manh asked for a slightly different colour palette per biome, so that the screen shows which biome is playing while still looking like Mars. Claude Code added it to the add-on only (ground, sand, rocks, light, haze and sun shifted a little per biome; Main Mars unchanged), with a test that keeps every shift small. Manh looked at a comparison sheet before it was pushed.
- **Scope and limits:** a sandbox option, not a rules decision. Scripted controllers only; no model has played a biome; no API spend, Harbor change or new prize submission. No controller reads the new published areas yet, and the default settings are mild by the keep rule.
