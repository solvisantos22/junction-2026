# Bounded adaptation of the saved Opus autopilot

Frozen before the first API request or any fresh-check case. This continues the
user-approved [transfer protocol](../rule-transfer.md), after the retained free
screen found 23 turning-cost deaths and three rejected relay calls. It asks
whether a strong model can repair its existing program with the full new rules
and useful practice feedback. This is a custom two-response coding diagnostic,
not a Harbor/OpenCode agent benchmark or a general model-capability claim.

## Fixed resources and information

- Model: `claude-opus-5-5`, adaptive thinking, medium effort, standard Messages
  API; at most two generation requests, no automatic retries, 16,000 maximum
  output tokens per response including thinking. No prompt caching configured.
- Total usage guard: **$1.00**. Before each generation, count the full input
  including tools and conversation. Reserve `(1.1 * counted_input + 1024) *
  $4 / 1e6 + 16000 * $20 / 1e6`, plus actual earlier request cost. Stop before
  launching if this exceeds $1.00. Token counts are estimates, so this is a
  conservative launch guard, not a provider billing limit. Rates and free token
  counting checked against [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)
  and [token-counting documentation](https://platform.claude.com/docs/en/build-with-claude/token-counting).
- The user's prior authorization covers this continuation. Historical possibly
  shared usage was $13.882161 against the earlier $15.70 allowance; this is not a
  live account balance. Do not include Kristján's separately approved runs in
  that key's ledger without evidence that the accounts coincide.
- Give the model the complete public rules, the five public tool interfaces,
  its full original program, per-kind free-screen summaries and public failure
  examples. No simulator source, reference code, hidden state/change parameters
  or fresh-check instance is supplied. Conservative budgeting is allowed;
  explicitly naming a change is not required for scoring.
- Original policy SHA-256:
  `288279ff7a4fcc545df26526b4bb82fec33808a829494a6b356da8754831c6fe`.
- Both model policies use the same pinned Python 3.12 + NumPy 2.3.4 container:
  `sha256:ceef33c56e54d804e711f6fe8b802e3c07744763e3141f63034498dd78feff24`.
  The Dockerfile is retained. Existing container isolation and runner limits
  remain in force; infrastructure/protection-limit interruptions are reported
  separately from mission failures. Simulation time pauses during computation.

## Adapt once, then freeze

1. First response calls `evaluate_policy` with a full replacement Python file or
   exact literal replacements applied to the **original** file. There is no
   small-patch restriction; full rewrites are allowed. Compile without executing
   on the host. A malformed candidate returns an error as the one practice
   feedback opportunity; it does not trigger another paid request beyond step 2.
2. A valid candidate runs on fixed, already-used seeds **3200–3203**, each with
   `none`, `ground`, `turning`, `link`, `relay`: 20 local episodes. Retain every
   result and full transcript/replay. Return outcome/safety/error summaries and
   public-tool feedback, never privileged evaluator trajectories. Only one
   practice evaluation is allowed by this budgeted diagnostic.
3. Second response calls `submit_policy` with the complete final file or literal
   replacements again applied to the **original**, not the practice candidate.
   Freeze the final source, source/protocol/prompt hashes, image, usage and API
   request IDs. No manual repair or candidate selection after submission.
4. Truncated responses, provider/count failures, an unaffordable second request,
   unexpected tool sequence or invalid final source leave the experiment
   **incomplete**, not a model failure. No fallback to the first candidate for a
   confirmatory check. Provider errors with unknown usage stop further spending.
   Raw provider thinking/signatures remain in private runtime outside the repo;
   retain public tool inputs, generated code, feedback and usage evidence only.

## Reserved fresh check: 52000–52039

These 40 seeds are reserved here before opening any case. A completed final
policy is hashed and frozen before constructing the first fresh environment.
Run the original saved policy, final adapted policy and Prepared reference on
all 40 seeds for each of the five conditions: **600 local episodes, no model
calls**. Same `rush_noisy`, delay 3, horizon 50, noise 1 as the free screen.
One fresh process per policy episode; no cross-episode memory or tuning.

Apply the existing retirement screen to adapted versus Prepared: all episodes
for those two policies execute normally with zero invalid calls; adapted mean
reward across the 160 changed cases is at least Prepared minus .05, each kind at
least Prepared minus .10; zero changed-case deaths; at least 154/160 alive/home,
at least 36/40 per kind. Original-policy failures are reported separately and do
not veto the adapted policy's gate. Score is raw reward divided by available
target value, not by an optimum. Reused numeric seeds across kinds are correlated;
these are descriptive engineering thresholds, not independent-trial inference.

Retain all cases, independently reconstruct every public call and grade, verify
hashes and report no-change behavior separately (ordinary DynamicEnvironment,
not a same-contract sham). If the gate passes, retire this configuration for
further spending. If it fails, identify whether the residual is a mission error,
coding error or resource/harness limit; it cannot by itself establish a frontier
agent gap. Further full-agent confirmation requires a separate decision and
budget. No environment expansion or canonical-task promotion in this experiment.

Kristján's four newly published rule-change pilots (`afbb89f`) are contextual
evidence, not additional adaptation training or check cases. This protocol does
not overwrite or reclassify those experiments. Seeds 3300–3302 and 3327 remain
used; the reserved range above does not overlap them.
