# Homepage Preview Implementation Plan

> Initially local in `codex/lightlag-home-preview`. After viewing it, Sölvi approved immediate publication on 15 November 2026. The original local-only restriction is superseded for this homepage.

**Goal:** A working local mission-control homepage using real Traverse terrain.

**Architecture:** Standalone candidate HTML/CSS/JS in `tools/traverse_farm/home_preview/`, with a standard-library localhost server. Existing production code stays untouched. Cache featured replays locally for review.

**Tech Stack:** Existing plain HTML, CSS and JavaScript. Python localhost server. Bun/Playwright for browser verification. No application framework or runtime dependency added.

- [x] Verify and install TasteSkill, Impeccable, Hallmark, UI/UX Pro Max and the original Unslop-UI scanner into the user's skill directory. Pin source revisions.
- [x] Fetch main, make an isolated worktree and publish only a coordination claim. Run the rollout-farm baseline.
- [x] Capture the existing homepage and a real cached world 2027 terrain view. Save local font assets and provenance.
- [x] Build the candidate using visible labels, one primary replay action, flat world/controller lists and mobile stacking. Keep original five destination paths and numeric bounds.
- [x] Start localhost preview. Inspect 1440, 1024, 768, 390 and 320 px widths, test interaction and run source audits. Fix material findings together.
- [x] Independent finish review: no material fixes; document actual design and checks; open local URL for user review.
- [x] Sölvi approved the preview for immediate publication. Integrate exact assets into the existing FastAPI app, verify routes and preserve replay/simulation.
- [x] Push verified homepage; deployment to existing `kristjansolvi03` Modal workspace observed at 10:25:42 Helsinki. Public assets match approved bytes; desktop/mobile browser, form and cached replay checks passed. [Evidence](../../homepage-release/README.md).
