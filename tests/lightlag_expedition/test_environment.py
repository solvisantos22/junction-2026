"""Information boundaries, atomic reservations, scoring and inherited physics."""

from copy import deepcopy
import unittest

from lightlag import Config
from lightlag_dynamic.environment import DynamicEnvironment
from lightlag_expedition import ExpeditionEnvironment
from lightlag_expedition.missions import make_mission
from lightlag_expedition.model import REGIONS


RICH = dict.fromkeys(REGIONS, "rich")
POOR = dict.fromkeys(REGIONS, "poor")


def finish(env):
    while not env.advance(5)["episode_complete"]:
        pass
    return env.evaluate()


def events(env, kind):
    return [event for packet in env.telemetry_log() for event in packet["events"] if event["type"] == kind]


def without_science(packets):
    packets = deepcopy(packets)
    for packet in packets:
        packet["events"] = [event for event in packet["events"] if event["type"] != "region_quality"]
        for event in packet["events"]:
            if event["type"] == "target_discovered":
                event["target"].pop("region", None)
                event["target"].pop("base_value", None)
    return packets


class PublicContractTests(unittest.TestCase):
    def test_defaults_and_truthful_public_distribution(self):
        env = ExpeditionEnvironment()
        rules = env.rules()
        self.assertEqual((rules["max_ticks"], rules["delay_ticks"], rules["initial_battery"]), (60, 3, 100))
        self.assertEqual((rules["idle_cost"], rules["drive_cost"], rules["sample_cost"]), (.5, 1, 3))
        self.assertEqual((rules["target_radius"], rules["base_radius"]), (.75, .75))
        self.assertEqual(rules["mission_profile"], "expedition")
        self.assertEqual(rules["map_generator"]["name"], "expedition-regional-v1")
        self.assertEqual(rules["science"]["regions"], {"r1": {"prior_rich": .9}, "r2": {"prior_rich": .35}, "r3": {"prior_rich": .5}})
        self.assertEqual(rules["science"]["inspection_accuracy"], .9)
        self.assertNotIn("public_qualities", rules["science"])
        self.assertEqual(len(env.map()["targets"]), 6)
        for target in env.map()["targets"]:
            self.assertEqual(target["value"], target["base_value"])
            self.assertIn(target["region"], REGIONS)

    def test_no_quality_leak_until_an_observation(self):
        rich = ExpeditionEnvironment(seed=17, mission_seed=31, quality_fixture=RICH, signal_fixture=POOR)
        poor = ExpeditionEnvironment(seed=17, mission_seed=31, quality_fixture=POOR, signal_fixture=POOR)
        for _ in range(6):
            self.assertEqual(rich.rules(), poor.rules())
            self.assertEqual(rich.map(), poor.map())
            self.assertEqual(rich.telemetry_log(), poor.telemetry_log())
            self.assertEqual(rich.advance(5), poor.advance(5))
        for env in (rich, poor):
            with self.assertRaises(ValueError):
                env.evaluate()
            with self.assertRaises(ValueError):
                env.replay()

    def test_public_control_changes_disclosure_only(self):
        hidden = ExpeditionEnvironment(seed=9, mission_seed=2)
        public = ExpeditionEnvironment(seed=9, mission_seed=2, visibility="public")
        self.assertEqual(public.rules()["science"]["public_qualities"], hidden._qualities)
        for env in (hidden, public):
            env.uplink([{"action": "inspect", "region": "r2"},
                        {"action": "drive", "heading_deg": 70, "metres": 2}, {"action": "sample"}])
        for _ in range(12):
            self.assertEqual(hidden.advance(5), public.advance(5))
            self.assertEqual(hidden.map(), public.map())
        self.assertEqual(hidden.evaluate(), public.evaluate())
        self.assertEqual(hidden.replay()["states"], public.replay()["states"])
        self.assertEqual(hidden._signals, public._signals)

    def test_episode_rng_does_not_change_geometry_and_map_rng_does_not_change_latents(self):
        one = ExpeditionEnvironment(seed=4, mission_seed=7)
        two = ExpeditionEnvironment(seed=99, mission_seed=7)
        three = ExpeditionEnvironment(seed=4, mission_seed=8)
        self.assertEqual(one.map(), two.map())
        self.assertNotEqual(one.map(), three.map())
        self.assertEqual((one._qualities, one._signals, one._slip, one._initial_heading_bias),
                         (three._qualities, three._signals, three._slip, three._initial_heading_bias))

    def test_discoveries_only_arrive_after_normal_delay(self):
        env = ExpeditionEnvironment()
        for tick in range(1, 27):
            env.advance()
            ids = {target["id"] for target in env.map()["targets"]}
            self.assertEqual("d1" in ids, tick >= 13)
            self.assertEqual("d2" in ids, tick >= 25)
        found = events(env, "target_discovered")
        self.assertEqual([event["target"]["region"] for event in found], ["r2", "r3"])
        self.assertTrue(all("quality" not in event["target"] for event in found))

    def test_public_returns_and_constructor_fixtures_are_copy_safe(self):
        quality, signal = dict(RICH), dict(POOR)
        env = ExpeditionEnvironment(visibility="public", quality_fixture=quality, signal_fixture=signal)
        quality["r1"], signal["r1"] = "poor", "rich"
        rules = env.rules()
        rules["science"]["public_qualities"]["r1"] = "poor"
        rules["map_generator"]["regions"]["r1"]["distance_m"][0] = -9
        public_map = env.map()
        public_map["targets"][0]["base_value"] = -99
        brief = env.telemetry_log()
        brief[0]["position"][0] = -99
        command = {"action": "inspect", "region": "r1"}
        ack = env.uplink([command])
        command["region"] = "r2"
        ack[0]["command"]["region"] = "r3"
        self.assertEqual(env.rules()["science"]["public_qualities"], RICH)
        self.assertEqual(env.rules()["map_generator"]["regions"]["r1"]["distance_m"], [4, 7])
        self.assertGreater(env.map()["targets"][0]["base_value"], 0)
        self.assertEqual(env.telemetry_log()[0]["position"], [20, 20])
        finish(env)
        self.assertEqual(events(env, "inspection_result"), [{"type": "inspection_result", "region": "r1", "signal": "poor"}])
        replay = env.replay()
        replay["expedition"]["qualities"]["r1"] = "poor"
        replay["states"][0]["position"][0] = -99
        self.assertEqual(env.replay()["expedition"]["qualities"], RICH)
        self.assertEqual(env.replay()["states"][0]["position"], [20, 20])

    def test_strict_constructor_inputs(self):
        cases = [{"seed": True}, {"mission_seed": 1.5}, {"visibility": "oracle"},
                 {"quality_fixture": {"r1": "rich"}}, {"signal_fixture": {**POOR, "r2": "unknown"}},
                 {"quality_fixture": {**RICH, "extra": "rich"}}]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ExpeditionEnvironment(**kwargs)


class InspectionTests(unittest.TestCase):
    def test_inspection_executes_fifo_and_signal_arrives_at_tick_seven(self):
        env = ExpeditionEnvironment(quality_fixture=RICH, signal_fixture=POOR)
        ack = env.uplink([{"action": "inspect", "region": "r1"}, {"action": "wait"}])
        self.assertEqual([row["execute_tick"] for row in ack], [4, 5])
        for tick in range(1, 8):
            env.advance()
            self.assertEqual(len(events(env, "inspection_result")), int(tick >= 7))
        result = events(env, "inspection_result")[0]
        self.assertEqual(result, {"type": "inspection_result", "region": "r1", "signal": "poor"})
        self.assertEqual(events(env, "region_quality"), [])
        self.assertEqual(env._battery, 100 - 7 * .5 - 2)
        packet = next(p for p in env.telemetry_log() if result in p["events"])
        self.assertEqual((packet["tick"], packet["received_tick"]), (4, 7))

    def test_all_batch_failures_are_atomic(self):
        env = ExpeditionEnvironment()
        invalid = [
            [{"action": "inspect", "region": "r1"}] * 2,
            [{"action": "inspect", "region": region} for region in REGIONS],
            [{"action": "inspect", "region": "r1"}, {"action": "drive", "heading_deg": 0, "metres": 6}],
            [{"action": "inspect", "region": "r1", "extra": 1}],
            [{"action": "inspect", "region": []}], [{"action": "inspect", "region": "r4"}],
            [{"action": "inspect"}], [{"action": "sample", "region": "r1"}],
            [{"action": "drive", "heading_deg": float("nan"), "metres": 1}], [], None,
        ]
        for commands in invalid:
            before = deepcopy(env.__dict__)
            with self.subTest(commands=commands), self.assertRaises(ValueError):
                env.uplink(commands)
            self.assertEqual(env.__dict__, before)
        env.uplink([{"action": "inspect", "region": "r1"}, {"action": "inspect", "region": "r2"}])
        for region in REGIONS:
            before = deepcopy(env.__dict__)
            with self.assertRaises(ValueError):
                env.uplink([{"action": "wait"}, {"action": "inspect", "region": region}])
            self.assertEqual(env.__dict__, before)

    def test_horizon_rejection_does_not_reserve_budget(self):
        env = ExpeditionEnvironment(config=Config(max_ticks=4))
        before = deepcopy(env.__dict__)
        with self.assertRaises(ValueError):
            env.uplink([{"action": "inspect", "region": "r1"}, {"action": "wait"}])
        self.assertEqual(env.__dict__, before)
        env.uplink([{"action": "inspect", "region": "r1"}])
        finish(env)
        with self.assertRaises(ValueError):
            env.uplink([{"action": "inspect", "region": "r2"}])
        # The command executed but its delayed signal has not arrived at the horizon.
        self.assertEqual(events(env, "inspection_result"), [])
        self.assertEqual(env.replay()["expedition"]["inspection_executed"], [{"region": "r1", "tick": 4, "success": True}])

    def test_safety_stop_clears_queue_but_never_refunds_inspection(self):
        env = ExpeditionEnvironment()
        env._x, env._y = 39.99, 20  # Trusted physics fixture at an outward map edge.
        env.uplink([{"action": "drive", "heading_deg": 0, "metres": 5},
                    {"action": "inspect", "region": "r1"}])
        env.advance(5)
        self.assertEqual(list(env._commands), [])
        self.assertEqual(env.rules()["science"]["inspection_reserved_regions"], ["r1"])
        self.assertEqual(env.rules()["science"]["inspection_remaining"], 1)
        with self.assertRaises(ValueError):
            env.uplink([{"action": "inspect", "region": "r1"}])
        env.uplink([{"action": "inspect", "region": "r2"}])
        finish(env)
        self.assertEqual([e["region"] for e in events(env, "inspection_result")], ["r2"])
        self.assertEqual([e["region"] for e in env.replay()["expedition"]["inspection_executed"]], ["r2"])

    def test_energy_order_exact_cost_and_insufficient_cost(self):
        for battery, success in ((4, True), (3.5, False)):
            env = ExpeditionEnvironment(config=Config(initial_battery=battery, max_ticks=8))
            env.uplink([{"action": "inspect", "region": "r1"}])
            result = finish(env)
            self.assertFalse(result["alive"])
            self.assertEqual(env._battery, 0)
            self.assertEqual(len(events(env, "inspection_result")), int(success))
            self.assertEqual(len(events(env, "inspection_failed")), int(not success))
            self.assertEqual(len(events(env, "battery_depleted")), 1)
            self.assertEqual(env.rules()["science"]["inspection_remaining"], 1)


class PhysicsAndRewardTests(unittest.TestCase):
    def test_no_inspections_all_rich_matches_original_dynamic_physics(self):
        config = Config(max_ticks=60)
        expedition = ExpeditionEnvironment(seed=7, mission_seed=12, config=config, quality_fixture=RICH)
        dynamic = DynamicEnvironment(seed=7, config=config, mission=make_mission(12))
        for env in (expedition, dynamic):
            target = env._world.targets[0]
            env._x, env._y = target.x, target.y  # Exact sample fixture; subsequent drives use real physics.
        commands = [{"action": "sample"}, {"action": "drive", "heading_deg": 33, "metres": 2},
                    {"action": "drive", "heading_deg": 210, "metres": 5}, {"action": "sample"}, {"action": "wait"}]
        self.assertEqual(expedition.uplink(commands), dynamic.uplink(commands))
        for _ in range(12):
            a, b = expedition.advance(5), dynamic.advance(5)
            self.assertEqual(without_science(a["packets"]), b["packets"])
        self.assertEqual(without_science(expedition.replay()["states"]), dynamic.replay()["states"])
        self.assertEqual(expedition._heading_errors, dynamic._heading_errors)
        a, b = expedition.evaluate(), dynamic.evaluate()
        for key in b:
            if key not in ("samples", "mission_profile"):
                self.assertEqual(a[key], b[key], key)
        self.assertEqual([{key: sample[key] for key in b["samples"][0]} for sample in a["samples"]], b["samples"])

    def test_sampling_reveals_exact_shared_quality_after_delay(self):
        env = ExpeditionEnvironment(quality_fixture=POOR, signal_fixture=RICH)
        target = env._world.targets[0]
        env._x, env._y = target.x, target.y
        env.uplink([{"action": "sample"}])
        for tick in range(1, 8):
            env.advance()
            self.assertEqual(len(events(env, "region_quality")), int(tick >= 7))
        self.assertEqual(events(env, "region_quality"), [{"type": "region_quality", "region": "r1", "quality": "poor", "target_id": "t1"}])
        self.assertEqual(env.rules()["science"]["inspection_remaining"], 2)
        target2 = env._world.targets[1]
        env._x, env._y = target2.x, target2.y
        env.uplink([{"action": "sample"}])
        env.advance(5)
        env.advance(3)
        self.assertEqual([e["quality"] for e in events(env, "region_quality")], ["poor", "poor"])

    def test_grade_uses_quality_deadline_and_public_constant_normalizer(self):
        for late in (False, True):
            env = ExpeditionEnvironment(quality_fixture=POOR)
            target = env._world.targets[0]
            if late:
                while env._tick <= env._plans[target.id].deadline_tick:
                    env.advance()
            env._x, env._y = target.x, target.y
            env.uplink([{"action": "sample"}])
            env.advance(5)
            env._x, env._y = env._world.base  # Isolate the grade's exact home factor.
            result = finish(env)
            expected = 2 * .2 * (.25 if late else 1)
            self.assertEqual(result["sampled_value"], expected)
            self.assertEqual(result["raw_score"], expected)
            self.assertEqual(result["max_available_value"], 20)
            sample = result["samples"][0]
            self.assertEqual((sample["base_value"], sample["quality"], sample["quality_multiplier"]), (2, "poor", .2))
            self.assertEqual(sample["on_time"], not late)
            self.assertEqual(env.replay()["result"], result)

    def test_late_unreceived_sample_counts_only_in_evaluator_truth(self):
        env = ExpeditionEnvironment(config=Config(max_ticks=4), quality_fixture=POOR)
        target = env._world.targets[0]
        env._x, env._y = target.x, target.y
        env.uplink([{"action": "sample"}])
        result = finish(env)
        self.assertEqual(events(env, "region_quality"), [])
        self.assertEqual(result["sampled_targets"], ["t1"])
        self.assertEqual(result["sampled_value"], .4)
        self.assertEqual(result["raw_score"], .2)  # alive elsewhere
        self.assertEqual(env.replay()["states"][-1]["events"][-1]["quality"], "poor")


if __name__ == "__main__":
    unittest.main()
