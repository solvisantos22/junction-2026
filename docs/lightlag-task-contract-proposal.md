# Lightlag task contract: proposal v0.1

**A proposal for priority 1 of the [morning brief](lightlag-morning-brief.md), not a team decision.** It names one objective, one mission and one reference, and says what result would falsify the claim. Nothing here is promoted to `harbor/lightlag`. Written by Manh with Claude Code, Saturday 14 November, about 14:15 Helsinki, on `main` at `4a5e8b4`. Edit it in the meeting; bump the version when anything changes.

## The contract in one table

| Item | Proposal |
|---|---|
| **What it measures** | Whether the agent keeps track of delayed observations, the commands it has already queued, and the time and energy those commands commit. It must bring the rover home with the samples a public-information controller collects, under rules that are fully published. This is the brief's construct. |
| **Mission** | Dynamic Lightlag, profile `rush`, seed **501**, delay 3 ticks, horizon 50, noise level 1.0, bumpiness 0. These are the exact settings of the fixed-seed and overnight runs (source `02e4f70`, clean). |
| **What the map holds** | Five targets at launch. Two discoveries, each worth 2: d2 appears at tick 6 (deadline 18) and d1 at tick 11 (deadline 21). Maximum value 12. |
| **Reward** | Credited value × survival factor ÷ 12. A sample on time earns its full value; after its deadline it earns 25%. The survival factor is 1.0 alive at base, 0.5 alive away from base, 0 dead. These are the existing grader's rules, unchanged. |
| **Reference** | Frozen `kf_mpc` (Manh controller 1), unchanged: **0.833**. It takes d2 on time, declines d1 and drives home ([run](lightlag-runs/rush-seed501-delay3-kf-mpc/)). |
| **Floors** | No-op 0.000, blind plan 0.583, whole-leg waiting 0.583 ([comparison](lightlag-fixed-seed-comparison.md)). |
| **Shown, never graded against** | All-knowing bound 0.875. Controller 36 scores 0.875 on this draw and 0.84 averaged over noise redraws. Claude with the accounting aid scored 0.917, the best seen. The all-knowing bound without delay scores 1.000. |

## Evidence on this instance

Claude Opus 5.5 with the original prompt, every attempt kept:

| Run | Reward | Outcome | Decisive mistake (audit) |
|---|---:|---|---|
| [fixed seed](lightlag-runs/rush-seed501-delay3-opus-5-5/) | 0.000 | dead | queued d1 at tick 15, sampled at tick 23 (deadline 21) ([audit](lightlag-audits/fixed-seeds501-504/rush-seed501-delay3-opus-5-5/audit.md)) |
| [a01](lightlag-runs/overnight-a01-rush-seed501-r1-opus-5-5/) | 0.000 | dead | d1 sampled at tick 23 (deadline 21) ([audit](lightlag-audits/overnight/overnight-a01-rush-seed501-r1-opus-5-5/audit.md)) |
| [a04](lightlag-runs/overnight-a04-rush-seed501-r2-opus-5-5/) | 0.833 | home | none; ties the reference |
| [a07](lightlag-runs/overnight-a07-rush-seed501-r3-opus-5-5/) | 0.000 | dead | d2 sampled at tick 24 (deadline 18) ([audit](lightlag-audits/overnight/overnight-a07-rush-seed501-r3-opus-5-5/audit.md)) |
| [b05, original prompt](lightlag-runs/overnight-b05-c-rush-seed501-r1-opus-5-5/) | 0.000 | dead | aimed from a packet 6 commands old; d2 sampled at tick 21 (deadline 18) ([audit](lightlag-audits/overnight/block-b/overnight-b05-c-rush-seed501-r1-opus-5-5/audit.md)) |
| [b08, original prompt](lightlag-runs/overnight-b08-c-rush-seed501-r2-opus-5-5/) | 0.438 | alive, away from base | d1 sampled at tick 23 (deadline 21) ([audit](lightlag-audits/overnight/block-b/overnight-b08-c-rush-seed501-r2-opus-5-5/audit.md)) |

**Mean 0.212. Four deaths and one rover away from base in six attempts.**
- **No infrastructure findings** in any audit.
- **Every fact needed was public:** the deadline is on the map, and each acknowledgement gives the tick its command will execute.
- **With the accounting aid** (b06 and b07), the same model scored 0.917 and 0.875, home both times.

**The reference does not depend on luck.** A local check replayed this map with the per-tick noise redrawn 30 more times; the map, slips and bias were unchanged. `kf_mpc` scored 0.833 on every draw and never died. So does every Manh controller from 1 to 35 that uses only public information. The gap therefore does not hinge on which of our controllers is the reference.

## The claim we would make, and the claims we would not

**Make:** "On a fully published instance, Claude Opus 5.5 with the original prompt lost the rover in four of six attempts. Each time it committed to a discovery it could no longer reach in time, once the 3-tick delay and its own queued commands were counted. A public-information controller scores 0.833 here and never dies. With explicit accounting advice, the same model scores 0.875–0.917."

**Do not make:**
- **A failure rate on random maps.** Seed 501 was chosen after failures were seen. Seeds 500 and core 7 are solved, and the model won or tied on several other seeds. Show those mixed results next to it.
- **That the model cannot do it.** The aid shows it can.
- **That this is a Mars digital twin.**

## What would falsify it (declare before any new attempt)

| # | Test | Falsified if |
|---|---|---|
| F1 | 3 new original-prompt attempts on the packaged task, no retries | 2 or more reach the reference's 0.833. Under the current rate (1 in 6) that has about a 7% chance. |
| F2 | Audit of every new failure | The decisive mistake is not deadline, queue or energy bookkeeping, or the audit finds an infrastructure fault (the attempt is kept but reported apart). |
| F3 | Fresh trap seeds, chosen by a scripted rule (below) before any model plays them | Original-prompt attempts average at least 90% of the reference with no deaths. Then the trap is specific to seed 501, and we say so. |
| F4 | Reference fairness | A shortcut (no-op, blind, whole-leg waiting) comes within 0.10 of the reference, or the reference's score depends on the noise draw. Both already checked: none. |

## Fresh-data check (priority 3, Manh + Sölvi)

1. **Free scripted screen.**
   - Build a "chaser": `kf_mpc` that queues each discovery as soon as it appears, without checking the acknowledged execute tick against the deadline or the energy needed to get home. It must fail on `rush` 501 and solve `rush` 500, as Claude did. If it doesn't, stop.
   - Screen unused seeds (7000 and up; none of 0–19, 100–139, 200–209, 300–319, 400–419, 500–504, 600–979, 1000–1499, 3000–3019, 5000–5259, 6000–6259, 60000–60019) with this rule:
     - `kf_mpc` stays within 10% of the best scripted score and never dies over 31 noise draws;
     - the chaser dies or loses at least 0.4.
   - Take the top two by the chaser's loss.
2. **Paid attempts, on Sölvi's ledger, no retries, every attempt kept:**
   - 3 on the packaged seed 501 (F1, which also confirms the package);
   - 3 on each fresh trap seed (F3).
   - That is 9 attempts at about $0.43 each, under $4, within the remaining budget the brief reports.

## Alternatives considered

| Option | Why not, for now |
|---|---|
| `rush_noisy` 504 | Claude fails often there (mean 0.38, 2 deaths in 6), but the reference reaches only 0.70 against the all-knowing 1.00. |
| Discriminative seeds 1000–1499 (`manh_controllers/seeds.py`) | Hard for scripted shortcuts, not shown hard for Claude. They resemble seed 500, which Claude solved. The sharpest one, 1165, is noise luck: the reference is perfect on only 65% of redraws, the bound on 13%. |
| `rush` 504 | Controllers 24, 34 and 36 score 1.00 on every draw, but `kf_mpc` only 0.70. Using it would mean switching the reference, and Claude has one attempt there (0.70). |
| Core seed 7, seed 500 | Solved by Claude. |
| Rule changes (wider heading bias, heavier noise, relay windows, slip check, real-time clock) | Not needed for this claim. The brief defers new mechanics. |

## Decisions for the meeting

1. **The task:** accept seed 501, change it, or plan a set: 501 plus the fresh trap seeds once they exist.
2. **Falsification:** accept F1–F4 and the budget for 9 attempts.
3. **Packaging:** Kristján points canonical `harbor/lightlag` at the chosen instance (priority 2).
4. **Story:** keep seeds 500 and 7 and the model wins visible in it (priority 4).

## Reproduce the reference check

From the repository root, standard library only:

```python
from lightlag_dynamic.controllers import POLICIES
from lightlag_dynamic.tools import PublicTools
from lightlag_dynamic.manh_controllers.scenarios import make_env

for draw in range(31):  # draw 0 is the published noise; the map, slips and bias never change
    env = make_env(501, 3, "rush")
    if draw:
        env._seed = 501 * 1000 + draw  # redraws only the per-tick noise streams
    POLICIES["kf_mpc"](PublicTools(env))
    while not env.advance(5)["episode_complete"]:
        pass
    r = env.replay()["result"]
    print(draw, round(r["raw_score"] / r["max_available_value"], 3), r["alive"], r["at_base"])
```
