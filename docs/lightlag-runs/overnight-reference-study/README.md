# Overnight reference-strength study

The fixed candidate improves some rush cells, but is not uniformly
better. Its mean gain on the fresh rush set is **0.79 percentage points**,
with three wins, sixteen ties and one loss. All noisy-profile scores tie.
The canonical reference and original model results remain unchanged.

The [published protocol](../../lightlag-overnight-evaluation.md) at
`f72f479a0a2cefb1eb96305d2628b8eaae9a19bd` fixed both policies, source revision,
settings and seeds before outcomes. The source is
`5ff2ca2caf175b63243532a500104f26952df3db`. There was no paid inference.

Both policies ran on plain `DynamicEnvironment`, delay 3, horizon 50, noise
level 1 and bumpiness 0. The original is `kf_mpc`; the candidate is the
directly instantiated class
`EKF_sandodo_stayalive_aimdisc_turncost_window_MPC` (registry name ending
`_manh_controller_24`). No candidate was selected separately for each map.

| Set / profile | Paired cells | Original mean | Candidate mean | Mean difference | Candidate wins / ties / losses |
|---|---:|---:|---:|---:|---:|
| Historical 501–504 / rush | 4 | 0.724679487 | 0.828525641 | +0.103846154 | 2 / 2 / 0 |
| Historical 501–504 / rush_noisy | 4 | 0.690224359 | 0.690224359 | 0 | 0 / 4 / 0 |
| Fresh 3000–3019 / rush | 20 | 0.772639166 | 0.780536894 | +0.007897727 | 3 / 16 / 1 |
| Fresh 3000–3019 / rush_noisy | 20 | 0.683006022 | 0.683006022 | 0 | 0 / 20 / 0 |

Scores are raw mission reward divided by the mission's maximum available
value. Every one of the **96 planned episodes** completed, with **zero
execution errors**; all 96 rovers were alive at base at tick 50. The
[summary](primary/summary.json) retains every row, calls, survival/home
status, paired differences, error lists and the separately labelled
historical model comparison. Mean policy calls, original → candidate: 62.75
→ 66.50 historical rush; 63.25 → 66.25 historical noisy; 62.95 → 66.20 fresh
rush; 63.40 → 66.40 fresh noisy. These local callback counts are not model
token usage or wall-clock latency costs.

The fresh rush improvements are seeds 3011, 3014 and 3015. The regression is
seed 3017: raw reward **6 → 4.5**, normalized **0.545455 → 0.409091**, while
both return home alive. Historical rush improves at seed 502 (**8 → 9.5**
raw points) and seed 504 (**7 → 10**). Tied noisy scores do not imply identical
behavior: only five of the 24 noisy cells have identical full replays.

These are descriptive results on the predeclared cells, not a claim of
optimality or broad superiority. Fresh cells compare controllers only;
there are no model results on seeds 3000–3019. A future reference change
requires a separate team decision and version. No settings, policies or
seeds were changed in response to outcomes.

## Historical original models against the candidate

This is a **post-hoc reference substitution analysis** of the eight original
model attempts. It is separate from the failure-selected overnight repeats,
and it does not replace the [original comparison](../../lightlag-fixed-seed-comparison.md)
or its reference-relative audits.

| Profile / seed | Original model | Original reference | Candidate |
|---|---:|---:|---:|
| rush / 501 | 0 | 0.833333 | 0.833333 |
| rush / 502 | 0.769231 | 0.615385 | 0.730769 |
| rush / 503 | 0.750000 | 0.750000 | 0.750000 |
| rush / 504 | 0.700000 | 0.700000 | 1.000000 |
| rush_noisy / 501 | 0.791667 | 0.666667 | 0.666667 |
| rush_noisy / 502 | 0.634615 | 0.769231 | 0.769231 |
| rush_noisy / 503 | 0.750000 | 0.625000 | 0.625000 |
| rush_noisy / 504 | 0 | 0.700000 | 0.700000 |

Against this candidate, those original attempts have **3 wins, 1 tie and 4
deficits**. The changed classification is rush seed 504, which was a tie
against the original reference. Historical model means remain 0.554807692
for rush and 0.544070513 for noisy; candidate means are 0.828525641 and
0.690224359 respectively. No model was rerun for this analysis.

## Boundary and verification

The candidate receives only `lightlag.controllers.api.PublicTools` callbacks
through the shared `lightlag.evaluation.run_episode`. Its actual inheritance
chain and inherited methods were reviewed before outcomes. `Current.logger`
remains null; no registry wrapper, oracle, `ScenarioEnvironment`, scenario
factors or real-time clock is used. The callback interface is auditable
trusted Python, not an introspection security sandbox.

All 19 imported repository Python files were copied from the source commit
into an isolated snapshot before execution. This let teammates update the
live worktree without affecting the study. The runner checks those source
hashes, the historical evidence inputs and its own bytes before and after
every episode. An unexpected mismatch aborts while retaining completed
artifacts. Execution failures receive null scores and are not retried. The
output directory must be new, so a rerun cannot overwrite earlier evidence.

- All **eight historical KF + MPC results, entire replays, policy-call
  counts and six-decimal Harbor rewards** match the frozen Harbor references.
  This gate passed before any candidate episode ran.
- A deterministic rerun produced **100 byte-identical files**: 96 complete
  episode JSONs plus the source manifest, runner, protocol snapshot and
  summary. [Reproduction check](reproduction/reproduction.json).
- An independent verification script replayed **6,310 policy/evaluator
  calls** across all 96 episodes, matching every returned value, final
  result and full replay; it also recomputed four paired groups and checked
  the eight historical model scores against evaluator artifacts.
  [Final verification report](verification-final.json).
- Five focused runner checks cover existing-output preservation, one-shot
  failed execution with null score, source mismatch, same-score trajectory
  mismatch and exclusion of failed pairs from score denominators.
  All five passed.

The second execution is a reproduction check, not 96 more independent
samples. Its identical full files were moved to temporary storage after
verification; the repository retains paired SHA-256 hashes and sizes for
all 100 files, with one complete copy of the 96 study episodes. Public
transcripts and evaluator truth belong in this evidence
bundle; no credential files or private agent state were read or copied.
The scientific JSON passed personal-path and token-pattern checks.

## Files and reproduction

The [runner](../../../tools/lightlag_experiments/overnight_references.py), its
[exact executed copy](primary/runner.py), [source/dependency manifest](primary/source-manifest.json),
[96 full episode artifacts](primary/episodes/), [independent verifier](verify_artifacts.py)
and [guard checks](checks.py) are retained. `primary/protocol.md` is a verbatim
snapshot of the published protocol; its relative links use the original
`docs/` location. Dependencies were **CPython 3.12.16 and numpy 2.5.4** on
Darwin arm64; no package installation is performed by the runner.

These were the exact execution commands, from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/lightlag-6974-overnight-analysis/bin/python docs/lightlag-runs/overnight-reference-study/checks.py
PYTHONDONTWRITEBYTECODE=1 /tmp/lightlag-6974-overnight-analysis/bin/python tools/lightlag_experiments/overnight_references.py --source-root /tmp/lightlag-6974-overnight-reference-source5ff2ca2 --output docs/lightlag-runs/overnight-reference-study/primary
PYTHONDONTWRITEBYTECODE=1 /tmp/lightlag-6974-overnight-analysis/bin/python tools/lightlag_experiments/overnight_references.py --source-root /tmp/lightlag-6974-overnight-reference-source5ff2ca2 --output docs/lightlag-runs/overnight-reference-study/reproduction --compare-to docs/lightlag-runs/overnight-reference-study/primary
PYTHONDONTWRITEBYTECODE=1 /tmp/lightlag-6974-overnight-analysis/bin/python docs/lightlag-runs/overnight-reference-study/verify_artifacts.py --source-root /tmp/lightlag-6974-overnight-reference-source5ff2ca2 --report docs/lightlag-runs/overnight-reference-study/verification.json
```

After relocating the identical reproduction tree, the final verification
also rechecked the complete temporary copy against the compact hash record:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/lightlag-6974-overnight-analysis/bin/python docs/lightlag-runs/overnight-reference-study/verify_artifacts.py --source-root /tmp/lightlag-6974-overnight-reference-source5ff2ca2 --reproduction-root /tmp/lightlag-6974-overnight-reference-reproduction-v1 --report docs/lightlag-runs/overnight-reference-study/verification-final.json
```

Choose a new `--output` directory, preferably under temporary storage, for
another full reproduction. Keep `--compare-to` pointing to `primary`.
Omit `--report` when rerunning the verifier to print its report without
creating another file. Without `--reproduction-root` it checks the retained
paired hash evidence; with that option it also compares the full copy.
To recreate
the isolated source snapshot, choose a new directory in the script below;
this uses only read-only Git commands and checks each copied file:

```python
import hashlib, json, pathlib, subprocess
manifest = json.loads(pathlib.Path("docs/lightlag-runs/overnight-reference-study/primary/source-manifest.json").read_text())
snapshot = pathlib.Path("/tmp/lightlag-reference-source-new")
snapshot.mkdir(exist_ok=False)
for relative, expected in manifest["source_sha256"].items():
    data = subprocess.check_output(["git", "show", manifest["source_commit"] + ":" + relative])
    assert hashlib.sha256(data).hexdigest() == expected
    target = snapshot / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
```

The coordinator can publish this directory and the single runner file after
review. No canonical reference, controller implementation, benchmark rule,
model run or existing evidence file was changed by this study.
