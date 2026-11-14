"""The held-out evaluation worlds: one list, the same in the frozen baseline and the evaluation page.

    python3 -m unittest discover -s tests/lightlag_traverse_max -p "test_heldout.py" -v
"""

import base64
import json
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from lightlag_traverse_max import heldout, oneshot  # noqa: E402

PAGE = REPO / "viewer" / "traverse-evaluation-max.html"


class HeldOutTest(unittest.TestCase):
    def test_the_six_worlds_are_the_frozen_baselines(self):
        self.assertEqual(heldout.EVALUATION_WORLDS, (500, 510, 520, 505, 509, 515))
        self.assertEqual((oneshot.HARD_WORLDS, oneshot.FAIR_WORLDS), (heldout.SUPERHARD_WORLDS, heldout.FAIR_WORLDS))
        frozen = oneshot.BASELINE / "freeze.json"
        if frozen.exists():
            data = json.loads(frozen.read_text(encoding="utf-8"))
            self.assertEqual((data["hard_worlds"], data["fair_worlds"]),
                             (list(heldout.SUPERHARD_WORLDS), list(heldout.FAIR_WORLDS)))

    def test_training_on_a_reserved_world_is_refused(self):
        heldout.check_training_seeds(range(200000, 200100))
        heldout.check_training_seeds([499, 524, 2025, 2030])
        for seeds in ([505], range(490, 510), [2027], [99991]):
            with self.assertRaises(ValueError):
                heldout.check_training_seeds(seeds)
        self.assertEqual(heldout.reserved([1, 500, 523, 2026, 524]), [500, 523, 2026])

    @unittest.skipUnless(PAGE.exists(), "the evaluation page is not built")
    def test_the_evaluation_page_shows_exactly_the_held_out_worlds(self):
        page = PAGE.read_text(encoding="utf-8")
        found = re.findall(r'<script id="src-data-(\d+)" type="application/octet-stream">([^<]*)</script>', page)
        seeds = [json.loads(base64.b64decode(data))["seed"] for _, data in found]
        self.assertEqual(seeds, list(heldout.EVALUATION_WORLDS))


if __name__ == "__main__":
    unittest.main()
