# Repository size audit and small judge checkout

15 November 2026. Measured at `90264f57` (which includes the first real narrated film in `19076505`). This is an inventory and a verified download alternative, **not authorization to remove evidence**. No tracked file was deleted, no history was rewritten, and no training or inference was launched.

## Where the size is

The current tree contains **14,354 files, 1,743.36 MiB (1.70 GiB)** of file contents. About 97.5% is under `docs/`. The first snapshot at `69e60684` was 1,711.21 MiB; the newly published narrated movie explains nearly all of the increase. This counts current file bytes, not compressed clone-transfer bytes or Docker images.

| Directory | Current MiB | What it contains |
|---|---:|---|
| `docs/learning-final-results` | 280.02 | Final learning checkpoints, validation/evaluation records and source/weight freezes |
| `docs/lightlag-rl-feasible-results` | 239.98 | Earlier feasibility-study evidence |
| `docs/planner-lab-results` | 222.06 | Planner training/evaluation data, fitted models and replays |
| `docs/lightlag-runs` | 218.45 | Actual model runs and earlier environment experiments |
| `docs/learning-hybrid-results` | 191.34 | Hybrid development/confirmation/final evidence and frozen operations records |
| `docs/manh-demo` | 128.51 | Earlier cut, current cut, narrator-free film and first real narration output |
| `docs/learning-campaign-results` | 102.90 | Earlier learning campaign/pilot records |
| `docs/learned-portfolio-results` | 85.84 | Learned-planner dataset, models and evaluation |

Ignored local files in this worktree total only about 2.8 MiB. Clearing Python caches would not solve the repository size. The shared local Git database also holds historical versions and other worktree refs; its size is not an exact public clone-transfer measurement.

## Cleanup candidates and boundaries

| Candidate | MiB | Condition before removing from the current tree |
|---|---:|---|
| `docs/manh-demo/manh_demo_1.mp4` | 30.65 | Superseded cut, but intentionally retained and still linked. Coordinate with its media owner and preserve a durable archive link. |
| Five older standalone viewer exports below | 16.75 combined | Rebuildable outputs; documentation and tests refer to committed copies. Update those references/tests or archive the complete historical demo. |
| `docs/lightlag-demo-media/first-cut-v1/lightlag-selected-case.webm` | 1.41 | Earlier silent cut; archive together with its verification/hash record. |

The five viewers are `viewer/biomes-demo.html`, `viewer/mars-demo.html`, `viewer/ghosts-demo.html`, `viewer/ghosts-rush-501-control.html`, and `viewer/ghosts-rush-501.html`.

These obvious older presentation outputs total only **48.81 MiB**, about 2.8% of the current tree. The bulk is experiment evidence. Earlier study bundles could be moved to a durable, publicly accessible artifact archive after their links, checksums and reproduction instructions are migrated; they are not disposable caches. Keep completed and failed attempts together. Preserve all protected source/weight freezes and the active narration kit, current narrated outputs and fallback film.

The largest single files are immutable operations freezes: final hybrid `ops-freeze.json` (59.58 MiB), confirmation `ops-freeze.json` (45.14 MiB) and recovery2 `freeze.json` (24.86 MiB). Their size alone is not a reason to alter them. Some freeze/checkpoint paths contain identical Git blobs: Git already shares their object storage, so deleting duplicate paths mainly changes checkout size.

A normal deletion commit leaves historical versions reachable. It therefore does not remove the old downloads from a full-history clone. Do not rewrite shared history during the submission push. A shallow clone alone still downloads the large current tree.

## Verified small checkout for judging

**Only `harbor/lightlag-traverse-campaign/` is needed for the frozen task's oracle/nop execution.** Its 33 files total **207,406 bytes (202.54 KiB)**. Docker contexts, the vendored simulator, the oracle solution and verifier are all inside that directory. Training archives, the viewer and root Python packages are not runtime dependencies of this exported task.

Use a fresh destination. This fetches only the current branch's metadata and required file contents, then selects the campaign task. Cone mode also includes the small top-level files, including the README:

```sh
git clone --depth 1 --filter=blob:none --no-checkout --single-branch --branch main https://github.com/solvisantos22/junction-2026.git lightlag-judge
git -C lightlag-judge sparse-checkout set --cone harbor/lightlag-traverse-campaign
git -C lightlag-judge checkout main

harbor run -p lightlag-judge/harbor/lightlag-traverse-campaign -a oracle
harbor run -p lightlag-judge/harbor/lightlag-traverse-campaign -a nop
```

This is supported by Git's [partial clone filter](https://git-scm.com/docs/git-clone) and [sparse checkout](https://git-scm.com/docs/git-sparse-checkout) features. A regular full clone followed by sparse checkout would already have downloaded the large objects.

**What was actually verified:** a new clone from public GitHub at `90264f57`, filtered before checkout. The exact task-only selection contained 33 files, every one byte-identical to the frozen task. Switching that clone to the recommended cone selection yielded **44 files / 567,338 bytes (554.04 KiB)**; every checked-out file matched its committed blob. The cone clone used **697.10 KiB of object packs** and approximately **3.1 MiB of Git metadata on local disk**. These are measured local sizes, not a network-byte trace. Root and `harbor/` ancillary files explain the difference from the task-only count.

**Execution boundary:** this audit did not run Docker or Harbor. The public-README reference/nop scores remain the previously recorded 0.476257 and 0.000, not new results from this clone. Judges still need Harbor 0.25.0, Docker/Compose and network access for container images and dependencies; those downloads are additional. This small checkout runs the exported task; regenerating tasks, running the full repository test suite or viewing archived experiments requires more paths.

## Decision and handoff

Use the small checkout for the remaining clean-clone execution check and judge-facing instructions. Keep the public evidence where existing submission links can reach it. After submission, decide which whole historical bundles belong in an artifact archive, verify their hashes and accessibility, and then update references before removing current-tree copies. No cleanup or Git garbage collection was performed by this audit.
