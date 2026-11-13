---
name: junction-team-workflow
description: Use when starting, changing, or handing off work in the Junction 2026 repository, including concurrent work by teammates, chats, agents, or worktrees.
---

# Junction team workflow

Three teammates and multiple chats share this repository. Publish small, working increments to `main` throughout each task so others can see and use the latest work. The user has authorized these routine commits and pushes; do not ask again for each increment.

## Start and claim

1. Read the repository-root `AGENTS.md` and `TEAM_STATUS.md` afresh for each task. Inspect the working tree, fetch `origin`, and review current `origin/main` before editing.
2. Choose a narrow task and file scope that does not overlap an active claim. Record your owner/chat, scope and status in `TEAM_STATUS.md`; commit and push the claim before substantial implementation.
3. Preserve other people's uncommitted changes. Coordinate overlapping ownership before editing. Use a separate worktree when simultaneous chats would otherwise share files or Git state.

## Push throughout the task

- After each coherent increment passes the checks appropriate to it, commit and push it to `main` promptly, before beginning the next independent increment. Do not accumulate the whole task locally or wait until the session ends.
- Before every push, fetch and integrate the latest `origin/main`. Prefer fast-forward updates; rebase only your own unpublished commits or merge as appropriate. Integrate finished work from temporary branches/worktrees into `main` regularly.
- Stage only your own intended changes. Never include credentials, private runtime logs, unrelated edits or known-broken checkpoints. Push completed slices, not arbitrary timer snapshots.
- If a teammate pushes first, fetch, reconcile, rerun affected checks and retry. Never force-push `main` or discard teammates' work. If ownership or a conflict cannot be resolved confidently, report that blocker and preserve the work.

## Finish or hand off

Update `TEAM_STATUS.md`, push remaining verified work, and confirm it reached `origin/main`. Report the commit and any blocker or unfinished scope. Claims prevent duplicate effort; frequent pushes alone do not.
