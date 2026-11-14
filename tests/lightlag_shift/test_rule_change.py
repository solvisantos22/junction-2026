"""The rule-change mission: one of four published changes, at a hidden tick. Standard library only.

    python3 -m unittest discover -s tests/lightlag_shift -v
"""

import json
import sys
import unittest
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from lightlag import Config  # noqa: E402
from lightlag_dynamic.environment import DynamicEnvironment  # noqa: E402
from lightlag_shift import CHANGE_WINDOW  # noqa: E402
from lightlag_shift.reference import Prepared  # noqa: E402
from lightlag_shift.rule_change import (KINDS, PACKET_LOSS, RELAY, TURN_COST,  # noqa: E402
                                        RuleChangeEnvironment, draw_rule_change)

CONFIG = Config(delay_ticks=3, max_ticks=50)


def play(env, heading=lambda tick: (tick * 37) % 360):
    """One short drive every six ticks, each on a new heading; returns the uplink acknowledgements."""
    acks = []
    while env._tick < CONFIG.max_ticks:
        if env._tick % 6 == 0 and env._tick < 44:
            acks.append(env.uplink([{"action": "drive", "heading_deg": heading(env._tick), "metres": 2.0}])[0])
        env.advance(1)
    return acks


class Draw(unittest.TestCase):
    def test_every_kind_comes_up_and_every_value_is_inside_what_is_published(self):
        seen = Counter()
        for seed in range(400):
            change = draw_rule_change(seed)
            self.assertEqual(change, draw_rule_change(seed))
            seen[change["kind"]] += 1
            self.assertTrue(CHANGE_WINDOW[0] <= change["tick"] <= CHANGE_WINDOW[1])
            if change["kind"] == "turning":
                self.assertTrue(TURN_COST[0] <= change["energy_per_degree"] <= TURN_COST[1])
            if change["kind"] == "link":
                self.assertTrue(PACKET_LOSS[0] <= change["loss_probability"] <= PACKET_LOSS[1])
        self.assertEqual(set(seen), set(KINDS))
        self.assertGreater(min(seen.values()), 60)

    def test_forcing_a_kind_keeps_the_tick(self):
        for kind in KINDS:
            self.assertEqual(draw_rule_change(7, kind)["tick"], draw_rule_change(7)["tick"])
            self.assertEqual(draw_rule_change(7, kind)["kind"], kind)
        with self.assertRaises(ValueError):
            draw_rule_change(7, "weather")


class WhatTheAgentIsTold(unittest.TestCase):
    def test_the_rules_never_change_and_never_name_the_change(self):
        for kind in KINDS:
            env = RuleChangeEnvironment(seed=3200, config=CONFIG, kind=kind)
            before = json.dumps(env.rules(), sort_keys=True)
            play(env)
            self.assertEqual(json.dumps(env.rules(), sort_keys=True), before, kind)
            rules = env.rules()
            for leak in ("turn_cost_per_degree", "telemetry_packet_loss", "uplink_windows", "slip_may_change"):
                self.assertNotIn(leak, rules, kind)
            self.assertEqual(set(rules["rule_change"]["one_of"]), set(KINDS))
            self.assertEqual(rules["rule_change"]["tick_window"], list(CHANGE_WINDOW))

    def test_until_the_change_it_is_the_teams_mission_exactly(self):
        for kind in KINDS:
            plain = DynamicEnvironment(seed=3200, config=CONFIG, profile="rush_noisy")
            changed = RuleChangeEnvironment(seed=3200, config=CONFIG, kind=kind)
            play(plain)
            play(changed)
            tick = changed.change["tick"]
            self.assertEqual(plain.replay()["states"][:tick], changed.replay()["states"][:tick], kind)


class EachChangeTakesEffect(unittest.TestCase):
    def run_kind(self, kind, **kw):
        env = RuleChangeEnvironment(seed=3200, config=CONFIG, kind=kind)
        acks = play(env, **kw)
        return env, acks

    def baseline(self, **kw):
        env = DynamicEnvironment(seed=3200, config=CONFIG, profile="rush_noisy")
        play(env, **kw)
        return env

    def test_ground(self):
        env, _ = self.run_kind("ground")
        for terrain, value in env.change["slip_after"].items():
            self.assertAlmostEqual(env._slip[terrain], value, places=9)

    def test_turning_drains_the_battery_only_when_the_rover_turns(self):
        turning, _ = self.run_kind("turning")
        self.assertLess(turning.replay()["states"][-1]["battery"], self.baseline().replay()["states"][-1]["battery"] - 5)
        straight, _ = self.run_kind("turning", heading=lambda tick: 30.0)
        same = self.baseline(heading=lambda tick: 30.0)
        self.assertAlmostEqual(straight.replay()["states"][-1]["battery"], same.replay()["states"][-1]["battery"], places=6)

    def test_link_loses_packets_only_after_the_change(self):
        env, _ = self.run_kind("link")
        got = {packet["tick"] for packet in env.telemetry_log()}
        tick = env.change["tick"]
        self.assertTrue(all(t in got for t in range(0, tick)))
        self.assertGreater(len([t for t in range(tick, 47) if t not in got]), 4)

    def test_relay_holds_uplinks_sent_between_passes(self):
        env, acks = self.run_kind("relay")
        tick, (period, open_ticks) = env.change["tick"], RELAY
        for ack in acks:
            sent = ack["sent_tick"]
            if sent < tick:
                self.assertEqual(ack.get("transmit_tick", sent), sent)
            elif sent % period >= open_ticks:
                self.assertEqual(ack["transmit_tick"], (sent // period + 1) * period)
        self.assertTrue(any(ack.get("transmit_tick", ack["sent_tick"]) > ack["sent_tick"] for ack in acks))

    def test_the_replay_says_what_happened(self):
        for kind in KINDS:
            env, _ = self.run_kind(kind)
            self.assertEqual(env.replay()["rule_change"], draw_rule_change(3200, kind))


class PreparedReference(unittest.TestCase):
    def test_it_only_adds_the_worst_turning_cost_from_the_published_menu(self):
        env = RuleChangeEnvironment(seed=3200, config=CONFIG)

        class Tools:
            rules = staticmethod(env.rules)
            map = staticmethod(env.map)

        real, prepared = env.rules(), Prepared(Tools()).rules()
        self.assertEqual(prepared.pop("turn_cost_per_degree"), TURN_COST[1])
        self.assertEqual(prepared, real)
        self.assertEqual(Prepared(Tools()).map(), env.map())

    def test_without_a_menu_it_changes_nothing(self):
        env = DynamicEnvironment(seed=3200, config=CONFIG, profile="rush_noisy")

        class Tools:
            rules = staticmethod(env.rules)

        self.assertEqual(Prepared(Tools()).rules(), env.rules())


if __name__ == "__main__":
    unittest.main()
