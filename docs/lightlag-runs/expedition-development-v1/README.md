# Expedition development study v1

This is a free scripted development comparison, not a Claude result or held-out validation.
The frozen bounded reference improves on the no-inspection and leader-inspection controls
in aggregate. It loses to no-inspection on map 2, and its small advantage over entropy-first
inspection does not establish that sophisticated information allocation is essential.

Command:

```sh
python3 -m lightlag_expedition.study --output docs/lightlag-runs/expedition-development-v1
```

The study completed all 1,536 episodes in 133.01 seconds. No outcomes were removed or retried.
All episodes survived and returned to base. Source hashes were unchanged during execution.

| Policy | Weighted raw science | Normalized score | Mean inspections |
|---|---:|---:|---:|
| Reference | 9.063320 | 0.453166 | 1.560 |
| Entropy inspection | 8.951860 | 0.447593 | 1.500 |
| Public-quality reference | 8.500563 | 0.425028 | 0 |
| No inspection | 8.245000 | 0.412250 | 0 |
| Leader inspection | 7.974370 | 0.398719 | 0.295 |
| Value blind | 7.495000 | 0.374750 | 0 |

The reference gains 0.040916 normalized score over no-inspection, 0.054448 over leader
inspection, and 0.005573 over entropy inspection. It starts with an inspection in every
world: 75% of map probability mass starts with a challenger and 25% with the current leader.
Here **leader means the region of the first target in the current best planned sequence**,
the same definition used by the leader policy. It does not mean the region with the highest
prior or highest single-target value.

| Map / physics seed | Reference | No inspection | Leader | Entropy | Value blind | Public quality |
|---|---:|---:|---:|---:|---:|---:|
| 0 / 100 | 0.464520 | 0.388000 | 0.388000 | 0.460120 | 0.388000 | 0.403700 |
| 1 / 101 | 0.448000 | 0.386000 | 0.386000 | 0.448000 | 0.296000 | 0.392725 |
| 2 / 102 | 0.443104 | 0.460000 | 0.405874 | 0.436170 | 0.400000 | 0.464375 |
| 3 / 103 | 0.457040 | 0.415000 | 0.415000 | 0.446082 | 0.415000 | 0.439313 |

Reference versus no-inspection wins on 63.735625%, ties on 12.98%, and loses on 23.284375%
of the weighted worlds. Its largest individual loss is 0.415 normalized score, retained as
`m3-q110s001-reference`. Reference versus entropy wins on 29.476625%, ties on 50%, and loses
on 20.523375%. These are discrete probability masses, not confidence intervals.

The public-quality reference performs worse than the hidden reference in aggregate. It
uses the same limited route heuristic and is **not an optimal bound**. Inspection waiting
also changes timing and opportunities to react to discoveries. This result cannot isolate
the causal value of information from the policy's timing and planning limitations.

## Design and limits

- Four public mission seeds, 0–3, receive equal weight. Each uses physics seed `100 + map`.
- All eight regional quality combinations and all eight conditional noisy-signal
  combinations are enumerated. Each world receives the product of the published regional
  priors and conditional signal likelihoods. There are 64 worlds per map and six policies.
- The same quality, signals and physics seed are paired across policies. Common physics
  seeds do not force different action trajectories to experience identical observations.
- Weights exactly integrate the discrete science variables conditional on these maps and
  deterministic physics random streams. They do not integrate continuous noise generally,
  justify performance on unseen maps, or establish a strong-model difficulty gap.
- Reference motion comes from the frozen public-only KF/MPC. Planning enumerates at most
  four announced targets and up to two inspections. Exact sample-quality revelations are
  used when delivered; future sample-information branches are not globally enumerated.
- The policy receives only five recorded public methods. The Python facade is an auditable
  boundary, not a sandbox for arbitrary adversarial Python.

## Artifacts

- `config.json`: full worlds, public-prior weights, paired seeds, policies and active source hashes.
- `rows.jsonl`: every compact episode outcome, including negative comparisons.
- `episodes.jsonl.gz`: every full public-tool transcript, replay, result and decision log.
- `summary.json`: weighted per-map and aggregate results, including inspection choices.
- `sha256.json`: hashes of the other artifact files.

The source manifest covers the environment, mission generator, constants, controller,
study runner and frozen physics/controller modules. Package `__init__.py` import wiring is
not included in that manifest. Full source and artifact reconstruction should accompany any
later claim; no policy changes should be evaluated by overwriting this directory.
