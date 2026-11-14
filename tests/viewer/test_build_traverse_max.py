"""The pages for the Traverse map option: Kristján's demo fed with runs on the normal and the MAX map.

    python3 -m unittest discover -s tests/viewer -p "test_build_traverse_max.py" -v

Standard library only. Two cheap players on a short mission; a few seconds.
"""

import base64
import hashlib
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "viewer"))
import build_traverse_max  # noqa: E402

CHEAP = [("straight", "reference", "Straight line", "played by the tests"),
         ("nothing", "scripted", "Nothing", "played by the tests")]
KRISTJANS = [REPO / "viewer" / "traverse" / "data.json", REPO / "viewer" / "traverse-demo.html"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def embedded(page):
    found = re.search(r'<script id="src-data" type="application/octet-stream">([^<]*)</script>', page)
    return json.loads(base64.b64decode(found.group(1)))


class PagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="traverse-players-tests-"))
        cls.addClassCleanup(shutil.rmtree, cls.root, ignore_errors=True)
        before = [digest(path) for path in KRISTJANS]
        cls.pages = build_traverse_max.build(seed=3, out_dir=cls.root, players=CHEAP, mission={"max_ticks": 60},
                                             workers=1)
        cls.untouched = before == [digest(path) for path in KRISTJANS]

    def test_one_page_per_map_and_nothing_of_kristjans_is_written(self):
        self.assertEqual([page.name for page in self.pages],
                         ["traverse-players-normal.html", "traverse-players-max.html"])
        self.assertTrue(self.untouched)

    def test_each_page_holds_its_own_map_of_the_same_world(self):
        normal, hard = (embedded(page.read_text(encoding="utf-8")) for page in self.pages)
        self.assertEqual((normal["title"], hard["title"]),
                         ("Lightlag Traverse · normal map", "Lightlag Traverse · MAX map"))
        self.assertIn("MAX map", hard["pitch"])
        self.assertEqual(normal["world"]["elevation_cm"], hard["world"]["elevation_cm"])
        self.assertEqual(normal["seed"], hard["seed"])
        for data in (normal, hard):
            self.assertEqual([run["label"] for run in data["runs"]], ["Straight line", "Nothing"])
            for run in data["runs"]:
                self.assertEqual(len(run["p"]), 2 * 61, "one position per tick")
                self.assertEqual(len(run["seen"]) % 2, 0)

    def test_the_evaluation_page_holds_one_site_per_world(self):
        out = self.root / "evaluation.html"
        build_traverse_max.evaluation(out, worlds=(505, 500), players=CHEAP, mission={"max_ticks": 60}, workers=1)
        page = out.read_text(encoding="utf-8")
        found = re.findall(r'<script id="src-data-(\d+)" type="application/octet-stream">([^<]*)</script>', page)
        sites = [json.loads(base64.b64decode(data)) for _, data in found]
        self.assertEqual([(s["site"], s["seed"], s["brand"]) for s in sites],
                         [(1, 505, "SITE 1 / 2"), (2, 500, "SITE 2 / 2")])
        self.assertEqual([site["label"] for site in sites[0]["sites"]], ["SITE 1", "SITE 2"])
        self.assertNotIn("MAX map", sites[1]["pitch"])

    def test_a_lost_packet_repeats_the_last_fix(self):
        replay = {"received_telemetry": [{"tick": 0, "position": [1.0, 2.0]}, {"tick": 2, "position": [3.0, 4.0]}]}
        log = build_traverse_max.filled(replay)["received_telemetry"]
        self.assertEqual([packet["tick"] for packet in log], [0, 1, 2])
        self.assertEqual(log[1]["position"], [1.0, 2.0])
        self.assertTrue(log[1]["lost"])
        self.assertNotIn("lost", log[2])


if __name__ == "__main__":
    unittest.main()
