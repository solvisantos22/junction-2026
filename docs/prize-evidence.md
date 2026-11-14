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
  Evaluation review is now complete: all 42 checks pass, including interrupted
  attempt retention, null-score bounds and non-fabricated reproducibility. The
  actual single paid response remains pending at this increment. No policy
  result, sponsor usage or prize entry is claimed yet.

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
