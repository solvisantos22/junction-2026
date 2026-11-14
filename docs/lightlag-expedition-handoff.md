# Expedition handoff and next decision

The expedition is a separate experimental package. Nothing here promotes it to
the canonical Harbor task or changes the team's provisional project choice.
The [experiment page](lightlag-expedition-experiment.md) and
[frozen pilot ledger](lightlag-runs/expedition-claude-pilot-v1/summary.json) contain
results, exceptions, costs and limitations. All observed episodes become
development evidence for any follow-up; reuse is not fresh validation.

## What the completed model runs teach

Opus scores .55 hidden and .5575 public on mission A; both protected controls
score .46 in either condition. Both model runs finish alive at base. This is
model success. It neither establishes global optimality nor a difficulty gap.

On mission B with disclosed qualities, Opus scores .29 against .31 for both
controls; all finish home alive. The exact gap is one omitted poor target worth
.4 raw science. Two failed sample attempts consume six energy, and the model
finishes with .65 battery. This is a small physical-control/resource shortfall,
not evidence of failed information selection. B's all-on-time realized science
upper total is only 7.2; the model collects 5.8 and the reference 6.2. A .29 score
against the fixed all-rich denominator does not mean it collected only 29% of
the value available in that world.

The fourth planned session, B hidden, is unrun: reported spend $1.5588192 crossed
the predeclared $1.50 new-launch guard. No attempted session was censored or
replaced. One complete hidden/public pair cannot establish a causal treatment
effect or reliable model gap. The three observed scores favor the model overall.

The hidden A run uses direct MCP calls, without scripting. It puts useful movement,
sampling and two inspections in its opening batch. It obtains exact evidence
from one physical sample and imperfect evidence about both other regions while
moving. It then avoids the poor region and collects a valuable discovery.
A redundant sample fails, but the final score still beats the references.

The reference waits for inspection results before driving and does not forecast
future discoveries or information obtained by sampling. Repair those limitations
before claiming that a task is difficult for a strong model. Its four-target
planning horizon and worse disclosed-quality results already limit the claim.
Preserve the frozen reference and pilot; develop a separate revised version.

## Preferred next structural experiment

Increase to **six science regions while keeping two remote inspections**. Keep
physical sampling informative, imperfect inspection likelihoods public, scripting
allowed and the physical clock/energy rules explicit. The intended difference is
that an opening sample plus two inspections leaves several alternatives without
new evidence; the agent must decide which uncertainty matters to its itinerary.

This is a proposal, not an implemented or measured improvement. More regions or
a smaller score alone do not establish difficulty. Additional regions must offer
feasible competing routes, with observations changing later commitments and with
publicly understandable resource tradeoffs. Avoid adding areas that a competent
policy would never consider.

Before another paid pilot:

1. Add a separate reference that can overlap inspections with useful travel and
   account for sample revelations. Retain inspect-first and no-inspection controls.
2. Choose a small six-region generator and publish its geometry, priors, shared
   quality effects and budget. Keep the existing simulator physics fixed. Specify
   the new all-rich denominator; do not compare its lower normalized scores with
   the old denominator as if that were evidence of a gap.
3. Run a predeclared free development comparison against fixed-two, highest-entropy
   and no-inspection policies. Check that competing unresolved routes are feasible,
   the preferred inspection changes with route value and geometry, and adaptive
   selection improves beyond simply observing the two most uncertain regions.
4. If those differences are negligible, stop adding regions and revise the
   information structure. If they matter and a public-only reference is competent,
   freeze new maps and evaluate the same strong model with all attempts retained.

Manh's weak-GPS/compass work is a useful parallel direction for sensor fusion.
It tests combining noisy observations, not directly the user's preferred choice
of which uncertainty to investigate. Do not silently substitute passive fusion
for the active-information objective or merge both changes in one experiment.

## Reuse and coordination

- Package and commands: [lightlag_expedition/README.md](../lightlag_expedition/README.md).
- Exact challenger closure: 672 branches and 54 nearby parameter cases, no paid calls.
- Free expedition evidence: 1,536 episodes and 116,456 reconstructed public calls;
  all replay/score checks pass, all policies survive and return home.
- Harbor preflight: live container isolation, protected grader, real public-MCP
  oracle and no-op; cached-preparer provenance caveat retained explicitly.
- Model evidence: frozen source/task hashes, seed commitments/reveals, exact public
  transcripts, protected replays/grades and reported usage. Raw provider text and
  private agent state stay outside the repository.
- Spending: use the final ledger, not an old credit estimate. Historical remaining
  credits are not a verified live balance. No further paid experiment is started
  by this handoff.

Claim the next implementation in `TEAM_STATUS.md` before editing. Preserve the
canonical task, teammate controllers/viewers and all frozen experiments unless a
new explicit team decision authorizes their replacement.
