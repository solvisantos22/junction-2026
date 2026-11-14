# Final Traverse training progress

As of **2026-11-14 21:40:39 UTC** / **2026-11-14 23:40:39 EET**.

Stage: **fit**. Supervisor: **monitoring**.

These are reused validation worlds, not the untouched final check. All three seeds are retained; this does not promote a learned policy over the reference.

| Run | Stage / status | Batch-file mission coverage / target | Latest validated milestone | Score | Home / alive | Invalid | Elapsed | Rough time remaining | Hard cutoff UTC |
|---|---|---:|---:|---:|---|---:|---:|---:|---|
| ppo-17 | fit / running | 7,616 / 8,192 | 2048 | 0.378374 | 32/32 · 32/32 | 0 | 118 min | 9 min | 2026-11-14 22:42:06 UTC |
| ppo-29 | fit / completed | 8,192 / 8,192 | 8192 | 0.375676 | 32/32 · 32/32 | 0 | 118 min | unknown | 2026-11-14 22:42:06 UTC |
| ppo-43 | fit / running | 7,296 / 8,192 | 2048 | 0.385452 | 32/32 · 32/32 | 0 | 118 min | 15 min | 2026-11-14 22:42:06 UTC |
| replay-17 | fit / running | 6,432 / 8,192 | 2048 | 0.377607 | 32/32 · 32/32 | 0 | 118 min | 32 min | 2026-11-14 22:42:06 UTC |
| replay-29 | fit / running | 6,528 / 8,192 | 2048 | 0.366528 | 32/32 · 32/32 | 0 | 118 min | 30 min | 2026-11-14 22:42:06 UTC |
| replay-43 | fit / running | 4,768 / 8,192 | 2048 | 0.364257 | 32/32 · 32/32 | 0 | 118 min | 85 min | 2026-11-14 22:42:06 UTC |

Method means use the highest checkpoint available for **all three seeds at the same training budget**:

| Method | Common milestone | Initial mean | Current mean | Home / alive | Invalid calls |
|---|---:|---:|---:|---|---:|
| ppo | 2,048 | 0.087395 | 0.380123 | 96/96 · 96/96 | 0 |
| replay | 2,048 | 0.087395 | 0.369464 | 96/96 · 96/96 | 0 |

Read-only reused-validation progress. Contiguous batch filenames show artifact coverage, not committed checkpoint state; volume visibility may lag. ETA is a rough linear extrapolation, separate from the hard stage cutoff. No production physics or optimizer audit; no final-world or reference-superiority claim.
