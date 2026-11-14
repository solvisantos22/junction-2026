# Additional reference check: candidate 27

Candidate 27 has **lower mean reward than both earlier policies** on the
already inspected 3000–3019 set, on both profiles. All 48 candidate attempts
completed without error and returned home alive. The mixed per-cell results,
including improvements, are retained; this supplement does not establish a
reason to replace the reference on these plain profiles.

The [supplement protocol](../../lightlag-overnight-evaluation.md#later-reference-supplement-candidate-27)
was published at `d9d5d32d244e52293c7bdfc0ad317f4d57962529` after the
candidate-24 aggregate results and before any candidate-27 outcome. It fixed
one candidate at `bdb77f629d1cee55d12c4275e5f31d351143361e` and the same 48
cells. **This is a later selected-policy check on already inspected cells,
not new independent held-out confirmation.** No additional candidates,
parameter tuning or seed replacements followed these outcomes.

The class directly instantiated was
`EKF_fading_sandfilter_sandodo_guarded_aimdisc_turncost_window_MPC`, registry
name ending `_manh_controller_27`. Every episode used plain
`DynamicEnvironment`, delay 3, horizon 50, noise level 1 and bumpiness 0.
Scores are raw mission reward divided by that mission's maximum available
value. All three policies are feasible public-information baselines, not
optimal policies.

## Paired results

The original KF + MPC and candidate-24 rows are reused from the
[unchanged first study](../overnight-reference-study/README.md), published at
`187601048b30c0686d5867ebc76781baf65b25a8`. Source and evidence checks passed
before reuse; this supplement contains **48 new primary attempts**, not
144 new executions.

| Set / profile | Cells | Original mean | Candidate 24 | Candidate 27 | 27 minus original | 27 minus 24 |
|---|---:|---:|---:|---:|---:|---:|
| Historical 501–504 / rush | 4 | 0.724679487 | 0.828525641 | 0.729006410 | +0.004326923 | −0.099519231 |
| Historical 501–504 / rush_noisy | 4 | 0.690224359 | 0.690224359 | 0.721474359 | +0.031250000 | +0.031250000 |
| Inspected 3000–3019 / rush | 20 | 0.772639166 | 0.780536894 | 0.754039537 | −0.018599630 | −0.026497357 |
| Inspected 3000–3019 / rush_noisy | 20 | 0.683006022 | 0.683006022 | 0.677788219 | −0.005217803 | −0.005217803 |

| Set / profile | 27 wins / ties / losses versus original | 27 wins / ties / losses versus 24 |
|---|---:|---:|
| Historical / rush | 1 / 2 / 1 | 0 / 2 / 2 |
| Historical / rush_noisy | 1 / 3 / 0 | 1 / 3 / 0 |
| Inspected / rush | 4 / 10 / 6 | 1 / 12 / 7 |
| Inspected / rush_noisy | 3 / 14 / 3 | 3 / 14 / 3 |

All 48 candidate-27 attempts are scored, with **zero execution errors**, and
all 48 rovers are alive at base at tick 50. Both earlier policies also return
home alive on every matched cell, so these data show no survival improvement.
Candidate-27 mean policy-call counts are 67.75 and 66.75 on historical rush
and noisy, and 67.10 and 67.75 on the inspected set. These are local public
callback counts, not model tokens or wall-clock latency charges. API cost is
**$0**; no inference was used.

Examples preserve both directions. On rush seed 3017, candidate 27 earns
**7/11**, versus original **6/11** and candidate 24 **4.5/11**. On rush seed
3005 it earns **7.5/10**, versus **9.25/10** for both earlier policies. On
historical noisy seed 503 it earns **6/8**, versus **5/8** for both. All rows,
errors, tool counts, paired differences and survival/home fields are in the
[complete summary](primary/summary.json), with [48 full episodes](primary/episodes/).

The first study called seeds 3000–3019 fresh when it first used them. This
supplement labels them `inspected_controller`, preserving the original set
label separately in reused rows. It does not estimate model performance on
those seeds: no model has run on them. The candidate's earlier development
suite included different scenario factors; this check concerns only the
unchanged plain profiles. No ablation separates its fading, terrain-filter
and guarded-move additions, so the score changes cannot be assigned to one
addition. Neither this supplement nor its retrospective model comparison
changes the canonical reference or existing audit attribution.

## Original model attempts: retrospective comparison

These are the **eight original model attempts**, unchanged. They are separate
from overnight repeats and from the 48 new scripted-controller attempts.

| Profile / seed | Original model | Original reference | Candidate 24 | Candidate 27 |
|---|---:|---:|---:|---:|
| rush / 501 | 0 | 0.833333 | 0.833333 | 0.833333 |
| rush / 502 | 0.769231 | 0.615385 | 0.730769 | 0.557692 |
| rush / 503 | 0.750000 | 0.750000 | 0.750000 | 0.750000 |
| rush / 504 | 0.700000 | 0.700000 | 1.000000 | 0.775000 |
| rush_noisy / 501 | 0.791667 | 0.666667 | 0.666667 | 0.666667 |
| rush_noisy / 502 | 0.634615 | 0.769231 | 0.769231 | 0.769231 |
| rush_noisy / 503 | 0.750000 | 0.625000 | 0.625000 | 0.750000 |
| rush_noisy / 504 | 0 | 0.700000 | 0.700000 | 0.700000 |

Against candidate 27, those attempts have **2 model wins, 2 ties and 4
deficits**. Model means remain 0.554807692 for rush and 0.544070513 for noisy;
candidate-27 means are 0.729006410 and 0.721474359. This is a retrospective
reference substitution, not a new model experiment or a replacement for the
[original comparison](../../lightlag-fixed-seed-comparison.md).

## Boundary, compatibility and verification

Nineteen repository Python files were frozen directly from `bdb77f6` into a
separate temporary source tree before importing the candidate. **Eighteen
files are byte-identical** to the first study's source, including every
simulator and original-reference dependency. Only the Manh controllers module
changed; **all 39 existing top-level class/function definitions have identical
ASTs**, including the candidate-24 inheritance chain and helpers. All 96 reused
baseline rows and their complete episode artifacts were checked against their
published bytes. The first study's eight exact Harbor-reference reproductions
remain its original evidence; they were not counted again as new attempts.

The candidate's actual MRO and helpers were inspected before outcomes. Its
sand labels use delivered battery/odometry/terrain packets, its fading uses
delivered position fixes, and its guarded prefixes use controller estimates
and public rules. It receives only shared `PublicTools` callbacks through
`lightlag.evaluation.run_episode`. `Current.logger` is null; no registry
wrapper, oracle, scenario environment/factors or real-time clock is used.
This is an auditable interface for trusted Python, not a sandbox against
introspection.

The [verification report](verification.json) confirms:

- **48 unique scored primary cases**, zero execution errors, all planned
  cells retained and no unrun cases.
- **3,283 policy/evaluator calls** independently replayed, matching every
  response, result and full trajectory. Fixed mission inputs match both
  earlier policies; policy-dependent heading-error histories are verified
  within each complete trajectory, not required to match another policy.
- All **eight paired comparison groups** recomputed; all **eight historical
  model scores** checked against authoritative evaluator artifacts.
- **Four predetermined policy repetitions** exactly reproduce the entire
  saved episode, including transcript, replay and calls: historical rush 501,
  historical noisy 504, inspected rush 3000 and inspected noisy 3019.
  [Compact paired hashes](representative-reruns.json); no duplicate trajectory
  tree is stored. These four repetitions are verification, not additional
  independent samples or replacement primary attempts.
- Four focused checks pass: the fixed 48-cell/rerun plan, changed-dependency
  rejection, null-score pair handling, and preservation of an execution error
  if a source mismatch also occurs.

Source and input hashes are checked before and after every primary episode.
An unexpected mismatch aborts and retains completed evidence. An execution
error would receive a null score, with no retry or replacement. Existing output
directories are rejected. Scientific JSON passed private-path and token-pattern
checks; no credential files or private agent state were read or copied.

## Provenance and exact commands

The [source/dependency manifest](primary/source-manifest.json) records the full
commits, 19 source hashes, 110 input hashes, preserved-definition hashes,
candidate MRO, and **CPython 3.12.16 / numpy 2.5.4** on Darwin arm64. The
[runner](../../../tools/lightlag_experiments/overnight_reference27.py), its
[exact executed copy](primary/runner.py), and the
[unchanged first-study helper copy](primary/shared-runner.py) are retained.
`primary/protocol.md` is the verbatim published protocol; its relative links
use the original `docs/` location. The runner installs no packages.

Executed from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/lightlag-6974-overnight-analysis/bin/python docs/lightlag-runs/overnight-reference27-study/checks.py
PYTHONDONTWRITEBYTECODE=1 /tmp/lightlag-6974-overnight-analysis/bin/python tools/lightlag_experiments/overnight_reference27.py --source-root /tmp/lightlag-6974-overnight-reference27-source-bdb77f6 --output docs/lightlag-runs/overnight-reference27-study/primary
PYTHONDONTWRITEBYTECODE=1 /tmp/lightlag-6974-overnight-analysis/bin/python docs/lightlag-runs/overnight-reference27-study/verify_artifacts.py --source-root /tmp/lightlag-6974-overnight-reference27-source-bdb77f6 --write-reports
```

For another full reproduction choose a new `--output` directory, preferably
under temporary storage. To rerun the verifier and its four fixed repetitions,
omit `--write-reports`; existing reports will remain unchanged. The verifier's
exact script hash is in its report. The repository must retain the immutable
first-study artifacts and helper, whose hashes are checked before reuse.

The isolated source tree can be recreated in a new directory using only
read-only Git commands:

```python
import hashlib, json, pathlib, subprocess
manifest = json.loads(pathlib.Path("docs/lightlag-runs/overnight-reference27-study/primary/source-manifest.json").read_text())
snapshot = pathlib.Path("/tmp/lightlag-reference27-source-new")
snapshot.mkdir(exist_ok=False)
for relative, expected in manifest["source_sha256"].items():
    data = subprocess.check_output(["git", "show", manifest["source_commit"] + ":" + relative])
    assert hashlib.sha256(data).hexdigest() == expected
    target = snapshot / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
```

The coordinator owns review, integration and shared status/prize updates.
The first study's runner/artifacts, canonical references, simulator/controller
implementations, rules and original model evidence were preserved.
