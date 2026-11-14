# Lightlag Traverse: answer to the team's readiness questions

An answer from the Traverse owner to [`docs/learning-campaign-results/team-training-readiness.md`](learning-campaign-results/team-training-readiness.md), in its reply template. It states the technical state of the code; the team's choice of final project is not made here.

- **Owner/session and timestamp:** Kristján / Claude Code (gap research chat, worktree `claude-gap-research`). First answer Saturday 14 November about 20:45 Helsinki; updated about 21:30 after Kristján's merge and the last agent runs.
- **Proposed final commit, environment and Harbor task path:** current `main`. Kristján froze Traverse (`TEAM_STATUS.md`) and merged the branch (`0130fa6`, then `d45d3f9`). Every `lightlag_traverse/*.py` file and both Harbor tasks on `main` are byte for byte what was tested below; later commits from the branch add runs, documents and the demo only.
  - rules: the Lightlag Traverse 0.1.0 rules, unchanged;
  - reference: the pilot of commit `1545627` (`lightlag_traverse/pilot.py`: 0.1.0's pilot plus the way-home rule `home_floor`);
  - submission candidate: the three-mission campaign, `harbor/lightlag-traverse-campaign/`, worlds 2027, 2028 and 2029; fallback: the one-mission task `harbor/lightlag-traverse/` on world 2026.
  - It is normal Traverse and a campaign of it, not MAX and not a combined version.
- **Rules still changing:** none. The sunrise-to-sunset day was tried and dropped.
- **What changed in `lightlag_traverse/` compared with the version earlier RL studies pinned:** `environment.py`, `terrain.py`, `surface.py`, `planning.py`, `play.py`, `sandbox*.py` and `oneshot.py` are byte for byte unchanged since `f90cb6b`, so the simulator, the map generation and the planner are the same. Changed: `pilot.py` (`home_floor`, `fly_campaign`), `server.py` (can serve a campaign), `make_task.py` (builds both tasks); new: `campaign.py`. On merged `main`, `tests/lightlag_rl`'s retained-smoke test fails on its source pins for exactly this reason: re-pin against `main`. Nothing a single-mission training adapter reads behaves differently.
- **Integration notes, none blocking:**
  - The way-home rule gives identical scores to the 0.1.0 pilot on development worlds 1 to 24, fresh worlds 1000 to 1011 and world 2026; it acts only when the battery is low on the way home (it does on campaign site 1).
  - In the campaign every mission is an unchanged `TraverseEnvironment`. The next begins at once, at its tick 0, when the last tick of one passes. Packets, acknowledgements, `map()` and `advance` replies gain a `mission` field, and `advance` gains `campaign_complete`. A single-mission adapter applies to each mission as it is.
  - The campaign's score is the value credited in all missions over all the value there was, not the mean of the missions' scores; the team's `grade.py` reads it unchanged.
- **Checks passed:**
  - 75 Traverse tests and 71 viewer tests; both tasks fresh (`python3 -m lightlag_traverse.make_task --all --check`).
  - Through Harbor 0.25.0, one mission: reference 0.564655, do nothing 0, stopped at tick 105 0.073. Campaign: reference 0.476257 (0.459, 0.508, 0.460, home every time), do nothing 0, stopped after the first mission 0.149.
  - Seven Claude agent runs on the campaign, all below the reference, the closest by 0.18: Sonnet 5.5 0.293 and 0.213, Opus 5.5 0.267, 0.247, 0.244 and 0.120, Haiku 5.5 0.000 ([write-up](lightlag-traverse-campaign.md)).
  - The Modal farm reproduces the campaign reference mission for mission; every saved Claude program scores below it on the same three worlds.
  - The campaign's worlds do not flatter the reference: its 0.476 there sits at the 19th percentile of three-world blocks from the farm's 300 fresh worlds (mean 0.502).
  - Manh's `lightlag_traverse_max` tests (13) pass against the merged code.
- **Remaining required checks:** none for the task. For RL: re-pin, and verify the training adapter against `main` before larger runs.
- **World ranges:**
  - In use, so do not train, select or check on them: 1–99 development; 2026 the one-mission task; 2027–2029 the campaign (never train or select on these); 1000–1199 the owner's fresh checks; 99991 the one-request example; 100–499 farm search and selection; 600–899 farm comparisons; 1200 and above appear in the integrity review's disposable exploit probes, which train and select nothing.
  - Proposed for RL, untouched as far as this owner knows: training 10000–19999, selection 20000–20999, final check 21000–21999.
- **Ready for a bounded compatibility pilot:** yes.
- **Team or user approval still needed:** the team's final choice of project.
