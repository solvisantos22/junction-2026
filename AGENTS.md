# Junction team workflow

Three teammates work concurrently. Keep `main` current with frequent, small, verified pushes so everyone sees progress promptly.

These instructions apply to every chat, agent and worktree working on this repository. At the start of each new task, reread this file and `TEAM_STATUS.md`; do not rely on an older chat's remembered state.

**Required skill:** Read and follow [junction-team-workflow](.agents/skills/junction-team-workflow/SKILL.md) for task claims, syncing, frequent verified pushes to `main`, and handoffs. If it is not listed in your skill picker, read that file directly. This repository file is the shared workflow for all teammates and chats.

## Current hackathon scope

- The team is provisionally committed to AfterQuery. Project ideas remain provisional until the team chooses one.
- Brainstorm before implementing the actual challenge project. Administrative tooling and repository coordination are already authorized.
- Keep travel and logistics out of this session.

## Held-out evaluation worlds (Traverse MAX map)

Decided by Manh, Saturday 14 November. Every method on the Traverse MAX map is tested on the same six worlds, so results stay comparable:

- **Evaluation worlds:** fair 500, 510, 520 (Manh's best scripted player, `manh_max`, scores about 0.5) and superhard 505, 509, 515 (about 0.1–0.2). Report a method's mean on each group of three beside `manh_max` and the reference pilot.
- **Never train, tune or select on them**, on either map: a seed makes the same ground on both. Keep off the whole pool they came from, 500–523. Kristján's submission worlds 2026–2029 and the example world 99991 stay reserved as before. `lightlag_traverse_max.heldout.check_training_seeds(seeds)` raises an error if a training range touches any reserved world.
- **The page:** open `viewer/traverse-evaluation-max.html` (one file, keys 1–6 switch world). Rebuild it with `python3 viewer/build_traverse_max.py --evaluation`. Kristján's pages (`traverse-demo.html`, `traverse-campaign.html`) stay the normal-map submission demo and are unchanged.
- **Harbor tasks** (Kristján's campaign task with the MAX map behind it, approved by him): `harbor/lightlag-traverse-max-fair/` (500, 510, 520) and `harbor/lightlag-traverse-max-superhard/` (505, 509, 515), three missions each, scored together. Regenerate with `python3 -m lightlag_traverse_max.make_task`; never edit the task folders by hand.
- The list lives in `lightlag_traverse_max/heldout.py`; the frozen model baseline on these worlds is in `docs/lightlag-runs/max-baseline/`. Details: [docs/lightlag-traverse-max.md](docs/lightlag-traverse-max.md#held-out-evaluation-worlds).

## Lightweight prize evidence

After a meaningful delivered increment, add or extend one entry in [docs/prize-evidence.md](docs/prize-evidence.md) when Codex or a relevant sponsor tool materially contributed. Record the actual tool/person, task or prompt summary, contribution, human decisions, verification and commit/artifact link. Bookkeeping-only edits need no entry. Keep attribution accurate across teammates and tools; do not invent model versions, time savings, usage or results, and do not copy credentials or private conversations into the repository.
