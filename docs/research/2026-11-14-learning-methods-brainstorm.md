# Learning methods that could beat our environments: picks and reading list

Saturday 14 November 2026, about 21:21 Helsinki. Manh / Claude Code. **A brainstorm, not a team decision.** Nothing was trained or run for it, and no teammate's code or results changed. Links were checked on the day: every arXiv link against the arXiv API, every DOI against Crossref, and every award against the conference's own announcement or the named report ([how this was checked](#how-this-was-checked)).

**Manh's question.** PPO + ICM is one idea, built in another chat and now on `main` as `lightlag_ppo_icm/`. Which known RL, deep-RL or other learning methods suit our task of beating the environments: the max env, `rush`, Lightlag Traverse and its MAX map? Collect the relevant papers, award winners included.

## The short answer

The scripted players win because they **plan with the published model**. They simulate ahead, keep the battery above a floor along the whole route, and head home with time to spare. A learner that starts from nothing has to rediscover all of that from one number at the end of a mission. So the methods that fit are the ones that **use the model, a teacher or a safety rule**, not the ones that explore harder.

Five picks to accept or deny. The first two go at the two faults every learner here has shown so far: it doesn't get home, and it starts from nothing. The third is the one with a route past the scripted players. The last two fix specific weak spots.

| | Pick | One reason | Helps most on |
|---|---|---|---|
| 1 | **Bumpers for battery and home** (shielded RL) | Our PPO agent never came home, even when rewarded step by step for heading there; on Traverse, a check that allows only trips the rover can return from brought 120 of 120 home | PPO + ICM on the max env and `rush` |
| 2 | **Copy the teacher, then practise** (imitation, then RL) | The one learned step that has clearly worked here: copying the planner tripled a Traverse learner's score | all four environments |
| 3 | **Search plus a learned judge** (AlphaZero-style) | Learning that beats strong planners is added to search, not swapped in for it | Traverse route choice |
| 4 | **See all targets at once** (attention routing nets) | Picking targets is an orienteering problem with deadlines; this model family was built for it and won the closest competition | Traverse target choice |
| 5 | **A teacher who sees the hidden values** (privileged learning) | In training we know the true slip, wheel size and panels: the teacher learns fast, the student learns to guess them | MAX map, max env |

For PPO + ICM itself: **keep PPO, switch curiosity off** ([why](#ppo--icm-keep-or-swap)).

### 1. Bumpers for the battery and the trip home

*Picture: bowling with bumpers. They don't throw for you; they only keep the ball out of the gutter, so every throw still teaches you something.*

A shield sits between the policy and the rover. It vetoes any action after which a safe ending is no longer possible. The policy still learns everything else.

- **Why here.** The score is collected value × 1 at the lander, × 0.5 alive elsewhere, × 0 with a flat battery, and it is paid once, at the very end. The [PPO + ICM report](../../lightlag_ppo_icm/README.md) shows both sides. On `rush`, before the battery guard, the score stayed at or below 0.2% for 450,000 decisions; with the guard, the same settings were rising within 250,000. But the guard only prevents dying. The agent came home on 0 of 40 fresh max-env missions, and an away ending halves the score. Rewarding it step by step for heading home (three runs) did not change that: by the time going home would pay, the guard is already holding the rover still. The report names the missing piece itself: a guard that also keeps the energy for the way home in hand.
- **It already worked on Traverse.** Kristján's [visit-and-return check](../lightlag-rl-feasible-results/README.md) masks out every target the rover could not visit and still get home from. When the check also counted the waits to recharge, all 120 development missions ended home and alive, against 70 of 120 when it counted travel time alone. The policies themselves were unchanged.
- **The same fault sinks Claude's programs.** The farm's new [point-of-no-return check](../traverse-farm.md#where-the-way-home-closed-the-point-of-no-return) replayed six saved Claude programs on 300 fresh worlds: of the 294 rovers they lost, 257 ran flat while the way home was still open, deaths that waiting for the sun would have avoided. The reference never reached that point.
- **In our code.** Extend the max env's battery guard into a home guard: once the energy or time needed to get home, with the guard's margins, reaches what is left, allow only the `plain` rule's drive home, or a wait. The agent then learns only what to do with the energy it may spend. To let it choose the moment itself, add a "go home and park" action, as in Sölvi's campaign. A potential-based pull toward home can stay on top, since it provably cannot change the best policy ([Ng et al. 1999](https://people.eecs.berkeley.edu/~russell/papers/icml99-shaping.pdf)), but on its own it did not bring this agent home.
- **Since built (14 November, about 23:00 Helsinki).** The home guard is now an option of the tester (`--home-guard`, [`lightlag_ppo_icm/home.py`](../../lightlag_ppo_icm/home.py)). On 40 fresh max-env missions (seeds 2800-2839) the learned agents with it come home in 34 to 36 missions instead of none. Switched on for `max.npz` without retraining, it adds 4.1 points (95% interval +1.7 to +6.6); retraining with the guard did no better than that, and the agents still leave the pacing to the guard. The "go home and park" action is not built. [Results and limits](../../lightlag_ppo_icm/README.md#results).
- **Read first.** [Safe RL via Shielding](https://arxiv.org/abs/1708.08611) (AAAI 2018) · [Invalid action masking in policy gradients](https://arxiv.org/abs/2006.14171) (FLAIRS 2022) · [Saute RL](https://arxiv.org/abs/2202.06558) (ICML 2022), which puts the remaining safety budget (our battery margin) into the state · [Reward Constrained Policy Optimization](https://arxiv.org/abs/1805.11074) (ICLR 2019).

### 2. Copy the teacher first, then practise

*Picture: an apprentice first copies the master's moves exactly, then practises to find tricks of their own.*

Train the network to imitate a scripted player, then continue with RL. Behaviour cloning copies the teacher's choices; DAgger then keeps asking the teacher what to do in the places the student actually reaches. A variant keeps the teacher running and learns only corrections on top of it (residual RL), so learning starts at the teacher's score.

- **Why here.** Kristján [tested exactly this on Traverse](../lightlag-rl-feasible-results/contextual.md) today, with a 1,984-weight chooser of the next target. Copying the planner lifted its score on 16 fresh worlds from .093 untrained to .282, with every rover home. The 128 RL missions per seed that followed added nothing measurable (−.003, 95% −.014 to +.007). Two limits kept it below greedy (.326) and the full planner (.509), and both can be worked on. The teacher it could copy is the planner cut down to one target at a time, which scored about .35–.38 on its own (on other worlds). And it matched the teacher's choice on 86–89% of training decisions but only 64–68% on held-out worlds.
- **Where the gap is wider.** On the max env, `max_navigator` scores 28.2% and PPO + ICM 11.0%; on `rush`, 82.3% against 28.1%. There, copying is the cheap first step that PPO hasn't had.
- **In our code.** On the max env, start with `plain` as the teacher: it runs on the same adapter, so its choices are already among the 50 actions, and it scores 15.3% and gets home in 17 of 40 missions. Clone it, then continue with PPO plus a fading penalty for straying from it ([Kickstarting](https://arxiv.org/abs/1803.03835)); then try `max_navigator`, mapping its commands to the nearest action. On Traverse, the next steps after Kristján's pilot are DAgger, for the held-out gap; more than 16 teacher worlds; and a student that can follow the full-route planner (picks 3 and 4). His RL phase was short (eight updates per seed): it rules out that run, not RL after imitation in general.
- **Read first.** [DAgger](https://arxiv.org/abs/1011.0686) (AISTATS 2011) · [Jump-Start RL](https://arxiv.org/abs/2204.02372) (ICML 2023) · [RLPD](https://arxiv.org/abs/2302.02948) (ICML 2023) · [Residual RL for robot control](https://arxiv.org/abs/1812.03201) (ICRA 2019) · AlphaStar ([Nature 2019](https://doi.org/10.1038/s41586-019-1724-z)): imitation first, then RL, to grandmaster level.

### 3. Search plus a learned judge

*Picture: a chess player calculates a few moves ahead, then judges the end position by feel. After each game the feel is retrained on what the calculation found, so the next calculation looks in better places.*

Keep a search at every decision (the pilot's beam, or Monte Carlo tree search), and learn a value: an estimate of what a partial route can still collect and whether it gets home. The search uses the value to rank and prune; the value is retrained on search results and finished missions. This loop is called Expert Iteration.

- **Why here.** Our model is published, so search is cheap and exact where a pure policy network has to guess. The pilot's beam search moved Traverse from 0.48 to 0.505 on the development worlds and from 0.45 to 0.565 on the task's world. A better judge of partial routes lets the same beam width find better routes. That is how Deep Policy Dynamic Programming and simulation-guided beam search gained on time-window routing, and how the Go and chess systems that beat strong programs worked. It also avoids the cap pick 2 ran into: the planner keeps its full-route search, and learning only sharpens its judgement.
- **In our code.** Start with the value alone: replace the beam's ranking of partial routes with a small network trained on farm missions (rover position, time, battery and a summary of the remaining targets → final score). Add a policy prior only if that helps.
- **Read first.** [Expert Iteration](https://arxiv.org/abs/1705.08439) (NeurIPS 2017) · [AlphaZero](https://arxiv.org/abs/1712.01815) (Science 2018) · [Gumbel MuZero](https://openreview.net/forum?id=bERaNdoegnO) (ICLR 2022), which works with very few simulations · [Deep Policy Dynamic Programming](https://arxiv.org/abs/2102.11756) (CPAIOR 2022) · [Simulation-guided Beam Search](https://arxiv.org/abs/2207.06190) (NeurIPS 2022) · [How to combine tree search in RL](https://arxiv.org/abs/1809.01843) (AAAI 2019 Outstanding Paper).

### 4. See all targets at once

*Picture: planning errands. You don't rate each shop on its own; you look at the whole town and notice that three shops on one street are worth one trip.*

An attention network reads every open target together (value, deadline, distance, energy to reach it and to get home afterwards) and points to the next one. POMO-style training plays several rollouts on the same world and compares them with each other, which removes "this world was just hard" from the learning signal.

- **Why here.** Traverse target choice is an orienteering problem with deadlines and a battery. Our first RL scorer rated each candidate on its own, and [Kristján's review](2026-11-14-rl-reference-and-failures.md) showed a candidate's rank there cannot depend on the others, so it cannot see clusters. The closest public competition, AI4TSP 2021 (orienteering with random travel times and time windows), was won in its RL track by POMO plus per-world search plus Monte Carlo rollouts ([report](https://arxiv.org/abs/2201.10453)).
- **In our code.** Both contextual learners, Sölvi's campaign and Kristján's pilot, summarise the other candidates by their mean and maximum. Swap that summary for a small attention encoder with a pointer output; keep the same masks, options and reward. Train with several rollouts per world and a shared baseline, and start by copying the planner (pick 2).
- **Read first.** [Attention, Learn to Solve Routing Problems!](https://arxiv.org/abs/1803.08475) (ICLR 2019; covers orienteering and a stochastic prize-collecting TSP) · [POMO](https://arxiv.org/abs/2010.16011) (NeurIPS 2020) · [Efficient Active Search](https://arxiv.org/abs/2106.05126) (ICLR 2022) · [Learning to handle complex constraints](https://arxiv.org/abs/2410.21066) (NeurIPS 2024; tight time windows) · [RL for orienteering with time windows](https://arxiv.org/abs/2011.03647) (Computers & OR 2021) · [DRL for electric-vehicle routing with time windows](https://arxiv.org/abs/2010.02068) (battery and charging).

### 5. A teacher who can see the hidden values

*Picture: a driving instructor who can see the black ice sits beside the learner. The learner can't see it, but learns to feel it through the steering wheel.*

In training, give a teacher policy, or just the critic, the hidden truth: slip, panel efficiency and heading bias, and on the MAX map also wheel size, sand gain and the soft cells under the crust. Then train a student that sees only telemetry to act like the teacher, or to guess those values from its recent history.

- **Why here.** On the MAX map the hidden values decide survival. The reference pilot keeps 14% of its normal-map score there and trips the slip check 14 times a mission. `manh_max` recovers much of it with hand-written estimators (0.313 against 0.072); a student that learns to read the hidden values from telemetry is the learned version of that. The same recipe taught legged robots to walk on unseen terrain, and it is the method of the CoRL 2021 best paper.
- **In our code.** Start cheap: give the PPO critic the true hidden values during training only (asymmetric actor-critic). The actor, and so the player, stays public-only. Later, an adaptation module that predicts the hidden values from history can be checked directly against the truth.
- **Read first.** [Asymmetric actor critic](https://arxiv.org/abs/1710.06542) (RSS 2018) · [Learning by Cheating](https://arxiv.org/abs/1912.12294) (CoRL 2019) · [RMA](https://arxiv.org/abs/2107.04034) (RSS 2021) · [Quadrupeds over challenging terrain](https://arxiv.org/abs/2010.11251) (Science Robotics 2020) · [In-hand object re-orientation](https://arxiv.org/abs/2111.03043) (CoRL 2021 Best Paper) · [VariBAD](https://arxiv.org/abs/1910.08348) (ICLR 2020).

## PPO + ICM: keep or swap?

**Keep PPO, set the curiosity coefficient to 0 (`--int-coef 0`), and spend the effort on picks 1 and 2.**

- **Our own run measured it.** On fresh seeds, curiosity added +0.3 points (95% interval −2.5 to +2.8), and PPO alone was ahead for the first two million decisions.
- **Why it can't help much here.** ICM pays the agent for being surprised. Our worlds are full of surprise no model can learn away: position noise, heading drift, lost packets, wild fixes. The large study of curiosity calls this the noisy-TV problem ([Burda et al., ICLR 2019](https://arxiv.org/abs/1808.04355)). The report met two cousins of it: the first curious agent parked against a hazard and kept driving into it, because its own last command changed the observation each time; and curiosity favoured long drives, which before the guard meant an earlier death.
- **Exploration is not what's missing.** The map and the targets are published, and every sample pays. What's missing is pacing and getting home: in the report's words, energy has no price until it is gone, and the bill arrives about twenty decisions later.

*Picture: a curious child who stares at TV static all day, because static never stops being "new".*

If you want an exploration bonus anyway, use one made for noisy worlds that change every episode: an episodic count of map cells visited this mission ([Henaff et al., ICML 2023](https://arxiv.org/abs/2306.03236)), [E3B](https://arxiv.org/abs/2210.05805) (NeurIPS 2022), or ensemble disagreement ([Pathak et al., ICML 2019](https://arxiv.org/abs/1906.04161)), which ignores noise that nobody can predict. Fade it to zero, and never let it override a guard.

## Also worth knowing (not picks)

- **Delays are already handled the textbook way.** Planning for the state at the tick a command lands, with the commands in flight applied, is the classic fix ([Katsikopoulos & Engelbrecht 2003](https://doi.org/10.1109/TAC.2003.809799); [Walsh et al. 2009](https://doi.org/10.1007/s10458-008-9056-7)). The pilot and the PPO adapter both do it. Newer learned variants are in the [delays list](#delays).
- **LLM-written programs, evolved on the farm** (FunSearch, AlphaEvolve, ReEvo, EoH). The farm already scores programs on hundreds of worlds. Tuning the pilot's numbers looks nearly spent: its owner expects about 0.01 from a full option search, and the one search run, under the harsher day, was stopped half way with its best setting at +0.005. Evolving the code can change its structure instead. It spends model credit, and [AfterQuery supplies none](../afterquery-update-2026-11-14.md).
- **Train where you lose.** Prioritized Level Replay and ACCEL choose the training worlds where the learner trails most. Worlds differ a lot: the pilot ranges from 0.373 to 0.554 on 24 fresh Traverse worlds.
- **Risk, not only the mean.** The battery cliff makes the worst missions matter; CVaR objectives and distributional RL optimise that bad tail directly.
- **Honest comparisons.** Paired worlds, every training seed and interval estimates ([Agarwal et al., NeurIPS 2021 Outstanding Paper](https://arxiv.org/abs/2108.13264)). The team already works this way.

## Background: what the environments ask of a learner

From the repository, not from papers.

- **Two jobs in one.** Choosing which targets, in what order and when to turn home (on Traverse, 46 targets with deadlines, of which the pilot samples about 23–29), and driving there over slip, slopes and hazards.
- **The rules are published.** `rules()`, `map()` and the ground model as code (`lightlag_surface.py`) give every formula. Only a few values are hidden, inside published ranges: slip, panel efficiency and heading bias, and on the MAX map also wheel size, sand gain and soft cells under the crust. A learner can simulate ahead; it does not need to discover the physics.
- **One cliff decides a lot.** Collected value × 1 at the lander, × 0.5 alive elsewhere, × 0 with a flat battery, decided at the end.
- **Late commands, old news.** A command executes `delay_ticks + 1` ticks after it is sent at the earliest; telemetry is `delay_ticks` old. On the MAX map the link is open 4 ticks of every 8 and 10% of packets are lost.
- **Fresh worlds.** Every seed is a new map, so a learner must generalise. The farm and Modal can play thousands of missions.
- **Strong scripted teachers.** The beam-search pilot (0.502 on 300 fresh Traverse worlds), `manh_max` on the MAX map (0.313 against the pilot's 0.072), `max_navigator` on the max env (28.2%).

### Where learning stands

| Learner (owner) | Environment | Result | Scripted comparison |
|---|---|---|---|
| PPO + ICM, 3.6M decisions ([Manh](../../lightlag_ppo_icm/README.md)) | max env, 40 fresh missions | 11.0%, home 0/40 | `max_navigator` 28.2%; the `plain` rule on the same adapter 15.3% |
| PPO alone, 3.0M decisions (same) | max env | 10.7% | curiosity's effect +0.3 points (−2.5 to +2.8) |
| PPO + ICM, 2.65M decisions (same) | `rush`, 40 fresh missions | 28.1%, home 1/40 | `kf_mpc` 82.3% |
| Planner imitation, then 128 RL missions per seed; 1,984-weight next-target chooser ([Kristján](../lightlag-rl-feasible-results/contextual.md)) | Traverse, 16 fresh worlds | untrained .093, imitation .282, after RL .279; all home | charging-aware greedy .326; full-route planner .509 |
| Contextual PPO over persistent targets, 512 missions ([Sölvi](../learning-campaign-results/README.md)) | Traverse validation | 0.344 | greedy 0.381; beam pilot 0.514 |
| 256-weight REINFORCE target scorer ([Sölvi](../lightlag-rl-results/README.md)) | Traverse, 40 check maps | 0.025 | greedy on the same navigator 0.233 |

Maps, budgets and seeds differ between rows. Sölvi's 2048-mission pilot results are not published yet, and his larger training stages are paused.

## The competitions closest to our task

| Competition | Task | What won | Lesson |
|---|---|---|---|
| [AI4TSP](https://arxiv.org/abs/2201.10453), IJCAI 2021 | Orienteering from a depot with time windows; random travel times revealed while driving; penalties for arriving late and for overrunning the tour limit | RL track: 1st RISEup, with POMO, per-instance Efficient Active Search and Monte Carlo rollouts (600 per candidate next stop, five candidates); 2nd Ratel, a pointer network with time-window features trained by REINFORCE | A learned policy plus per-world search plus rollouts: picks 3 and 4 |
| [EURO Meets NeurIPS 2022](https://neurips.cc/virtual/2022/competition/50085) vehicle routing | Vehicle routing with time windows, static and dynamic (requests arrive during the day) | [Baty et al.](https://arxiv.org/abs/2304.00789) report first place on the dynamic variant: a learned layer prices each waiting request and a prize-collecting routing solver decides the routes | Learning steers a strong solver instead of replacing it |
| [NetHack Challenge](https://arxiv.org/abs/2203.11889), NeurIPS 2021 | A long, procedurally generated game | Symbolic bots outperformed deep RL by a large margin | Against a good scripted player, pure RL loses; hybrids are the way in |
| [Flatland](https://arxiv.org/abs/2103.16511), NeurIPS 2020 | Train scheduling and rescheduling on a grid | The best submissions were operations-research methods | The same lesson |

On AI4TSP the noise was travel time; on Traverse it is slip, panels and sensing. The AI4TSP organisers also questioned whether participants should get the full simulator, since it exposes the exact distributions; we publish ours on purpose.

## Award winners that bear on this task

Each award is checked against the linked announcement or report.

| Award | Paper | Why it matters here |
|---|---|---|
| NIPS 2016 Best Paper ([awards](https://neurips.cc/Conferences/2016/Awards)) | [Value Iteration Networks](https://arxiv.org/abs/1602.02867) | A network that runs value iteration over a grid map: a learned cost-to-go field |
| ICML 2016 Best Paper ([Google's report](https://research.google/blog/icml-2016-research-at-google/)) | [Dueling Network Architectures](https://arxiv.org/abs/1511.06581) | A Rainbow ingredient that Sölvi's replay learner leaves out |
| ICML 2026 Test of Time, for ICML 2016 ([ICML 2026 awards](https://blog.icml.cc/2026/07/05/announcing-the-icml-2026-awards/)) | [A3C](https://arxiv.org/abs/1602.01783) | Parallel actor-critic, the ancestor of our PPO setups |
| ICLR 2026 Test of Time, for ICLR 2016 ([announcement](https://blog.iclr.cc/2026/04/22/announcing-the-test-of-time-awards-from-iclr-2016/)) | [DDPG](https://arxiv.org/abs/1509.02971) | Continuous actions: heading and metres without 16 × 3 bins |
| ICLR 2018 Best Paper ([Synced](https://syncedreview.com/2018/04/16/iclr-2018s-best-papers-variant-adam-spherical-cnns-and-meta-learning/)) | [Continuous Adaptation via Meta-Learning](https://arxiv.org/abs/1710.03641) | Adapting quickly when conditions change, as the MAX map's hidden values demand |
| AAAI 2019 Outstanding Paper ([Synced](https://syncedreview.com/2019/01/29/aaai-19-announces-best-papers/)) | [How to Combine Tree-Search Methods in RL](https://arxiv.org/abs/1809.01843) | Pick 3 |
| NeurIPS 2021 Outstanding Paper ([announcement](https://blog.neurips.cc/2021/11/30/announcing-the-neurips-2021-award-recipients/)) | [Deep RL at the Edge of the Statistical Precipice](https://arxiv.org/abs/2108.13264) | How to compare learners honestly with few seeds |
| NeurIPS 2021 Outstanding Paper (same) | [On the Expressivity of Markov Reward](https://arxiv.org/abs/2111.00876) | When a goal can be written as per-step reward; ours can, once collected value is part of the state |
| CoRL 2021 Best Paper ([AIhub](https://aihub.org/2021/11/24/interview-with-tao-chen-jie-xu-and-pulkit-agrawal-corl-2021-best-paper-award-winners/)) | [In-hand object re-orientation](https://arxiv.org/abs/2111.03043) | Privileged teacher, then student: pick 5 |
| ICML 2022 Outstanding Paper ([awards](https://icml.cc/virtual/2022/awards_detail)) | [Do Differentiable Simulators Give Better Policy Gradients?](https://arxiv.org/abs/2202.00817) | When gradients through our ground model would help, and when its hard stops would mislead them |
| ICML 2022 Outstanding Paper (same) | [Non-Markovianity in Maximum State Entropy Exploration](https://arxiv.org/abs/2202.03060) | Exploration that remembers the mission so far |
| NeurIPS 2022 Outstanding Paper ([awards](https://blog.neurips.cc/2022/11/21/announcing-the-neurips-2022-awards/)) | [ProcTHOR](https://arxiv.org/abs/2206.06994) | Training on many procedurally generated worlds to generalise |
| ICLR 2023 Outstanding Paper ([announcement](https://blog.iclr.cc/2023/03/21/announcing-the-iclr-2023-outstanding-paper-award-recipients/)) | [Emergence of Maps in the Memories of Blind Navigation Agents](https://arxiv.org/abs/2301.13261) | Navigating by memory and egomotion alone: dead reckoning under drift |
| NeurIPS 2025 Best Paper ([announcement](https://blog.neurips.cc/2025/11/26/announcing-the-neurips-2025-best-paper-awards/)) | [1000 Layer Networks for Self-Supervised RL](https://arxiv.org/abs/2503.14858) | Goal-reaching RL that scales with depth, for a learned navigator |

Checked and not directly relevant: the ICLR 2026 Outstanding Papers (how compactly transformers represent concepts; LLMs losing track in multi-turn conversation) and the ICML 2026 Outstanding Papers (diffusion). The RLC 2025 award for scientific understanding went to [How Should We Meta-Learn RL Algorithms?](https://arxiv.org/abs/2507.17668) ([Oxford news](https://aims.robots.ox.ac.uk/newsblog-posts/alex-goldie-receives-outstanding-paper-for-scientific-understanding-in-reinforcement-learning-at-rlc-2025-in-alberta)), background only. NeurIPS 2026 awards are not out yet.

## Reading list by family

About 245 papers, grouped by what they would do for us. **Bold** marks an award. Venues are the peer-reviewed ones where they exist; otherwise the arXiv year.

### Search plus learning (pick 3)

- [Thinking Fast and Slow with Deep Learning and Tree Search](https://arxiv.org/abs/1705.08439) — Anthony et al., NeurIPS 2017. Expert Iteration.
- [Mastering the game of Go with deep neural networks and tree search](https://doi.org/10.1038/nature16961) — Silver et al., Nature 2016.
- [Mastering Chess and Shogi by Self-Play with a General RL Algorithm](https://arxiv.org/abs/1712.01815) — Silver et al., 2017; [Science 2018](https://doi.org/10.1126/science.aar6404). AlphaZero.
- [Mastering Atari, Go, Chess and Shogi by Planning with a Learned Model](https://arxiv.org/abs/1911.08265) — Schrittwieser et al., [Nature 2020](https://doi.org/10.1038/s41586-020-03051-4). MuZero; we can skip its learned model, because ours is published.
- [Policy improvement by planning with Gumbel](https://openreview.net/forum?id=bERaNdoegnO) — Danihelka et al., ICLR 2022. Strong with very few simulations.
- [Planning in Stochastic Environments with a Learned Model](https://openreview.net/forum?id=X6D9bAHhBQ1) — Antonoglou et al., ICLR 2022. Chance nodes for random outcomes.
- [Learning and Planning in Complex Action Spaces](https://arxiv.org/abs/2104.06303) — Hubert et al., ICML 2021. Sampled MuZero, for continuous heading and distance.
- [Mastering Atari Games with Limited Data](https://arxiv.org/abs/2111.00210) — Ye et al., NeurIPS 2021 (EfficientZero); [EfficientZero V2](https://arxiv.org/abs/2403.00564) — Wang et al., ICML 2024.
- [Monte-Carlo Tree Search as Regularized Policy Optimization](https://arxiv.org/abs/2007.12509) — Grill et al., ICML 2020.
- [SPO: Sequential Monte Carlo Policy Optimisation](https://arxiv.org/abs/2402.07963) — Macfarlane et al., NeurIPS 2024. A search that parallelises well.
- [Muesli: Combining Improvements in Policy Optimization](https://arxiv.org/abs/2104.06159) — Hessel et al., ICML 2021.
- [How to Combine Tree-Search Methods in Reinforcement Learning](https://arxiv.org/abs/1809.01843) — Efroni et al., AAAI 2019. **Outstanding Paper.**
- [Ranked Reward: Enabling Self-Play RL for Combinatorial Optimization](https://arxiv.org/abs/1807.01672) — Laterre et al., 2018. AlphaZero for one-player problems: beat your own recent results.
- [Thinker: Learning to Plan and Act](https://arxiv.org/abs/2307.14993) — Chung et al., NeurIPS 2023.
- [Learning to Search with MCTSnets](https://arxiv.org/abs/1802.04697) — Guez et al., ICML 2018.
- [Nested Rollout Policy Adaptation for Monte Carlo Tree Search](https://www.ijcai.org/proceedings/2011/0115.pdf) — Rosin, IJCAI 2011. Learns a rollout policy inside one problem.
- [Nested Monte-Carlo Search](https://www.ijcai.org/proceedings/2009/0083.pdf) — Cazenave, IJCAI 2009.
- [Optimization of the Nested Monte-Carlo Algorithm on the TSP with Time Windows](https://doi.org/10.1007/978-3-642-20520-0_51) — Rimmel, Teytaud & Cazenave, EvoApplications 2011.
- [Application of the NRPA Algorithm to the TSP with Time Windows](https://doi.org/10.1007/978-3-642-34413-8_4) — Cazenave & Teytaud, LION 2012. Nested search on time-window routing, a cousin of our route layer.

### Routing and target choice (pick 4)

Neural solvers:

- [Pointer Networks](https://arxiv.org/abs/1506.03134) — Vinyals et al., NeurIPS 2015.
- [Neural Combinatorial Optimization with Reinforcement Learning](https://arxiv.org/abs/1611.09940) — Bello et al., 2016.
- [Learning Combinatorial Optimization Algorithms over Graphs](https://arxiv.org/abs/1704.01665) — Dai et al., NeurIPS 2017.
- [Reinforcement Learning for Solving the Vehicle Routing Problem](https://arxiv.org/abs/1802.04240) — Nazari et al., NeurIPS 2018. Demands that change during the route.
- [Attention, Learn to Solve Routing Problems!](https://arxiv.org/abs/1803.08475) — Kool et al., ICLR 2019. Covers orienteering and a stochastic prize-collecting TSP.
- [Buy 4 REINFORCE Samples, Get a Baseline for Free!](https://openreview.net/forum?id=r1lgTGL5DE) — Kool et al., ICLR 2019 workshop. Several rollouts per instance as the baseline.
- [POMO: Policy Optimization with Multiple Optima](https://arxiv.org/abs/2010.16011) — Kwon et al., NeurIPS 2020.
- [Matrix Encoding Networks for Neural Combinatorial Optimization](https://arxiv.org/abs/2106.11113) — Kwon et al., NeurIPS 2021. Reads a travel-cost matrix directly, such as cost-to-go between targets.
- [Learning to Solve VRPs with Time Windows through Joint Attention](https://arxiv.org/abs/2006.09100) — Falkner & Schmidt-Thieme, 2020.
- [Learning Collaborative Policies to Solve NP-hard Routing Problems](https://arxiv.org/abs/2110.13987) — Kim et al., NeurIPS 2021.
- [Sym-NCO](https://arxiv.org/abs/2205.13209) — Kim et al., NeurIPS 2022.
- [Neural Combinatorial Optimization with Heavy Decoder](https://arxiv.org/abs/2310.07985) — Luo et al., NeurIPS 2023.
- [BQ-NCO: Bisimulation Quotienting](https://arxiv.org/abs/2301.03313) — Drakulic et al., NeurIPS 2023.
- [Learning to Handle Complex Constraints for Vehicle Routing Problems](https://arxiv.org/abs/2410.21066) — Bi et al., NeurIPS 2024. Tight time windows without infeasible picks.
- [MVMoE: Multi-Task Vehicle Routing Solver](https://arxiv.org/abs/2405.01029) — Zhou et al., ICML 2024; [RouteFinder](https://arxiv.org/abs/2406.15007) — Berto et al., 2024. One model for many routing variants.
- [RL4CO](https://arxiv.org/abs/2306.17100) — Berto et al., 2023. A library with POMO, Sym-NCO and others.

Orienteering, deadlines and batteries:

- [A Reinforcement Learning Approach to the Orienteering Problem with Time Windows](https://arxiv.org/abs/2011.03647) — Gama & Fernandes, [Computers & OR 2021](https://doi.org/10.1016/j.cor.2021.105357).
- [Deep RL for the Electric Vehicle Routing Problem with Time Windows](https://arxiv.org/abs/2010.02068) — Lin et al., 2020. Battery and charging stops.
- [Deep RL for Orienteering Problems Based on Decomposition](https://arxiv.org/abs/2204.11575) — Liu et al., 2022.
- [Learning to Solve Orienteering Problem with Time Windows and Variable Profits](https://arxiv.org/abs/2603.06260) — Gao et al., 2026.
- [N(CO)²: Neural CO with Chance Constraints to Solve Stochastic Orienteering](https://arxiv.org/abs/2606.18514) — Saeed et al., 2026. Risk limits on random travel.
- [The First AI4TSP Competition: Learning to Solve Stochastic Routing Problems](https://arxiv.org/abs/2201.10453) — Bliek et al., [Artificial Intelligence 2023](https://doi.org/10.1016/j.artint.2023.103918). Instances and code on [GitHub](https://github.com/paulorocosta/ai-for-tsp-competition).

Learning inside a search or solver:

- [Efficient Active Search for Combinatorial Optimization Problems](https://arxiv.org/abs/2106.05126) — Hottung et al., ICLR 2022. Fine-tunes on the instance at test time.
- [Simulation-guided Beam Search](https://arxiv.org/abs/2207.06190) — Choo et al., NeurIPS 2022. A network, a beam and rollouts, close to our pilot's beam.
- [Deep Policy Dynamic Programming for Vehicle Routing Problems](https://arxiv.org/abs/2102.11756) — Kool et al., CPAIOR 2022. A learned heat map restricts dynamic programming; strong on time windows.
- [Neural Large Neighborhood Search](https://arxiv.org/abs/1911.09539) — Hottung & Tierney, ECAI 2020.
- [Learning to Delegate for Large-scale Vehicle Routing](https://arxiv.org/abs/2107.04139) — Li et al., NeurIPS 2021.
- [Dual-Aspect Collaborative Transformer](https://arxiv.org/abs/2110.02544) — Ma et al., NeurIPS 2021. Learned improvement moves.
- [Online Control of Adaptive Large Neighborhood Search using Deep RL](https://arxiv.org/abs/2211.00759) — Reijnen et al., 2022. Tested on the AI4TSP orienteering problem.
- [Combinatorial Optimization enriched Machine Learning for the Dynamic VRPTW](https://arxiv.org/abs/2304.00789) — Baty et al., 2023.

Surveys and strong non-learning yardsticks:

- [Machine Learning for Combinatorial Optimization: a Methodological Tour d'Horizon](https://arxiv.org/abs/1811.06128) — Bengio et al., [EJOR 2021](https://doi.org/10.1016/j.ejor.2020.07.063).
- [Combinatorial optimization and reasoning with graph neural networks](https://arxiv.org/abs/2102.09544) — Cappart et al., JMLR 2023.
- [Neural Combinatorial Optimization Algorithms for Vehicle Routing: a Survey](https://arxiv.org/abs/2406.00415) — Wu et al., 2024.
- [The orienteering problem: A survey](https://doi.org/10.1016/j.ejor.2010.03.045) — Vansteenwegen et al., EJOR 2011; [its recent variants](https://doi.org/10.1016/j.ejor.2016.04.059) — Gunawan et al., EJOR 2016; [model evolution and algorithmic advances](https://arxiv.org/abs/2512.16865) — Shen et al., 2025.
- [PyVRP: a high-performance VRP solver package](https://arxiv.org/abs/2403.13795) — Wouda et al., [INFORMS Journal on Computing 2024](https://doi.org/10.1287/ijoc.2023.0055). Open source, with prize collecting and time windows: a yardstick for any learned router.
- [Hybrid Genetic Search for the CVRP](https://arxiv.org/abs/2012.10384) — Vidal, [Computers & OR 2022](https://doi.org/10.1016/j.cor.2021.105643).
- [An Adaptive Large Neighborhood Search Heuristic](https://doi.org/10.1287/trsc.1050.0135) — Ropke & Pisinger, Transportation Science 2006.

### Teacher first (pick 2)

- [A Reduction of Imitation Learning to No-Regret Online Learning (DAgger)](https://arxiv.org/abs/1011.0686) — Ross et al., AISTATS 2011.
- [Policy Distillation](https://arxiv.org/abs/1511.06295) — Rusu et al., ICLR 2016.
- [Deep Q-learning from Demonstrations](https://arxiv.org/abs/1704.03732) — Hester et al., AAAI 2018.
- [Overcoming Exploration in RL with Demonstrations](https://arxiv.org/abs/1709.10089) — Nair et al., ICRA 2018.
- [Learning Complex Dexterous Manipulation with Deep RL and Demonstrations](https://arxiv.org/abs/1709.10087) — Rajeswaran et al., RSS 2018.
- [Kickstarting Deep Reinforcement Learning](https://arxiv.org/abs/1803.03835) — Schmitt et al., 2018.
- [Residual Policy Learning](https://arxiv.org/abs/1812.06298) — Silver et al., 2018; [Residual RL for Robot Control](https://arxiv.org/abs/1812.03201) — Johannink et al., ICRA 2019.
- [AWAC: Accelerating Online RL with Offline Datasets](https://arxiv.org/abs/2006.09359) — Nair et al., 2020.
- [Jump-Start Reinforcement Learning](https://arxiv.org/abs/2204.02372) — Uchendu et al., ICML 2023. The teacher plays the start of each episode, and the learner takes over earlier and earlier.
- [Efficient Online RL with Offline Data](https://arxiv.org/abs/2302.02948) — Ball et al., ICML 2023.
- [Cal-QL: Calibrated Offline RL Pre-Training](https://arxiv.org/abs/2303.05479) — Nakamoto et al., NeurIPS 2023.
- [Imitation Bootstrapped Reinforcement Learning](https://arxiv.org/abs/2311.02198) — Hu et al., RSS 2024.
- [Imitation Is Not Enough](https://arxiv.org/abs/2212.11419) — Lu et al., 2022. Imitation plus RL for safe driving.
- [Grandmaster level in StarCraft II using multi-agent RL](https://doi.org/10.1038/s41586-019-1724-z) — Vinyals et al., Nature 2019.

### Hidden values, privileged teachers and planning while unsure (pick 5)

- [Asymmetric Actor Critic for Image-Based Robot Learning](https://arxiv.org/abs/1710.06542) — Pinto et al., RSS 2018.
- [Unbiased Asymmetric RL under Partial Observability](https://arxiv.org/abs/2105.11674) — Baisero & Amato, AAMAS 2022. When a privileged critic is safe to use.
- [Learning by Cheating](https://arxiv.org/abs/1912.12294) — Chen et al., CoRL 2019.
- [A System for General In-Hand Object Re-Orientation](https://arxiv.org/abs/2111.03043) — Chen et al., CoRL 2021. **Best Paper.**
- [Learning Quadrupedal Locomotion over Challenging Terrain](https://arxiv.org/abs/2010.11251) — Lee et al., [Science Robotics 2020](https://doi.org/10.1126/scirobotics.abc5986).
- [RMA: Rapid Motor Adaptation for Legged Robots](https://arxiv.org/abs/2107.04034) — Kumar et al., RSS 2021.
- [Learning robust perceptive locomotion for quadrupedal robots in the wild](https://arxiv.org/abs/2201.08117) — Miki et al., [Science Robotics 2022](https://doi.org/10.1126/scirobotics.abk2822). Learns when to trust its terrain sensing.
- [Preparing for the Unknown: a Universal Policy with Online System Identification](https://arxiv.org/abs/1702.02453) — Yu et al., RSS 2017.
- [Hidden Parameter Markov Decision Processes](https://arxiv.org/abs/1308.3513) — Doshi-Velez & Konidaris, IJCAI 2016.
- [VariBAD: Bayes-Adaptive Deep RL via Meta-Learning](https://arxiv.org/abs/1910.08348) — Zintgraf et al., ICLR 2020.
- [PEARL: Off-Policy Meta-RL via Probabilistic Context Variables](https://arxiv.org/abs/1903.08254) — Rakelly et al., ICML 2019.
- [RL²: Fast RL via Slow RL](https://arxiv.org/abs/1611.02779) — Duan et al., 2016.
- [Continuous Adaptation via Meta-Learning in Nonstationary and Competitive Environments](https://arxiv.org/abs/1710.03641) — Al-Shedivat et al., ICLR 2018. **Best Paper.**
- [A Tutorial on Meta-Reinforcement Learning](https://arxiv.org/abs/2301.08028) — Beck et al., 2023.
- [Domain Randomization](https://arxiv.org/abs/1703.06907) — Tobin et al., IROS 2017; [Dynamics Randomization](https://arxiv.org/abs/1710.06537) — Peng et al., ICRA 2018.
- [Learning to Walk in Minutes Using Massively Parallel Deep RL](https://arxiv.org/abs/2109.11978) — Rudin et al., CoRL 2021.

Planning while unsure:

- [Planning and acting in partially observable stochastic domains](https://doi.org/10.1016/S0004-3702%2898%2900023-X) — Kaelbling et al., Artificial Intelligence 1998.
- [Monte-Carlo Planning in Large POMDPs](https://papers.nips.cc/paper/4031-monte-carlo-planning-in-large-pomdps) — Silver & Veness, NeurIPS 2010.
- [DESPOT: Online POMDP Planning with Regularization](https://arxiv.org/abs/1609.03250) — Ye et al., JAIR 2017.
- [Online algorithms for POMDPs with continuous state, action and observation spaces](https://arxiv.org/abs/1709.06196) — Sunberg & Kochenderfer, ICAPS 2018.
- [Efficient Bayes-Adaptive RL using Sample-Based Search](https://arxiv.org/abs/1205.3109) — Guez et al., NeurIPS 2012.

### Memory, noisy sensing and navigation

- [Deep Recurrent Q-Learning for Partially Observable MDPs](https://arxiv.org/abs/1507.06527) — Hausknecht & Stone, 2015.
- [Recurrent Experience Replay in Distributed RL (R2D2)](https://openreview.net/forum?id=r1lyTjAqYX) — Kapturowski et al., ICLR 2019.
- [Recurrent Model-Free RL Can Be a Strong Baseline for Many POMDPs](https://arxiv.org/abs/2110.05038) — Ni et al., ICML 2022.
- [When Do Transformers Shine in RL? Decoupling Memory from Credit Assignment](https://arxiv.org/abs/2307.03864) — Ni et al., NeurIPS 2023. Memory helps; long-range credit assignment stays hard.
- [Deep Variational Reinforcement Learning for POMDPs](https://arxiv.org/abs/1806.02426) — Igl et al., ICML 2018.
- [Stabilizing Transformers for Reinforcement Learning](https://arxiv.org/abs/1910.06764) — Parisotto et al., ICML 2020.
- [POPGym: Benchmarking Partially Observable RL](https://arxiv.org/abs/2303.01859) — Morad et al., ICLR 2023.
- [Learning to Navigate in Complex Environments](https://arxiv.org/abs/1611.03673) — Mirowski et al., ICLR 2017.
- [DD-PPO: Near-Perfect PointGoal Navigators](https://arxiv.org/abs/1911.00357) — Wijmans et al., ICLR 2020.
- [Is Mapping Necessary for Realistic PointGoal Navigation?](https://arxiv.org/abs/2206.00997) — Partsey et al., CVPR 2022. Noisy actuation and no GPS, much like our heading drift.
- [Emergence of Maps in the Memories of Blind Navigation Agents](https://arxiv.org/abs/2301.13261) — Wijmans et al., ICLR 2023. **Outstanding Paper.**

### Delays

- [Markov decision processes with delays and asynchronous cost collection](https://doi.org/10.1109/TAC.2003.809799) — Katsikopoulos & Engelbrecht, IEEE TAC 2003. Put the commands in flight into the state.
- [Learning and planning in environments with delayed feedback](https://doi.org/10.1007/s10458-008-9056-7) — Walsh et al., JAAMAS 2009. Simulate forward to the state when the command lands.
- [Real-Time Reinforcement Learning](https://arxiv.org/abs/1911.04448) — Ramstedt & Pal, NeurIPS 2019.
- [Reinforcement Learning with Random Delays](https://arxiv.org/abs/2010.02966) — Bouteiller, Ramstedt et al., ICLR 2021.
- [Acting in Delayed Environments with Non-Stationary Markov Policies](https://arxiv.org/abs/2101.11992) — Derman et al., ICLR 2021.
- [Delay-Aware Model-Based RL for Continuous Control](https://arxiv.org/abs/2005.05440) — Chen et al., 2020.
- [Revisiting State Augmentation for RL with Stochastic Delays](https://arxiv.org/abs/2108.07555) — Nath et al., CIKM 2021.
- [Delayed Reinforcement Learning by Imitation](https://arxiv.org/abs/2205.05569) — Liotet et al., ICML 2022. Imitates an expert that acts without delay.
- [Belief Projection-Based RL for Environments with Delayed Feedback](https://neurips.cc/virtual/2023/poster/70249) — Kim et al., NeurIPS 2023.
- [Addressing Signal Delay in Deep RL](https://proceedings.iclr.cc/paper_files/paper/2024/hash/45cc967d7899616f51993b7b363d35b5-Abstract-Conference.html) — Wang et al., ICLR 2024.
- [Boosting RL with Strongly Delayed Feedback Through Auxiliary Short Delays](https://arxiv.org/abs/2402.03141) — Wu et al., ICML 2024.
- [Variational Delayed Policy Optimization](https://arxiv.org/abs/2405.14226) — Wu et al., NeurIPS 2024.

### Safety, constraints and risk (pick 1)

- [Policy invariance under reward transformations](https://people.eecs.berkeley.edu/~russell/papers/icml99-shaping.pdf) — Ng et al., ICML 1999. Shaping that cannot change the best policy.
- [Constrained Policy Optimization](https://arxiv.org/abs/1705.10528) — Achiam et al., ICML 2017.
- [Safe Reinforcement Learning via Shielding](https://arxiv.org/abs/1708.08611) — Alshiekh et al., AAAI 2018.
- [Safe Exploration in Continuous Action Spaces](https://arxiv.org/abs/1801.08757) — Dalal et al., 2018. A safety layer that corrects actions.
- [A Lyapunov-based Approach to Safe Reinforcement Learning](https://arxiv.org/abs/1805.07708) — Chow et al., NeurIPS 2018.
- [Safe Model-based RL with Stability Guarantees](https://arxiv.org/abs/1705.08551) — Berkenkamp et al., NeurIPS 2017.
- [Reward Constrained Policy Optimization](https://arxiv.org/abs/1805.11074) — Tessler et al., ICLR 2019.
- [Benchmarking Safe Exploration in Deep RL (Safety Gym)](https://cdn.openai.com/safexp-short.pdf) — Ray et al., 2019. PPO-Lagrangian.
- [Responsive Safety in RL by PID Lagrangian Methods](https://arxiv.org/abs/2007.03964) — Stooke et al., ICML 2020.
- [A Closer Look at Invalid Action Masking in Policy Gradient Algorithms](https://arxiv.org/abs/2006.14171) — Huang & Ontañón, FLAIRS 2022.
- [Saute RL: Almost Surely Safe RL Using State Augmentation](https://arxiv.org/abs/2202.06558) — Sootla et al., ICML 2022.
- [Constrained Policy Optimization via Bayesian World Models](https://arxiv.org/abs/2201.09802) — As et al., ICLR 2022.
- [Safety-Gymnasium](https://arxiv.org/abs/2310.12567) — Ji et al., NeurIPS 2023; [OmniSafe](https://arxiv.org/abs/2305.09304) — Ji et al., JMLR 2024. Tested safe-RL code.
- [A Review of Safe Reinforcement Learning](https://arxiv.org/abs/2205.10330) — Gu et al., 2022.

Risk-aware:

- [A Distributional Perspective on Reinforcement Learning](https://arxiv.org/abs/1707.06887) — Bellemare et al., ICML 2017.
- [Distributional RL with Quantile Regression](https://arxiv.org/abs/1710.10044) — Dabney et al., AAAI 2018.
- [Implicit Quantile Networks](https://arxiv.org/abs/1806.06923) — Dabney et al., ICML 2018. Can be made risk-averse.
- [Optimizing the CVaR via Sampling](https://arxiv.org/abs/1404.3862) — Tamar et al., AAAI 2015.
- [Risk-Sensitive and Robust Decision-Making: a CVaR Optimization Approach](https://arxiv.org/abs/1506.02188) — Chow et al., NeurIPS 2015.

### Exploration: ICM and better choices for our worlds

- [Curiosity-driven Exploration by Self-supervised Prediction](https://arxiv.org/abs/1705.05363) — Pathak et al., ICML 2017. ICM.
- [Large-Scale Study of Curiosity-Driven Learning](https://arxiv.org/abs/1808.04355) — Burda et al., ICLR 2019. The noisy-TV problem.
- [Exploration by Random Network Distillation](https://arxiv.org/abs/1810.12894) — Burda et al., ICLR 2019.
- [Unifying Count-Based Exploration and Intrinsic Motivation](https://arxiv.org/abs/1606.01868) — Bellemare et al., NeurIPS 2016; [#Exploration](https://arxiv.org/abs/1611.04717) — Tang et al., NeurIPS 2017.
- [Self-Supervised Exploration via Disagreement](https://arxiv.org/abs/1906.04161) — Pathak et al., ICML 2019. Ignores noise that nobody can predict.
- [RIDE: Rewarding Impact-Driven Exploration for Procedurally-Generated Environments](https://arxiv.org/abs/2002.12292) — Raileanu & Rocktäschel, ICLR 2020.
- [NovelD: A Simple yet Effective Exploration Criterion](https://proceedings.neurips.cc/paper/2021/hash/d428d070622e0f4363fceae11f4a3576-Abstract.html) — Zhang et al., NeurIPS 2021.
- [Exploration via Elliptical Episodic Bonuses](https://arxiv.org/abs/2210.05805) — Henaff et al., NeurIPS 2022.
- [A Study of Global and Episodic Bonuses for Exploration in Contextual MDPs](https://arxiv.org/abs/2306.03236) — Henaff et al., ICML 2023. Which bonus fits worlds that change every episode.
- [Never Give Up](https://arxiv.org/abs/2002.06038) — Badia et al., ICLR 2020; [Agent57](https://arxiv.org/abs/2003.13350) — Badia et al., ICML 2020.
- [BYOL-Explore](https://arxiv.org/abs/2206.08332) — Guo et al., NeurIPS 2022.
- [Go-Explore](https://arxiv.org/abs/1901.10995) — Ecoffet et al., 2019; [First return, then explore](https://arxiv.org/abs/2004.12919) — Ecoffet et al., [Nature 2021](https://doi.org/10.1038/s41586-020-03157-9).
- [The Importance of Non-Markovianity in Maximum State Entropy Exploration](https://arxiv.org/abs/2202.03060) — Mutti, De Santi & Restelli, ICML 2022. **Outstanding Paper.**

### Hierarchy, options and goal-reaching

- [Between MDPs and semi-MDPs: temporal abstraction in RL](https://doi.org/10.1016/S0004-3702%2899%2900052-1) — Sutton et al., Artificial Intelligence 1999. The theory behind our persistent target options.
- [The Option-Critic Architecture](https://arxiv.org/abs/1609.05140) — Bacon et al., AAAI 2017.
- [FeUdal Networks for Hierarchical RL](https://arxiv.org/abs/1703.01161) — Vezhnevets et al., ICML 2017.
- [Data-Efficient Hierarchical Reinforcement Learning](https://arxiv.org/abs/1805.08296) — Nachum et al., NeurIPS 2018.
- [Learning Multi-Level Hierarchies with Hindsight](https://arxiv.org/abs/1712.00948) — Levy et al., ICLR 2019.
- [Deep Hierarchical Planning from Pixels](https://arxiv.org/abs/2206.04114) — Hafner et al., NeurIPS 2022.
- [Universal Value Function Approximators](https://proceedings.mlr.press/v37/schaul15.html) — Schaul et al., ICML 2015.
- [Hindsight Experience Replay](https://arxiv.org/abs/1707.01495) — Andrychowicz et al., NeurIPS 2017. Every drive teaches how to reach the place where it ended.
- [Search on the Replay Buffer](https://arxiv.org/abs/1906.05253) — Eysenbach et al., NeurIPS 2019.
- [Contrastive Learning as Goal-Conditioned RL](https://arxiv.org/abs/2206.07568) — Eysenbach et al., NeurIPS 2022.
- [1000 Layer Networks for Self-Supervised RL](https://arxiv.org/abs/2503.14858) — Wang et al., NeurIPS 2025. **Best Paper.**
- [Value Iteration Networks](https://arxiv.org/abs/1602.02867) — Tamar et al., NIPS 2016. **Best Paper.**
- [Gated Path Planning Networks](https://arxiv.org/abs/1806.06408) — Lee et al., ICML 2018; [Neural A* Search](https://arxiv.org/abs/2009.07476) — Yonetani et al., ICML 2021.

### World models and differentiable simulation (lower priority: our model is published)

- [Mastering Diverse Domains through World Models](https://arxiv.org/abs/2301.04104) — Hafner et al., [Nature 2025](https://doi.org/10.1038/s41586-025-08744-2). DreamerV3.
- [TD-MPC2](https://arxiv.org/abs/2310.16828) — Hansen et al., ICLR 2024.
- [Deep RL in a Handful of Trials using Probabilistic Dynamics Models](https://arxiv.org/abs/1805.12114) — Chua et al., NeurIPS 2018.
- [When to Trust Your Model: Model-Based Policy Optimization](https://arxiv.org/abs/1906.08253) — Janner et al., NeurIPS 2019.
- [Do Differentiable Simulators Give Better Policy Gradients?](https://arxiv.org/abs/2202.00817) — Suh et al., ICML 2022. **Outstanding Paper.**

### Generalising to fresh worlds

- [Quantifying Generalization in Reinforcement Learning](https://arxiv.org/abs/1812.02341) — Cobbe et al., ICML 2019.
- [Assessing Generalization in Deep Reinforcement Learning](https://arxiv.org/abs/1810.12282) — Packer et al., 2018.
- [Leveraging Procedural Generation to Benchmark RL (Procgen)](https://arxiv.org/abs/1912.01588) — Cobbe et al., ICML 2020; [its NeurIPS 2020 competition](https://arxiv.org/abs/2103.15332) — Mohanty et al., 2021.
- [A Survey of Zero-shot Generalisation in Deep RL](https://arxiv.org/abs/2111.09794) — Kirk et al., JAIR 2023.
- [Prioritized Level Replay](https://arxiv.org/abs/2010.03934) — Jiang et al., ICML 2021.
- [Unsupervised Environment Design (PAIRED)](https://arxiv.org/abs/2012.02096) — Dennis et al., NeurIPS 2020; [Replay-Guided Adversarial Environment Design](https://arxiv.org/abs/2110.02439) — Jiang et al., NeurIPS 2021; [ACCEL](https://arxiv.org/abs/2203.01302) — Parker-Holder et al., ICML 2022.
- [Phasic Policy Gradient](https://arxiv.org/abs/2009.04416) — Cobbe et al., ICML 2021; [Decoupling Value and Policy for Generalization](https://arxiv.org/abs/2102.10330) — Raileanu & Fergus, ICML 2021.
- [ProcTHOR: Large-Scale Embodied AI Using Procedural Generation](https://arxiv.org/abs/2206.06994) — Deitke et al., NeurIPS 2022. **Outstanding Paper.**
- [The NetHack Learning Environment](https://arxiv.org/abs/2006.13760) — Küttler et al., NeurIPS 2020; [Craftax](https://arxiv.org/abs/2402.16801) — Matthews et al., ICML 2024.

### Making PPO work, and measuring it honestly

- [Proximal Policy Optimization Algorithms](https://arxiv.org/abs/1707.06347) — Schulman et al., 2017; [Generalized Advantage Estimation](https://arxiv.org/abs/1506.02438) — Schulman et al., ICLR 2016.
- [Asynchronous Methods for Deep RL (A3C)](https://arxiv.org/abs/1602.01783) — Mnih et al., ICML 2016. **ICML 2026 Test of Time.**
- [Continuous control with deep RL (DDPG)](https://arxiv.org/abs/1509.02971) — Lillicrap et al., ICLR 2016. **ICLR 2026 Test of Time.**
- [IMPALA](https://arxiv.org/abs/1802.01561) — Espeholt et al., ICML 2018.
- [Implementation Matters in Deep Policy Gradients](https://arxiv.org/abs/2005.12729) — Engstrom et al., ICLR 2020.
- [What Matters in On-Policy RL? A Large-Scale Empirical Study](https://arxiv.org/abs/2006.05990) — Andrychowicz et al., ICLR 2021.
- [The 37 Implementation Details of PPO](https://iclr-blog-track.github.io/2022/03/25/ppo-implementation-details/) — Huang et al., ICLR Blog Track 2022.
- [Dota 2 with Large Scale Deep RL](https://arxiv.org/abs/1912.06680) — OpenAI, 2019. PPO at scale over a long game.
- [Rainbow](https://arxiv.org/abs/1710.02298) — Hessel et al., AAAI 2018; [Dueling Network Architectures](https://arxiv.org/abs/1511.06581) — Wang et al., ICML 2016. **Best Paper.**
- [Stop Regressing: Training Value Functions via Classification](https://arxiv.org/abs/2403.03950) — Farebrother et al., ICML 2024. Steadier value learning for 0–1 scores.
- [DeepSeekMath (GRPO)](https://arxiv.org/abs/2402.03300) — Shao et al., 2024. A group of runs on the same problem as the baseline.
- [Population Based Training](https://arxiv.org/abs/1711.09846) — Jaderberg et al., 2017; [Evolution Strategies](https://arxiv.org/abs/1703.03864) — Salimans et al., 2017.
- [Deep RL that Matters](https://arxiv.org/abs/1709.06560) — Henderson et al., AAAI 2018; [Deep RL at the Edge of the Statistical Precipice](https://arxiv.org/abs/2108.13264) — Agarwal et al., NeurIPS 2021. **Outstanding Paper.**

### Long-horizon credit assignment

- [RUDDER: Return Decomposition for Delayed Rewards](https://arxiv.org/abs/1806.07857) — Arjona-Medina et al., NeurIPS 2019. Moves an end-of-episode reward back to the steps that earned it.
- [Hindsight Credit Assignment](https://arxiv.org/abs/1912.02503) — Harutyunyan et al., NeurIPS 2019.
- [Optimizing Agent Behavior over Long Time Scales by Transporting Value](https://arxiv.org/abs/1810.06721) — Hung et al., [Nature Communications 2019](https://doi.org/10.1038/s41467-019-13073-w).
- [Synthetic Returns for Long-Term Credit Assignment](https://arxiv.org/abs/2102.12425) — Raposo et al., 2021.
- [On the Expressivity of Markov Reward](https://arxiv.org/abs/2111.00876) — Abel et al., NeurIPS 2021. **Outstanding Paper.**

### Learning from logged missions (offline RL)

The farm has thousands of logged missions from the pilot, greedy and Claude's programs.

- [Conservative Q-Learning](https://arxiv.org/abs/2006.04779) — Kumar et al., NeurIPS 2020; [Implicit Q-Learning](https://arxiv.org/abs/2110.06169) — Kostrikov et al., ICLR 2022; [TD3+BC](https://arxiv.org/abs/2106.06860) — Fujimoto & Gu, NeurIPS 2021; [Decision Transformer](https://arxiv.org/abs/2106.01345) — Chen et al., NeurIPS 2021.

### LLM-guided program and heuristic search

- [Mathematical discoveries from program search with large language models (FunSearch)](https://doi.org/10.1038/s41586-023-06924-6) — Romera-Paredes et al., Nature 2023.
- [AlphaEvolve](https://arxiv.org/abs/2506.13131) — Novikov et al., 2025.
- [ReEvo: LLMs as Hyper-Heuristics with Reflective Evolution](https://arxiv.org/abs/2402.01145) — Ye et al., NeurIPS 2024. Tested on routing problems.
- [Evolution of Heuristics](https://arxiv.org/abs/2401.02051) — Liu et al., ICML 2024.
- [LLaMEA](https://arxiv.org/abs/2405.20132) — van Stein & Bäck, 2024.
- [Large Language Models as Optimizers](https://arxiv.org/abs/2309.03409) — Yang et al., ICLR 2024.
- [Eureka: Human-Level Reward Design via Coding LLMs](https://arxiv.org/abs/2310.12931) — Ma et al., ICLR 2024. An LLM writes reward functions; it could write our shaping.
- [Code as Policies](https://arxiv.org/abs/2209.07753) — Liang et al., ICRA 2023; [Voyager](https://arxiv.org/abs/2305.16291) — Wang et al., 2023.

### Training an LLM agent with RL (if an LLM, not a small network, should beat it)

- [Grounding LLMs in Interactive Environments with Online RL](https://arxiv.org/abs/2302.02662) — Carta et al., ICML 2023.
- [ArCHer: Hierarchical Multi-Turn RL for LLM Agents](https://arxiv.org/abs/2402.19446) — Zhou et al., ICML 2024.
- [RAGEN: Multi-Turn RL for LLM Agents](https://arxiv.org/abs/2504.20073) — Wang et al., 2025.
- [Group-in-Group Policy Optimization for LLM Agent Training](https://arxiv.org/abs/2505.10978) — Feng et al., 2025.
- [Reinforcement Learning for Long-Horizon Interactive LLM Agents](https://arxiv.org/abs/2502.01600) — Chen et al., 2025.

### Rovers, solar power and field RL (domain prior art)

- [Mission-level path planning and re-planning for rover exploration (TEMPEST)](https://doi.org/10.1016/j.robot.2005.09.027) — Tompkins, Stentz & Wettergreen, Robotics and Autonomous Systems 2006. Plans over space, time and solar energy together, re-plans as it goes, field-tested in the Atacama: the closest relative of our pilot.
- [Sun-Synchronous Robotic Exploration](https://doi.org/10.1177/0278364904046632) — Wettergreen et al., IJRR 2005. A solar rover that plans its route around the sun.
- [AEGIS autonomous targeting for ChemCam on Mars Science Laboratory](https://doi.org/10.1126/scirobotics.aan4582) — Francis et al., Science Robotics 2017. Curiosity picks its own science targets: over 93% hit the preferred material, against about 24% expected without it.
- [Autonomous robotics is driving Perseverance rover's progress on Mars](https://doi.org/10.1126/scirobotics.adi3099) — Verma et al., Science Robotics 2023. AutoNav evaluated 88% of the 17.7 km driven in the first Mars year.
- [Learning and prediction of slip from visual information](https://doi.org/10.1002/rob.20179) — Angelova et al., Journal of Field Robotics 2007.
- [SPOC: Deep learning-based terrain classification for Mars rover missions](https://doi.org/10.2514/6.2016-5539) — Rothrock et al., AIAA SPACE 2016.
- [Fast Path Planning for Long-Range Planetary Roving with a Hierarchical Framework and Deep RL](https://doi.org/10.3390/aerospace9020101) — Hu & Zhang, Aerospace 2022.
- [NNPP: a learned heuristic for optimal path planning on uneven terrain](https://arxiv.org/abs/2308.04792) — Ji et al., 2023.
- [Risk-aware path planning for planetary rovers on heterogeneous terrain](https://arxiv.org/abs/2303.01169) — Endo et al., 2023.
- [DRL multi-objective path planning on off-road terrain](https://arxiv.org/abs/2305.13783) — Huang et al., 2023.
- [Planetary Terrain Datasets and Benchmarks for Rover Path Planning](https://arxiv.org/abs/2512.21438) — Chancán et al., 2025.
- [Autonomous navigation of stratospheric balloons using reinforcement learning](https://doi.org/10.1038/s41586-020-2939-8) — Bellemare et al., Nature 2020. Trained in simulation, then flew 39 days over the Pacific with battery energy to conserve.
- [Outracing champion Gran Turismo drivers with deep RL](https://doi.org/10.1038/s41586-021-04357-7) — Wurman et al., Nature 2022; [Champion-level drone racing using deep RL](https://doi.org/10.1038/s41586-023-06419-4) — Kaufmann et al., Nature 2023.

## How this was checked

- **arXiv links.** All 210 IDs were fetched from the arXiv API and each registered title compared with the paper cited; all match. For one paper the arXiv title differs from the conference title, and the arXiv title is used.
- **DOIs.** All 34 were looked up on Crossref and each registered title compared; all match. Two DOIs I first had in mind were wrong and are not used.
- **Other links.** All 29 web links (OpenReview, proceedings, announcements) returned the page, and every link into this repository resolves.
- **Awards.** From the conference's own announcement page where reachable (NeurIPS 2016, 2021, 2022 and 2025; ICML 2022 and 2026; ICLR 2023 and 2026), otherwise from the named report in the table.
- **Competitions.** From the organisers' reports on arXiv.
- **Our numbers.** From `main` at `8ceec6c` (14 November, 21:16 Helsinki): `lightlag_ppo_icm/README.md`, `docs/lightlag-rl-feasible-results/README.md` and `contextual.md`, `docs/learning-campaign-results/README.md`, `docs/lightlag-rl-results/README.md`, `docs/research/2026-11-14-rl-reference-and-failures.md`, `lightlag_traverse/README.md`, `docs/lightlag-traverse-max.md`, `docs/traverse-farm.md` (including its point-of-no-return section) and the farm's row in `TEAM_STATUS.md`. Picks 1 and 2 were updated after the PPO + ICM report and Kristján's pilot reached `main`; the five picks stayed the same.
- **Not done.** I did not read every paper in full. Each "why here" line is my reading of the paper's abstract and known results, not something tested on our environments. "Every relevant paper" is not achievable; this is the core, chosen for fit to our task.
