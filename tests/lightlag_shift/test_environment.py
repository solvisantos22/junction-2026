"""The ground-change mission. Standard library only.

    python3 -m unittest discover -s tests/lightlag_shift -v
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from lightlag import Config  # noqa: E402
from lightlag_dynamic.environment import DynamicEnvironment  # noqa: E402
from lightlag_shift import CHANGE_WINDOW, SLIP_AFTER, ShiftEnvironment, draw_change  # noqa: E402
from lightlag_shift.serve import ShiftEpisodeService  # noqa: E402

CONFIG = Config(delay_ticks=3, max_ticks=50)
SCRIPT = [{"action": "drive", "heading_deg": 30.0, "metres": 4.0}] * 5


def play(env, ticks=50):
    """The same short drive every ten ticks, so both environments get identical commands."""
    while True:
        tick = env._tick
        if tick >= ticks:
            return
        if tick % 10 == 0:
            env.uplink(SCRIPT)
        env.advance(1)


class Change(unittest.TestCase):
    def test_the_hidden_draw_is_repeatable_and_inside_what_is_published(self):
        for seed in range(200):
            tick, after = draw_change(seed)
            self.assertEqual((tick, after), draw_change(seed))
            self.assertTrue(CHANGE_WINDOW[0] <= tick <= CHANGE_WINDOW[1], seed)
            for terrain, (low, high) in SLIP_AFTER.items():
                self.assertTrue(low <= after[terrain] <= high, (seed, terrain))
        self.assertGreater(len({draw_change(seed)[0] for seed in range(200)}), 10)

    def test_rules_publish_the_window_and_ranges_but_not_the_tick_or_values(self):
        env = ShiftEnvironment(seed=3100, config=CONFIG)
        rules = env.rules()
        change = rules["ground_change"]
        self.assertEqual(change["tick_window"], list(CHANGE_WINDOW))
        self.assertEqual(change["slip_after"], {k: list(v) for k, v in SLIP_AFTER.items()})
        self.assertFalse(change["announced"])
        self.assertNotIn("slip_may_change", rules)
        text = json.dumps([rules, env.map(), env.telemetry_log()])
        for hidden in env.shift["slip_after"].values():
            self.assertNotIn(str(hidden), text)
        self.assertNotIn('"tick": {}'.format(env.shift["tick"]), json.dumps(change))

    def test_until_the_change_it_is_the_teams_mission_exactly(self):
        plain = DynamicEnvironment(seed=3100, config=CONFIG, profile="rush_noisy")
        shifted = ShiftEnvironment(seed=3100, config=CONFIG, profile="rush_noisy")
        self.assertEqual(plain.map(), shifted.map())
        play(plain)
        play(shifted)
        tick = shifted.shift["tick"]
        a, b = plain.replay()["states"], shifted.replay()["states"]
        self.assertEqual(a[:tick], b[:tick])          # every state before the change tick
        self.assertNotEqual(a[tick:], b[tick:])       # and it matters afterwards

    def test_the_ground_becomes_exactly_what_was_drawn_at_the_drawn_tick(self):
        env = ShiftEnvironment(seed=3101, config=CONFIG)
        tick, after = draw_change(3101)
        before = dict(env.shift["slip_before"])
        while env._tick < tick - 1:
            env.advance(1)
        self.assertEqual({t: env._slip[t] for t in after}, before)
        env.advance(1)
        for terrain in after:
            self.assertAlmostEqual(env._slip[terrain], after[terrain], places=9)
        while env._tick < CONFIG.max_ticks:
            env.advance(1)
        self.assertEqual(env.replay()["ground_change"]["tick"], tick)

    def test_it_makes_the_ground_worse_on_every_terrain(self):
        for seed in range(50):
            env = ShiftEnvironment(seed=seed, config=CONFIG)
            for terrain, value in env.shift["slip_after"].items():
                self.assertGreater(value, env.shift["slip_before"][terrain], (seed, terrain))


class Service(unittest.TestCase):
    def test_the_service_plays_the_ground_change_mission_and_grades_it(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ShiftEpisodeService(seed=3100, profile="rush_noisy", config=CONFIG, artifact_dir=directory)
            self.assertIn("ground_change", service.call("rules"))
            service.call("uplink", {"commands": SCRIPT})
            service.call("advance", {"ticks": 5})
            service.finish()
            replay = json.loads((Path(directory) / "replay.json").read_text(encoding="utf-8"))
            result = json.loads((Path(directory) / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(replay["ground_change"]["tick"], draw_change(3100)[0])
        self.assertIn("raw_score", result)


if __name__ == "__main__":
    unittest.main()
