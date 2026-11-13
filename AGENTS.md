# Junction team workflow

Three teammates work concurrently. Keep `main` current with frequent, small, verified pushes so everyone sees progress promptly.

These instructions apply to every chat, agent and worktree working on this repository. At the start of each new task, reread this file and `TEAM_STATUS.md`; do not rely on an older chat's remembered state. Use `origin/main` and the shared status file to coordinate across chats.

## Before starting work

- Read `TEAM_STATUS.md`, inspect `git status`, fetch `origin`, and review recent changes on `origin/main`.
- Choose a specific task and file scope that does not overlap another active claim. Record the claim in `TEAM_STATUS.md` and push that small coordination update before substantial implementation.
- If work overlaps, resolve ownership or split the task before proceeding. Do not assume frequent pushes alone prevent duplicate work.
- Preserve existing uncommitted changes and identify their owner before touching them.

## While working

- Keep changes focused. Commit and push each coherent, verified increment to `main` promptly; do not accumulate a large private branch or wait until the end of the session.
- Before pushing, fetch again and integrate current `origin/main`. Use a fast-forward pull when possible. Rebase only your own unshared commits, or merge when appropriate; preserve teammates' published history.
- If a push is rejected because someone pushed first, fetch, reconcile their changes, rerun affected checks, then retry. Never force-push `main`.
- Run checks appropriate to the change. Share working increments; do not push broken intermediate code just to satisfy a timer.
- Update `TEAM_STATUS.md` when scope changes, work is ready for others, or a task is complete. Leave clear next steps when handing off.
- Stage only your own intended changes. Do not commit credentials, private runtime logs or unrelated edits.

Use short-lived worktrees or branches when useful, but integrate completed increments into `main` regularly. The user's preference is continuous team visibility, not long-lived isolated work.

## Current hackathon scope

- The team is provisionally committed to AfterQuery. Project ideas remain provisional until the team chooses one.
- Brainstorm before implementing the actual challenge project. Administrative tooling and repository coordination are already authorized.
- Keep travel and logistics out of this session.
