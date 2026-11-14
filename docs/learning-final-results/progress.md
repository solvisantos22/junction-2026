# Final Traverse training progress

As of **2026-11-14 20:22:18 UTC** / **2026-11-14 22:22:18 EET**.

Stage: **fit**. Supervisor: **monitoring**.

These are reused validation worlds, not the untouched final check. All three seeds are retained; this does not promote a learned policy over the reference.

| Run | Stage / status | Batch-file mission coverage / target | Latest validated milestone | Score | Home / alive | Invalid | Elapsed | Rough time remaining | Hard cutoff UTC |
|---|---|---:|---:|---:|---|---:|---:|---:|---|
| ppo-17 | fit / running | 2,560 / 8,192 | 2048 | 0.378374 | 32/32 · 32/32 | 0 | 40 min | 88 min | 2026-11-14 22:42:06 UTC |
| ppo-29 | fit / running | 2,848 / 8,192 | 2048 | 0.376544 | 32/32 · 32/32 | 0 | 40 min | 75 min | 2026-11-14 22:42:06 UTC |
| ppo-43 | fit / running | 2,336 / 8,192 | 2048 | 0.385452 | 32/32 · 32/32 | 0 | 40 min | 100 min | 2026-11-14 22:42:06 UTC |
| replay-17 | fit / running | 2,784 / 8,192 | 2048 | 0.377607 | 32/32 · 32/32 | 0 | 40 min | 78 min | 2026-11-14 22:42:06 UTC |
| replay-29 | fit / running | 2,912 / 8,192 | 2048 | 0.366528 | 32/32 · 32/32 | 0 | 40 min | 72 min | 2026-11-14 22:42:06 UTC |
| replay-43 | fit / running | 2,016 / 8,192 | 512 | 0.298269 | 32/32 · 32/32 | 0 | 40 min | 122 min | 2026-11-14 22:42:06 UTC |

Method means use the highest checkpoint available for **all three seeds at the same training budget**:

| Method | Common milestone | Initial mean | Current mean | Home / alive | Invalid calls |
|---|---:|---:|---:|---|---:|
| ppo | 2,048 | 0.087395 | 0.380123 | 96/96 · 96/96 | 0 |
| replay | 512 | 0.087395 | 0.276713 | 96/96 · 96/96 | 0 |

Read-only reused-validation progress. Contiguous batch filenames show artifact coverage, not committed checkpoint state; volume visibility may lag. ETA is a rough linear extrapolation, separate from the hard stage cutoff. No production physics or optimizer audit; no final-world or reference-superiority claim.
