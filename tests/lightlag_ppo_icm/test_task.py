import math
import statistics
import unittest

import numpy as np

from helpers import plain_chooser
from lightlag_ppo_icm.belief import Belief
from lightlag_ppo_icm.envs import FiveTools, finish, make_env, run_episode, share
from lightlag_ppo_icm.ground import GridGround, RectGround
from lightlag_ppo_icm.task import FIRST_DRIVE, GLOBAL, SAMPLE, WAIT, RoverTask, TaskConfig

CONFIG = TaskConfig()


class CountingTools:
    """The five public tools and nothing else: any other attribute is an AttributeError."""

    __slots__ = ("_tools", "calls")

    def __init__(self, env):
        object.__setattr__(self, "_tools", FiveTools(env))
        object.__setattr__(self, "calls", {})

    def __getattr__(self, name):
        if name not in ("rules", "map", "telemetry_log", "uplink", "advance"):
            raise AttributeError(name)
        self.calls[name] = self.calls.get(name, 0) + 1
        return getattr(self._tools, name)


def play(spec, seed, chooser=None, rng=None):
    """One episode; returns (task, environment, result, observations, belief at every decision)."""
    env = make_env(spec, seed)
    tools = CountingTools(env)
    task = RoverTask(tools, CONFIG)
    chooser = chooser or (lambda obs: int(rng.integers(CONFIG.n_actions)))
    seen, beliefs = [], []

    def choose(obs):
        seen.append(obs)
        slot = max(task.tick + task.delay + 1, task.reserved + 1)
        beliefs.append((slot,) + tuple(task._predict(slot)[0].m[:2]))
        return chooser(obs)

    task.play(choose)
    return task, env, finish(env), seen, beliefs, tools


class ObservationTests(unittest.TestCase):
    def test_fixed_size_finite_and_bounded_on_every_environment_family(self):
        self.assertEqual(CONFIG.obs_dim, 138)
        self.assertEqual(CONFIG.n_actions, 50)
        rng = np.random.default_rng(0)
        for spec in ("max", "max_rocks", "rush", "noisy", "rush_noisy@troy_crust+relay_pass"):
            for chooser in (None, plain_chooser(CONFIG)):
                _, _, _, seen, _, _ = play(spec, 300001, chooser, rng)
                obs = np.array(seen)
                self.assertEqual(obs.shape[1], CONFIG.obs_dim, spec)
                self.assertTrue(np.isfinite(obs).all(), spec)
                self.assertLessEqual(float(np.abs(obs).max()), 1.0 + 1e-9, spec)

    def test_only_the_five_public_tools_are_used(self):
        task, _, _, _, _, tools = play("max", 300002, plain_chooser(CONFIG))
        self.assertEqual(set(tools.calls) - {"rules", "map", "telemetry_log", "uplink", "advance"}, set())
        self.assertEqual(tools.calls["rules"], 1)
        self.assertEqual(tools.calls["telemetry_log"], 1)
        self.assertEqual(tools.calls["uplink"], len(task.decisions))
        self.assertEqual(tools.calls["advance"], task.horizon)

    def test_same_seed_and_actions_give_the_same_observations(self):
        runs = [play("max", 300003, None, np.random.default_rng(4))[3] for _ in range(2)]
        np.testing.assert_array_equal(np.array(runs[0]), np.array(runs[1]))
        other = play("max", 300004, None, np.random.default_rng(4))[3]
        self.assertFalse(np.array_equal(np.array(runs[0]), np.array(other)))

    def test_actions_decode_to_valid_commands(self):
        task = RoverTask(FiveTools(make_env("max", 300000)), CONFIG)
        self.assertEqual(task.command(WAIT), {"action": "wait"})
        self.assertEqual(task.command(SAMPLE), {"action": "sample"})
        limit = task.rules["max_metres_per_drive"]
        commands = [task.command(a) for a in range(FIRST_DRIVE, CONFIG.n_actions)]
        self.assertEqual(sorted({c["heading_deg"] for c in commands}), [i * 22.5 for i in range(16)])
        self.assertEqual(sorted({c["metres"] for c in commands}), [0.25 * limit, 0.5 * limit, limit])
        for bad in (-1, CONFIG.n_actions):
            with self.assertRaises(ValueError):
                task.command(bad)
        self.assertEqual(TaskConfig.from_dict(CONFIG.to_dict()), CONFIG)

    def test_curiosity_is_not_shown_the_agents_own_last_action(self):
        shown = set(CONFIG.curiosity_inputs)
        self.assertEqual(len(shown), len(CONFIG.curiosity_inputs))
        self.assertTrue(shown.isdisjoint(range(13, 21)))          # the link, the previous command, the heading
        self.assertIn(22, shown)                                  # the value sampled so far
        self.assertTrue(shown.isdisjoint((2, 3, 4, 5, 8, 9, 10, 11)))   # belief and stop bookkeeping
        self.assertTrue(set(range(GLOBAL, CONFIG.obs_dim)) <= shown)
        # Two different commands sent while the rover stands still must look the same to curiosity
        # until one of them has moved it: the previous-command entries are the only difference.
        observations = []
        for action in (WAIT, FIRST_DRIVE + 5):
            task = RoverTask(FiveTools(make_env("rush", 300000)), CONFIG)
            slot = task._send(action) + 1
            observations.append(task.observe(slot))
        hidden = [i for i in range(CONFIG.obs_dim) if i not in shown]
        self.assertFalse(np.array_equal(observations[0][hidden], observations[1][hidden]))


class SchedulingTests(unittest.TestCase):
    def test_every_slot_is_decided_exactly_once(self):
        # On an open link one slot per tick; with relay passes (the max env) the last open tick
        # decides every slot up to the next pass. Either way no slot is left empty or filled twice.
        for spec in ("rush", "max", "rush_noisy@relay_pass"):
            task, env, _, _, _, _ = play(spec, 300005, plain_chooser(CONFIG))
            slots = [slot for slot, _ in task.decisions]
            self.assertEqual(slots, list(range(task.delay + 1, task.horizon + 1)), spec)
            self.assertEqual([c["execute_tick"] for c in env.replay()["commands"]], slots, spec)

    def test_relay_passes_batch_the_decisions(self):
        task, env, _, _, _, _ = play("max", 300006, plain_chooser(CONFIG))
        self.assertEqual(task.passes, (8, 4))
        sent = [c["sent_tick"] for c in env.replay()["commands"]]
        self.assertTrue(all(tick % 8 < 4 for tick in sent))           # nothing is sent on a closed link
        self.assertEqual(sent[:8], [0, 1, 2, 3, 3, 3, 3, 3])         # five slots on the last open tick

    def test_delay_zero_and_other_delays(self):
        for delay in (0, 5):
            env = make_env("rush", 300007, delay)
            task = RoverTask(FiveTools(env), CONFIG)
            task.play(plain_chooser(CONFIG))
            self.assertEqual([s for s, _ in task.decisions], list(range(delay + 1, task.horizon + 1)))


class RewardTests(unittest.TestCase):
    def test_rewards_add_up_to_the_official_share(self):
        shares = []
        for spec, seed in (("rush", 300008), ("rush", 300009), ("rush_noisy", 300010), ("max", 300011)):
            task, _, result, _, _, _ = play(spec, seed, plain_chooser(CONFIG))
            rewards = task.rewards(result)
            self.assertEqual(len(rewards), len(task.decisions))
            self.assertAlmostEqual(float(rewards.sum()), share(result), places=9)
            shares.append(share(result))
        self.assertGreater(max(shares), 0.2)     # the check is not vacuous

    def test_a_sample_is_paid_at_its_own_decision_and_death_takes_it_back(self):
        task, _, result, _, _, _ = play("rush", 300008, plain_chooser(CONFIG))
        rewards = task.rewards(result)
        total = result["max_available_value"]
        by_slot = {slot: i for i, (slot, _) in enumerate(task.decisions)}
        self.assertTrue(result["samples"])
        for sample in result["samples"]:
            i = by_slot[sample["tick"]]
            self.assertEqual(task.decisions[i][1], SAMPLE)
            if i != len(rewards) - 1:
                self.assertAlmostEqual(float(rewards[i]), 0.5 * sample["credited_value"] / total, places=9)
        dead = dict(result, survival_factor=0.0, raw_score=0.0)
        self.assertAlmostEqual(float(task.rewards(dead).sum()), 0.0, places=9)

    def test_the_pull_toward_home_moves_reward_earlier_without_changing_the_total(self):
        for spec, seed in (("rush", 300008), ("rush_noisy", 300010), ("max", 300011)):
            task, _, result, _, _, _ = play(spec, seed, plain_chooser(CONFIG))
            plain = task.rewards(result)
            self.assertEqual(len(task.trace), len(task.decisions))
            for strength in (1.0, 4.0):
                pulled = task.rewards(result, home_pull=strength)
                self.assertAlmostEqual(float(pulled.sum()), share(result), places=9, msg=spec)
                self.assertAlmostEqual(float(pulled.sum()), float(plain.sum()), places=9)
            np.testing.assert_allclose(task.rewards(result, home_pull=4.0) - plain,
                                       4.0 * (task.rewards(result, home_pull=1.0) - plain), atol=1e-12)
        # rush 300008: the rule samples, then drives home. On the way home the pull pays, and the
        # last decision, which without it carries the whole bonus for being home, carries less.
        task, _, result, _, _, _ = play("rush", 300008, plain_chooser(CONFIG))
        self.assertTrue(result["at_base"] and result["samples"])
        plain, pulled = task.rewards(result), task.rewards(result, home_pull=1.0)
        last_sample = max(i for i, (_, action) in enumerate(task.decisions) if action == SAMPLE)
        distances = [d for _, d in task.trace]
        approaching = [i for i in range(last_sample + 1, len(distances) - 1) if distances[i + 1] < distances[i] - 0.5]
        self.assertTrue(approaching)
        self.assertTrue(all(pulled[i] > plain[i] for i in approaching))
        self.assertLess(pulled[-1], plain[-1])
        # No value sampled: nothing to pull with.
        task, _, result, _, _, _ = play("rush", 300008, lambda obs: FIRST_DRIVE)
        np.testing.assert_array_equal(task.rewards(result, home_pull=1.0), task.rewards(result))

    def test_the_plain_chooser_scores_from_the_observation_alone(self):
        rows = [run_episode("rush", seed, plain_chooser(CONFIG)) for seed in range(300012, 300020)]
        self.assertGreater(statistics.fmean(r["share"] for r in rows), 0.35)
        rows = [run_episode("max", seed, plain_chooser(CONFIG)) for seed in range(300012, 300020)]
        self.assertGreater(statistics.fmean(r["share"] for r in rows), 0.05)


class GuardTests(unittest.TestCase):
    def spend(self, spec, seed, guard):
        env = make_env(spec, seed)
        task = RoverTask(FiveTools(env), TaskConfig(guard=guard))
        rng = np.random.default_rng(seed)
        task.play(lambda obs: int(rng.integers(FIRST_DRIVE, CONFIG.n_actions)))    # nothing but drives
        return task, finish(env)

    def test_without_the_guard_a_driver_empties_the_battery_and_with_it_it_survives(self):
        # On the max env a rover that only drives often ends up held by the slip check, which saves it.
        for spec, at_least in (("rush", 5), ("rush_noisy", 5), ("max", 2)):
            dead = [not self.spend(spec, seed, False)[1]["alive"] for seed in range(300040, 300046)]
            self.assertGreaterEqual(sum(dead), at_least, spec)
            replaced = 0
            for seed in range(300040, 300052):
                task, result = self.spend(spec, seed, True)
                self.assertTrue(result["alive"], (spec, seed))
                self.assertEqual(len(task.decisions), task.horizon - task.delay)   # a decision per slot still
                replaced += task.guarded
            self.assertGreater(replaced, 50, spec)     # a rover stuck at a hazard needs no guard; most do

    def test_the_guard_prices_what_telemetry_has_not_confirmed_at_the_dearest_rate(self):
        ground = RectGround(dict(RULES, turn_cost_per_degree=0.01), MAP)
        self.assertAlmostEqual(ground.worst_energy(20.0, 20.0, 0.0, 2.0, 0.0), 4.0)      # sand under every metre
        self.assertAlmostEqual(ground.worst_energy(20.0, 20.0, 0.0, 2.0, 90.0), 4.0 + 1.8)
        task = RoverTask(FiveTools(make_env("max", 300041)), CONFIG)
        self.assertAlmostEqual(task.scale_error, 0.2)
        self.assertAlmostEqual(task._worst(0.0, 2.0, 20.0, 20.0, 0.0), 2.0 * 1.2 * 2.0)   # and the biggest wheels

    def test_the_guard_leaves_an_affordable_plan_alone(self):
        # Six short drives and a sample, then waiting: far inside the battery.
        plan = [FIRST_DRIVE + 3 * 4, FIRST_DRIVE + 3 * 4 + 1, SAMPLE, FIRST_DRIVE + 3 * 12, FIRST_DRIVE + 3 * 12 + 1,
                FIRST_DRIVE, FIRST_DRIVE + 3 * 8]
        commands = []
        for guard in (True, False):
            env = make_env("rush", 300008)
            task = RoverTask(FiveTools(env), TaskConfig(guard=guard))
            steps = iter(plan)
            task.play(lambda obs: next(steps, WAIT))
            finish(env)
            self.assertEqual(task.guarded, 0)
            commands.append([c["command"] for c in env.replay()["commands"]])
        self.assertEqual(commands[0], commands[1])
        self.assertEqual(sum(c["action"] == "drive" for c in commands[0]), 6)
        self.assertEqual(TaskConfig.from_dict(TaskConfig(guard=False).to_dict()).guard, False)


class BookkeepingTests(unittest.TestCase):
    def test_the_value_sampled_so_far_follows_the_evaluators_count(self):
        for spec, seed in (("rush", 300008), ("rush_noisy", 300010), ("max", 300013)):
            task, _, result, seen, _, _ = play(spec, seed, plain_chooser(CONFIG))
            known = sum(t[2] for t in task.targets.values())
            # After the last telemetry every sample the evaluator credits is known to the adapter,
            # except those whose packets are still on their way at the horizon.
            late = {s["target_id"] for s in result["samples"] if s["tick"] > task.filter_tick}
            credited = sum(s["credited_value"] for s in result["samples"] if s["target_id"] not in late)
            mine = sum(v for tid, v in task.credited.items() if tid in task.sampled)
            self.assertAlmostEqual(mine, credited, places=9, msg=spec)
            banked = np.array(seen)[:, 22]
            self.assertTrue((np.diff(banked) > -0.34).all())      # it only falls when a sample is seen to have missed
            self.assertLessEqual(banked.max(), 1.0)
            if result["samples"]:
                self.assertGreater(banked.max(), 0.0)
            self.assertLessEqual(mine / known, 1.0)


class BeliefTests(unittest.TestCase):
    def errors(self, spec, seeds):
        out = []
        for seed in seeds:
            _, env, _, _, beliefs, _ = play(spec, seed, plain_chooser(CONFIG))
            states = env.replay()["states"]       # the evaluator's truth: where the rover really was
            out += [math.hypot(x - states[slot - 1]["position"][0], y - states[slot - 1]["position"][1])
                    for slot, x, y in beliefs if states[slot - 1]["alive"]]
        return sorted(out)

    def test_the_expected_position_tracks_the_rover(self):
        clean = self.errors("rush", range(300020, 300024))
        self.assertLess(clean[len(clean) // 2], 0.15)
        noisy = self.errors("rush_noisy", range(300020, 300024))
        self.assertLess(noisy[len(noisy) // 2], 0.6)
        hard = self.errors("max", range(300020, 300026))
        self.assertLess(hard[len(hard) // 2], 1.5)

    def test_the_filter_learns_a_scale_and_a_rotation_from_fixes(self):
        rng = np.random.default_rng(3)
        scale, turn = 1.15, math.radians(9.0)
        truth = complex(20.0, 20.0)
        belief = Belief(20.0, 20.0, 0.2 ** 2 / 3 + 0.05 ** 2, math.radians(15.0) ** 2 / 3)
        for _ in range(40):
            heading = rng.uniform(0, 2 * math.pi)
            d = 2.0 * complex(math.cos(heading), math.sin(heading))
            truth += d * scale * complex(math.cos(turn), math.sin(turn))
            belief.move(d.real, d.imag, 1e-4, 1e-6, 1e-6)
            self.assertTrue(belief.fix(truth.real + rng.normal(0, 0.3), truth.imag + rng.normal(0, 0.3), 0.3 ** 2))
        self.assertAlmostEqual(math.hypot(belief.m[2], belief.m[3]), scale, delta=0.03)
        self.assertAlmostEqual(math.atan2(belief.m[3], belief.m[2]), turn, delta=0.03)
        self.assertLess(math.hypot(belief.m[0] - truth.real, belief.m[1] - truth.imag), 0.4)

    def test_the_gate_holds_back_a_wild_fix(self):
        belief = Belief(5.0, 5.0, 0.01, 0.01)
        belief.move(1.0, 0.0, 0.01, 1e-6, 1e-6)
        before = belief.m.copy()
        self.assertFalse(belief.fix(15.0, 5.0, 0.3 ** 2, gate=9.21))
        np.testing.assert_array_equal(belief.m, before)
        self.assertTrue(belief.fix(6.1, 5.0, 0.3 ** 2, gate=9.21))
        copy = belief.copy()
        copy.move(1.0, 1.0, 0.1, 0.0, 0.0)
        self.assertFalse(np.array_equal(copy.m, belief.m))

    def test_a_dead_rover_is_not_expected_to_move(self):
        task = RoverTask(FiveTools(make_env("rush", 300030)), TaskConfig(guard=False))
        full_east = FIRST_DRIVE + len(CONFIG.metres) - 1          # heading 0, the longest drive
        task.play(lambda obs: full_east if obs[0] < 0.3 else SAMPLE)   # drive and sample until flat
        self.assertFalse(task.alive)
        kf, _, battery, _, _, alive, _ = task._predict(task.horizon + 1)
        self.assertFalse(alive)
        self.assertEqual(battery, 0.0)
        np.testing.assert_array_equal(kf.m, task.kf.m)


RULES = {"slip_ranges": {"bedrock": [0.0, 0.05], "sand": [0.2, 0.45]}, "drive_cost": 1.0, "idle_cost": 0.5,
         "terrain_drive_multipliers": {"bedrock": 1.0, "sand": 2.0}, "drive_integration_metres": 0.1}
MAP = {"width": 40.0, "height": 40.0, "default_terrain": "bedrock",
       "sand": [{"x1": 24.0, "y1": 0.0, "x2": 30.0, "y2": 40.0}],
       "hazards": [{"x1": 18.0, "y1": 23.0, "x2": 22.0, "y2": 24.0}],
       "crust_regions": [{"x1": 10.0, "y1": 18.0, "x2": 15.0, "y2": 22.0}]}
EAST_NORTH_WEST_SOUTH = (np.array([1.0, 0.0, -1.0, 0.0]), np.array([0.0, 1.0, 0.0, -1.0]))


class GroundTests(unittest.TestCase):
    def test_rays_measure_the_way_to_a_stop_to_soft_and_to_risky_ground(self):
        ground = RectGround(RULES, MAP)
        free, firm, safe = ground.rays(20.0, 20.0, *EAST_NORTH_WEST_SOUTH, 10.0)
        np.testing.assert_allclose(free, [1.0, 0.3, 1.0, 1.0])       # the hazard is 3 m north
        np.testing.assert_allclose(firm, [0.4, 1.0, 1.0, 1.0])       # the sand is 4 m east
        np.testing.assert_allclose(safe, [1.0, 1.0, 0.5, 1.0])       # the crust is 5 m west
        free, firm, _ = ground.rays(38.0, 20.0, *EAST_NORTH_WEST_SOUTH, 10.0)
        np.testing.assert_allclose(free, [0.2, 1.0, 1.0, 1.0])       # the map edge is 2 m east
        np.testing.assert_allclose(firm[2], 0.8)                     # the sand is 8 m west
        self.assertEqual(ground.rays(26.0, 20.0, *EAST_NORTH_WEST_SOUTH, 10.0)[1].tolist(), [0.0] * 4)
        self.assertTrue(ground.soft_at(26.0, 20.0) and ground.risky_at(12.0, 20.0))
        self.assertFalse(ground.soft_at(20.0, 20.0) or ground.risky_at(20.0, 20.0))

    def test_an_expected_drive_uses_the_middle_of_the_slip_range_and_stops_where_the_rules_stop_it(self):
        ground = RectGround(RULES, MAP)
        dx, dy, wheel, energy, stopped = ground.advance(20.0, 20.0, 180.0, 2.0)
        self.assertAlmostEqual(dx, -2.0 * 0.975)
        self.assertAlmostEqual(dy, 0.0, places=9)
        self.assertEqual((wheel, energy, stopped), (2.0, 2.0, False))
        dx, dy, wheel, energy, stopped = ground.advance(20.0, 20.0, 90.0, 5.0)     # into the hazard
        self.assertTrue(stopped)
        self.assertLess(dy, 3.0)
        self.assertEqual(ground.advance(20.0, 20.0, 90.0, 5.0, stops=False)[2], 5.0)   # what telemetry reported ran
        self.assertTrue(ground.advance(38.0, 20.0, 0.0, 5.0)[4])                    # off the map
        on_sand = ground.advance(26.0, 20.0, 90.0, 1.0)
        self.assertAlmostEqual(on_sand[1], 0.675)
        self.assertAlmostEqual(on_sand[3], 2.0)
        turned = ground.advance(20.0, 20.0, 0.0, 1.0, gr=1.0, gi=0.2)               # the learned gain turns the track
        self.assertAlmostEqual(turned[0], 0.975)                                      # the commanded displacement is kept

    def test_the_slip_check_ends_a_drive_on_a_steep_dune_face(self):
        rules = dict(RULES, onboard_slip_check={"limit": 0.4}, dune_slip={"slip_per_degree": [0.01, 0.03]},
                     turn_cost_per_degree=0.01)
        dunes = dict(MAP, dune_faces=[{"x1": 24.0, "y1": 0.0, "x2": 30.0, "y2": 40.0, "slope_deg": 10.0}])
        ground = RectGround(rules, dunes)
        self.assertAlmostEqual(ground.slip_at(26.0, 20.0), 0.325 + 0.02 * 10.0)
        dx, dy, wheel, energy, stopped = ground.advance(26.0, 20.0, 90.0, 2.0)
        self.assertTrue(stopped)
        self.assertAlmostEqual(wheel, 0.1)
        self.assertFalse(ground.advance(20.0, 20.0, 180.0, 2.0)[4])
        self.assertAlmostEqual(ground.turn_energy(90.0, 20.0, 20.0), 0.9)
        self.assertAlmostEqual(ground.turn_energy(90.0, 26.0, 20.0), 1.8)

    def test_the_height_grid_of_the_traverse(self):
        physics = {"segment_m": 0.25, "max_tilt": 0.36, "slip_max": 0.95, "climb_cost_per_m": 2.0,
                   "slip_base_ranges": {"bedrock": [0.01, 0.05], "regolith": [0.05, 0.12], "sand": [0.15, 0.35]},
                   "slip_grade_gain": {"bedrock": 0.8, "regolith": 1.5, "sand": 3.5},
                   "drive_cost_per_wheel_m": {"bedrock": 0.3, "regolith": 0.36, "sand": 0.5}}
        rules = {"physics": physics, "idle_cost": 0.15, "solar_peak": 2.8, "solar_efficiency_range": [0.8, 1.0],
                 "sun_margin_ticks": 56, "max_ticks": 420}
        # 5 m cells, 30 m by 20 m; a wall rising 5 m over one cell at x = 20..25, sand in the first column.
        heights = [[0, 0, 0, 0, 0, 500, 500] for _ in range(5)]
        public = {"width": 30.0, "height": 20.0, "cell_m": 5.0, "elevation_cm": heights,
                  "terrain": ["sbbbbb"] * 4, "terrain_codes": {"b": "bedrock", "s": "sand"}}
        ground = GridGround(rules, public)
        free, firm, safe = ground.rays(12.0, 10.0, *EAST_NORTH_WEST_SOUTH, 10.0)
        self.assertLess(free[0], 1.0)                 # the wall to the east is too steep
        self.assertAlmostEqual(free[1], 1.0)          # north: flat, though the edge is 10 m away
        self.assertLess(firm[2], 1.0)                 # sand to the west
        self.assertAlmostEqual(firm[0], 1.0)
        self.assertEqual(safe.tolist(), [1.0] * 4)
        self.assertTrue(ground.soft_at(2.0, 10.0))
        self.assertFalse(ground.soft_at(12.0, 10.0))
        flat = ground.advance(12.0, 10.0, 90.0, 4.0)
        self.assertAlmostEqual(flat[1], 4.0 * 0.97)
        self.assertFalse(flat[4])
        self.assertTrue(ground.advance(12.0, 10.0, 0.0, 12.0)[4])     # stopped at the wall
        self.assertLess(ground.tick_energy(210), 0.0)                 # at noon the sun gives more than idling costs


class EnvironmentTests(unittest.TestCase):
    def test_names(self):
        from lightlag_dynamic.biomes.nogps import NoGpsEnvironment
        self.assertIsInstance(make_env("max", 1), NoGpsEnvironment)
        self.assertIn("gale_rock_field", make_env("max_rocks", 1).biome_ids)
        self.assertEqual(make_env("rush", 1, delay=5).rules()["delay_ticks"], 5)
        self.assertEqual(make_env("rush_noisy@troy_crust", 1).biome_ids, ("troy_crust",))
        self.assertEqual(make_env("traverse", 1).rules()["version"], "lightlag-traverse-v1")
        self.assertEqual(make_env("traverse_max", 1).rules()["map_option"], "max")
        with self.assertRaises(ValueError):
            make_env("traverse", 1, delay=5)       # the traverse fixes its own delay
        for bad in ("moon", "rush@atlantis"):
            with self.assertRaises(ValueError):
                make_env(bad, 1)

    def test_the_traverse_and_its_max_map_play_through_the_same_adapter(self):
        for spec in ("traverse", "traverse_max"):
            env = make_env(spec, 300031)
            task = RoverTask(FiveTools(env), CONFIG)
            rng = np.random.default_rng(1)
            seen = []

            def choose(obs):
                seen.append(obs)
                return int(rng.integers(CONFIG.n_actions)) if obs[0] < 0.12 else WAIT

            task.play(choose)
            result = finish(env)
            obs = np.array(seen)
            self.assertEqual(obs.shape, (417, CONFIG.obs_dim), spec)
            self.assertTrue(np.isfinite(obs).all(), spec)
            self.assertLessEqual(float(np.abs(obs).max()), 1.0 + 1e-9, spec)
            self.assertAlmostEqual(float(task.rewards(result).sum()), share(result), places=9)
            self.assertGreater(obs[:, GLOBAL + 7].max(), 0.0)    # a target is listed (BASE is 7 wide)
            self.assertEqual([slot for slot, _ in task.decisions], list(range(4, 421)), spec)
        self.assertEqual(task.passes, (8, 4))          # the MAX map's relay passes are read
        self.assertAlmostEqual(task.scale_error, 0.2)  # and its wheels of a hidden size
        self.assertIsNotNone(task.gate)                # and its wild fixes


if __name__ == "__main__":
    unittest.main()
