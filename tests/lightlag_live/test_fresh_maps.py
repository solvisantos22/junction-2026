"""The fresh-map comparison: its arithmetic, and the saved scores the write-up quotes.

    python3 -m unittest discover -s tests/lightlag_live -v

Standard library only. The saved file was produced by `python3 -m lightlag_live.fresh_maps play`,
which needs Docker; these tests read it and never run a program.
"""

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lightlag_live import fresh_maps  # noqa: E402


def rows(*rewards, alive=True, home=True):
    return {str(index): {"reward": reward, "alive": alive, "home": home} for index, reward in enumerate(rewards)}


class CompareTest(unittest.TestCase):
    def test_a_reference_that_is_higher_on_every_map_wins_every_campaign(self):
        reference, program = rows(0.6, 0.7, 0.8, 0.9), rows(0.5, 0.6, 0.7, 0.8)
        result = fresh_maps.compare(reference, program, list(reference), lengths=(1, 2, 4, 8), draws=200)
        self.assertAlmostEqual(result["lead"], 0.1)
        self.assertEqual((result["higher"], result["equal"], result["lower"]), (4, 0, 0))
        self.assertEqual(result["campaigns"], {1: 1.0, 2: 1.0, 4: 1.0, 8: None})   # only four maps to draw from

    def test_equal_scores_are_not_wins(self):
        same = rows(0.5, 0.5, 0.5)
        result = fresh_maps.compare(same, same, list(same), lengths=(1, 3), draws=200)
        self.assertEqual(result["campaigns"], {1: 0.0, 3: 0.0})
        self.assertEqual(result["equal"], 3)

    def test_a_small_lead_wins_more_often_in_longer_campaigns(self):
        # Higher on 6 maps in 10 by 0.1, lower on 4 by 0.1: a lead of 0.02 a map.
        reference = rows(*([0.6] * 6 + [0.4] * 4))
        program = rows(*([0.5] * 10))
        result = fresh_maps.compare(reference, program, list(reference), lengths=(1, 5, 9), draws=4000)
        self.assertAlmostEqual(result["campaigns"][1], 0.6, delta=0.05)
        self.assertGreater(result["campaigns"][9], result["campaigns"][1])
        self.assertAlmostEqual(result["lead"], 0.02)

    def test_the_mission_rule_needs_a_live_rover_at_base_with_enough_score(self):
        reference = {"1": {"reward": 0.6, "alive": True, "home": True},
                     "2": {"reward": 0.59, "alive": True, "home": True},
                     "3": {"reward": 0.9, "alive": True, "home": False},
                     "4": {"reward": 0.9, "alive": False, "home": True},
                     "10": {"reward": 0.7, "alive": True, "home": True}}
        self.assertEqual(fresh_maps.picked_by_the_rule(reference), ["1", "10"])


class SavedScoresTest(unittest.TestCase):
    """The numbers docs/lightlag-live.md quotes from the 200 fresh maps."""

    @classmethod
    def setUpClass(cls):
        cls.saved = json.loads(fresh_maps.SAVED.read_text(encoding="utf-8"))
        cls.scores = cls.saved["scores"]
        cls.maps = sorted(cls.scores["reference"], key=int)

    def test_every_program_was_scored_on_every_map_and_nothing_failed(self):
        self.assertEqual(len(self.maps), 200)
        self.assertEqual(self.saved["problems"], [])
        self.assertEqual(set(self.scores), set(fresh_maps.PROGRAMS))
        for name, played in self.scores.items():
            self.assertEqual(sorted(played, key=int), self.maps, name)

    def test_the_maps_are_not_the_tasks_or_the_exploration_maps(self):
        from lightlag_live import make_task
        task = {int(part.split(":")[0]) for part in make_task.MISSIONS.split(",")}
        seeds = {int(seed) for seed in self.maps}
        self.assertFalse(seeds & task)
        self.assertFalse(seeds & set(range(8000, 8040)))      # the maps the settings were chosen on
        self.assertFalse(seeds & set(range(9001, 9041)))      # the maps the mission rule was run over

    def test_the_headline_numbers(self):
        reference = self.scores["reference"]
        mean = lambda name, pool: sum(self.scores[name][s]["reward"] for s in pool) / len(pool)
        self.assertAlmostEqual(mean("reference", self.maps), 0.518, places=3)
        self.assertAlmostEqual(mean("opus-oneshot-1", self.maps), 0.515, places=3)
        self.assertAlmostEqual(mean("opus-agent-2", self.maps), 0.480, places=3)
        self.assertAlmostEqual(mean("opus-agent-3", self.maps), 0.459, places=3)
        picked = fresh_maps.picked_by_the_rule(reference)
        self.assertEqual(len(picked), 56)
        self.assertAlmostEqual(mean("reference", picked), 0.688, places=3)
        # Against Opus's one-request program the reference has no lead on unselected maps ...
        level = fresh_maps.compare(reference, self.scores["opus-oneshot-1"], self.maps, lengths=(6,), draws=4000)
        self.assertLess(level["lead_low"], 0.0)
        self.assertGreater(level["lead_high"], 0.0)
        self.assertAlmostEqual(level["campaigns"][6], 0.5, delta=0.05)
        # ... and the mission rule alone gives it one.
        chosen = fresh_maps.compare(reference, self.scores["opus-oneshot-1"], picked, lengths=(6,), draws=4000)
        self.assertGreater(chosen["lead_low"], 0.0)
        self.assertGreater(chosen["campaigns"][6], 0.75)
        # Against the smaller models' programs it wins nearly every six-map campaign either way.
        for name in ("sonnet-oneshot-1", "haiku-oneshot-1", "haiku-oneshot-2", "haiku-oneshot-3"):
            self.assertGreater(fresh_maps.compare(reference, self.scores[name], self.maps, lengths=(6,), draws=2000)
                               ["campaigns"][6], 0.97, name)

    def test_the_table_prints(self):
        text = fresh_maps.table(self.saved, draws=300)
        self.assertIn("every map: 200 maps, reference mean 0.518", text)
        self.assertIn("maps the mission rule would pick: 56 maps", text)


if __name__ == "__main__":
    unittest.main()
