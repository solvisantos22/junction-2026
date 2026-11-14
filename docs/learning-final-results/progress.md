# Final Traverse training progress

As of **2026-11-14 22:20:39 UTC** / **2026-11-15 00:20:39 EET**.

Stage: **fit**. Supervisor: **monitoring**.

These are reused validation worlds, not the untouched final check. All three seeds are retained; this does not promote a learned policy over the reference.

| Run | Stage / status | Batch-file mission coverage / target | Latest validated milestone | Score | Home / alive | Invalid | Elapsed | Rough time remaining | Hard cutoff UTC |
|---|---|---:|---:|---:|---|---:|---:|---:|---|
| ppo-17 | fit / completed | 8,192 / 8,192 | 8192 | 0.362394 | 32/32 · 32/32 | 0 | 127 min | unknown | 2026-11-14 22:42:06 UTC |
| ppo-29 | fit / completed | 8,192 / 8,192 | 8192 | 0.375676 | 32/32 · 32/32 | 0 | 118 min | unknown | 2026-11-14 22:42:06 UTC |
| ppo-43 | fit / completed | 8,192 / 8,192 | 8192 | 0.399862 | 32/32 · 32/32 | 0 | 131 min | unknown | 2026-11-14 22:42:06 UTC |
| replay-17 | fit / completed | 8,192 / 8,192 | 8192 | 0.364181 | 32/32 · 32/32 | 0 | 155 min | unknown | 2026-11-14 22:42:06 UTC |
| replay-29 | fit / completed | 8,192 / 8,192 | 8192 | 0.355892 | 32/32 · 32/32 | 0 | 153 min | unknown | 2026-11-14 22:42:06 UTC |
| replay-43 | fit / running | 6,144 / 8,192 | 2048 | 0.364257 | 32/32 · 32/32 | 0 | 158 min | 53 min | 2026-11-14 22:42:06 UTC |

Method means use the highest checkpoint available for **all three seeds at the same training budget**:

| Method | Common milestone | Initial mean | Current mean | Home / alive | Invalid calls |
|---|---:|---:|---:|---|---:|
| ppo | 8,192 | 0.087395 | 0.379311 | 96/96 · 96/96 | 0 |
| replay | 2,048 | 0.087395 | 0.369464 | 96/96 · 96/96 | 0 |

Read-only reused-validation progress. Contiguous batch filenames show artifact coverage, not committed checkpoint state; volume visibility may lag. ETA is a rough linear extrapolation, separate from the hard stage cutoff. No production physics or optimizer audit; no final-world or reference-superiority claim.
