# Isolated dynamic Harbor experiments

The existing Harbor task works, and its first Claude Opus 5.5 run matched the
reference at 1.0. The next experiment tests Manh's delivered time-pressure rules.
This continues the authorized Lightlag development; it does not select final
project rules or replace Kristján's task.

## Approach and alternatives

Generate a self-contained temporary Harbor task from the checked-in package.
Keep the simulator sidecar, evaluator-only finish and separate verifier. Add the
delivered dynamic service and a public-tool-only dynamic reference solution.

Replacing `harbor/lightlag/` would prematurely change the shared submission
candidate and overlap its owner's work. A direct local MCP run would be faster
but would not verify the Harbor lifecycle. A generated separate task gives a
repeatable Harbor test without either problem.

## Scope and data flow

- `tools/lightlag_experiments/prepare.py` builds a new directory outside the
  checkout. It takes a profile (`rush` or `rush_noisy`), seed, delay and scripted
  solution policy (`kf_mpc`, `open_loop` or `leg_and_wait`).
- Start with `rush`, seed 500, delay 3. This seed is preselected, not picked for a
  low model score. Use existing physics, profile horizon 50, noise level 1 and
  bumpiness 0. No controller tuning in this experiment.
- Copy only tracked task files and explicitly required source files. Refresh the
  simulator/service copies from their originals. In the reference solution,
  include only the dynamic controller modules and an empty package initializer;
  never include simulator code, hidden mission settings or an evaluator token.
- Explain deadlines, delayed discoveries and any noisy observations in the
  generated instruction. The model and scripted policies get the same five tools
  and public rules. All other original task settings remain unchanged.
- A manifest records parameters, source commit, source-file hashes and generated
  task-file hashes. No absolute local paths, credentials or environment values.
- Refuse an existing output directory. A malformed task is an error, never a
  scored agent failure. Raw jobs remain outside Git; inspect and sanitize any
  evidence before committing it.

## Verification and interpretation

Test the generated service's actual rules, that the reference imports without
simulator modules, manifest completeness and determinism, and non-overwrite
behavior. Run Harbor lint, then an oracle and no-op in real containers. Compare
oracle results against direct public-tool runs on the same seed/settings.

After a provider key is supplied locally, attempt one model run with the same
model family as the original result and record exact resolved settings, cost,
reward, transcript and replay. Model access is pending, not simulated. The user
reports Claude credits obtained and Gemini applied for; neither a submitted
application nor a placeholder key counts as verified API access.

Only compare runs with the same task rules and seed. A single-seed result is a
wiring/difficulty probe, not a general benchmark gap. If useful, follow with a
delay-0 control and additional predeclared seeds in a later increment. Preserve
the original 1.0 model result and any negative findings.
