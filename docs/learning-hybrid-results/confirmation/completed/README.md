# Confirmation completed — one candidate advances

All **5376 cases** (21 arms × 256 worlds, 611000–611255) completed at
**15 November 02:43:53 UTC**. The original call and downloaded terminal state
match exactly. The unchanged selection rule advances **`ensemble-all-rho090`**:
the rank ensemble of all six retained policies, with science choices restricted
to at least 90% of the best feasible greedy efficiency. Home remains legal.

Its mean reward is **0.380209**, versus matched greedy **0.375202** and the
frozen beam reference **0.500510**. The paired gain is **0.005007** (0.5007
percentage points), with 95% map-bootstrap interval **[−0.000188, 0.010190]**.
This is selection evidence, **not a confirmed improvement**. Confirmation's
predeclared gate requires a positive mean and safety; the independent final
test requires at least 0.01 gain and an interval wholly above zero.

## All six shortlisted groups

| Group | Mean reward | Gain over greedy | Joint home/alive | Deaths | Decision |
|---|---:|---:|---:|---:|---|
| single-ppo-rho090 | 0.378752 | +0.003550 | 768/768 | 0 | Eligible; lower mean |
| single-ppo-rho075 | 0.382683 | +0.007480 | 767/768 | 1 | Excluded by safety gate |
| ensemble-ppo-rho090 | 0.378938 | +0.003736 | 256/256 | 0 | Eligible; lower mean |
| **ensemble-all-rho090** | **0.380209** | **+0.005007** | **256/256** | **0** | **Selected** |
| blend-ppo-greedy075 | 0.379435 | +0.004233 | 256/256 | 0 | Eligible; lower mean |
| blend-all-greedy050 | 0.383265 | +0.008063 | 255/256 | 1 | Excluded by safety gate |

Single-policy groups average all three training seeds within each world before
averaging worlds or bootstrapping. No best seed, checkpoint substitution or
per-world policy switching is used. The two higher-scoring unsafe candidates
remain in the report; they cannot replace the selected safe group.

All 5376 cases together contain **5372 jointly home and alive**, 5373 home,
5373 alive, **3 deaths**, 3 away endings and zero invalid calls. Home and alive
are separate fields: one dead rover is at home and one living rover is away.
The third death is in an unmodified PPO control. These are retained scientific
outcomes, not infrastructure failures. The selected group and both matched
greedy/reference controls are each 256/256 home and alive.

## Evidence and reproduction

- [All 13 group summaries and exact paired intervals](analysis.json),
  [group CSV](group-summary.csv), [all 21 arm summaries](arm-summary.csv).
- [Complete terminal rows, call IDs and trajectory hashes](state.json).
  SHA256 `ad2411db2aa08ad75f1376fd49b5ef7b250193f73c30f0395eeee268a24627e2`.
- [Independent original-call/source/lineage/cost audit](terminal-audit.json)
  and [independent arithmetic, selection and final-freeze audit](independent-audit.json).
- [Original metadata-download manifest](download-manifest.json) lists paths
  within the private download; it is not a list of files in this directory.
  [Published-file manifest](files.json) covers this directory.

The original app is **`ap-mAROrYr7XrA7sT2t7Z5zMI`**, call
**`fc-01M7EFBZEQXETSYPQH3PCREV4D`**. The prelaunch selection/source/resource
freeze reached main in **`2256f63`**. Every job's saved physics and choice audit,
source, original call and attempt-storage binding verifies. Independent review
recomputes every group mean, map vector, 20,000-resample interval and selection.
This completion audit does not rerun simulation or download the full episode
archives: those remain on Modal volume `junction-learning-hybrid`, with the
exact compressed-file paths/hashes retained in the rows. No completed job was
repeated. All earlier failed development attempts and their control records
remain unchanged.

Run analysis only from the immutable source snapshot, because current main has
newer teammate harness files:

```sh
cd /tmp/junction-hybrid-recovery2-frozen
PYTHONPATH=/tmp/junction-hybrid-recovery2-frozen /tmp/junction-learning-venv/bin/python -m tools.learning_hybrid.experiment analyze --stage-file /tmp/junction-hybrid-confirmation-stage-20261115.json --status /tmp/junction-hybrid-confirmation-terminal-20261115/confirmation/state.json --output NEW_ANALYSIS.json
```

The original terminal metadata was downloaded once to
`/tmp/junction-hybrid-confirmation-terminal-20261115`. Do not repeat that
download or launch. Analysis SHA256:
`ae632872031f0584c8ba3e9ee0308363aa94d5639857e6f439adce98170e331b`.

## Cost and next step

Recorded confirmation running compute is **$2.278476**: workers $2.165140,
coordinator $0.113336. Cumulative hybrid including smoke and earlier attempts
is **$4.136855**; separate closed prior training is **$2.404367**; combined
**$6.541221**. These estimates exclude ancillary, idle and lost unrecorded
work; they are not an invoice or credit balance. The original $75 shared
ceiling and 05:30 UTC cutoff still apply.

[Final selection, controls and operations freeze](../../final/README.md) must
reach main before the one-shot final evaluation on 612000–612255. That stage
retains greedy, beam, all six pure individual policies and the pure all-six
ensemble. No weights, threshold, runtime or scientific source changes follow
confirmation. Final success/failure will be published without further tuning;
keep the current team reference. Greedy-prior training stays closed, and its
629000–629127 maps remain unopened.
