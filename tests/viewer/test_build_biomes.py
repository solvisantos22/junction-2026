"""The biome edition of the 3D Mars demo: its data, and that it leaves the main demo alone.

    python3 -m unittest tests.viewer.test_build_biomes -v

Needs numpy (the biome missions are played by the Manh controllers); about fifteen seconds.
The page's looks are checked by opening it in a browser. These tests cover what it is fed,
that the main demo's own missions pass through unchanged, and that the add-on still finds in
the main demo's app the few things it leans on.
"""

import base64
import contextlib
import hashlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "viewer"))

try:
    import numpy  # noqa: F401
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False

PUBLIC_TOOLS = {"rules", "map", "telemetry_log", "uplink", "advance"}
MAIN_FILES = [REPO / "viewer" / "mars-demo.html", REPO / "viewer" / "mars" / "data.json",
              REPO / "viewer" / "mars" / "app.js", REPO / "viewer" / "mars" / "index.html",
              REPO / "viewer" / "mars" / "style.css"]


def digest(paths):
    return [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]


@unittest.skipUnless(HAVE_NUMPY, "the biome missions are played by the Manh controllers, which need numpy")
class BiomeDemoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import build_biomes
        import build_mars
        from lightlag_dynamic.biomes import BIOME_IDS, MAIN
        cls.build, cls.main_build, cls.BIOME_IDS, cls.MAIN = build_biomes, build_mars, BIOME_IDS, MAIN
        cls.before = digest(MAIN_FILES)
        cls.data = build_biomes.gather()
        cls.missions = cls.data["missions"]
        cls.biome_missions = [m for m in cls.missions if m["biome"] != MAIN]

    def test_main_mars_holds_the_main_demos_missions_unchanged(self):
        ours = [m for m in self.missions if m["biome"] == self.MAIN]
        theirs = self.main_build.gather()["missions"]
        self.assertEqual([{k: v for k, v in m.items() if k != "biome"} for m in ours], theirs)
        self.assertEqual(self.missions[:len(theirs)], ours, "Main Mars comes first, in the main demo's order")

    def test_every_other_biome_has_one_mission_of_four_scripted_runs_on_one_map(self):
        self.assertEqual([m["biome"] for m in self.biome_missions], list(self.BIOME_IDS[1:]))
        self.assertEqual([b["id"] for b in self.data["biomes"]], list(self.BIOME_IDS))
        for mission in self.biome_missions:
            with self.subTest(biome=mission["biome"]):
                self.assertEqual([r["id"] for r in mission["runs"]], ["best", "reference", "fixed-plan", "leg-and-wait"])
                self.assertEqual(mission["featured"], "best")
                self.assertEqual({r["kind"] for r in mission["runs"]}, {"scripted"})
                self.assertIn("no model has played this biome", mission["brief"])
                first = self.build.mission_definition(mission["runs"][0]["replay"])
                for run in mission["runs"]:
                    self.assertEqual(self.build.mission_definition(run["replay"]), first)
                    self.assertEqual(run["replay"]["biome"]["ids"], [mission["biome"]])
                    self.assertEqual(run["replay"]["seed"], mission["seed"])
                self.assertIn(mission["seed"], self.build.SEEDS)

    def test_each_mission_shows_its_biome(self):
        for mission in self.biome_missions:
            with self.subTest(biome=mission["biome"]):
                self.assertTrue(self.build.shows_biome(mission["biome"], mission["runs"]))

    def test_every_call_shown_reached_the_simulator_and_matches_the_replay(self):
        for mission in self.biome_missions:
            for run in mission["runs"]:
                with self.subTest(biome=mission["biome"], run=run["id"]):
                    calls = run["calls"]
                    self.assertLessEqual({c["tool"] for c in calls}, PUBLIC_TOOLS)
                    self.assertTrue(all(c["kind"] == "mcp" for c in calls))
                    ticks = [c["tick"] for c in calls]
                    self.assertEqual(ticks, sorted(ticks))
                    self.assertLessEqual(calls[-1]["tick_after"], mission["ticks"])
                    sent = [command for c in calls if c["tool"] == "uplink" and c["ok"] for command in c["arguments"]["commands"]]
                    self.assertEqual(len(sent), len(run["replay"]["commands"]))
                    landed = [t for c in calls if c["tool"] == "uplink" and c["ok"] for t in c["summary"]["execute_ticks"]]
                    self.assertEqual(landed, [c["execute_tick"] for c in run["replay"]["commands"]])

    def test_the_score_shown_is_the_evaluators(self):
        for mission in self.biome_missions:
            for run in mission["runs"]:
                result = run["replay"]["result"]
                self.assertAlmostEqual(run["reward"], result["raw_score"] / result["max_available_value"])
                self.assertEqual(len(run["replay"]["states"]), mission["ticks"] + 1)

    def test_the_first_run_is_the_controller_named_best_overall(self):
        summary = self.build.SUMMARY
        self.assertTrue(summary.exists(), "the early test's summary is committed with the doc")
        overall = json.loads(summary.read_text(encoding="utf-8"))["overall"]
        self.assertEqual(next(iter(overall)), self.build.BEST)
        self.assertEqual(self.data["early_test"]["best_overall"], self.data["shown_best"])

    def test_building_leaves_the_main_demo_alone(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "biomes-demo.html"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.build.main(["--out", str(out)]), 0)
            page = out.read_text(encoding="utf-8")
        self.assertEqual(digest(MAIN_FILES), self.before)
        self.assertNotRegex(page, r'(src|href)="https?://')
        embedded = dict(re.findall(r'<script id="(src-[a-z]+)" type="application/octet-stream">([^<]*)</script>', page))
        self.assertEqual(base64.b64decode(embedded["src-app"]), (REPO / "viewer" / "mars" / "app.js").read_bytes())
        self.assertEqual(base64.b64decode(embedded["src-biomes"]), self.build.ADDON.read_bytes())
        self.assertEqual(json.loads(base64.b64decode(embedded["src-data"])), json.loads(json.dumps(self.data)))

    def test_the_committed_page_carries_the_current_data_and_add_on(self):
        committed = REPO / "viewer" / "biomes-demo.html"
        self.assertTrue(committed.exists(), "run python3 viewer/build_biomes.py")
        page = committed.read_text(encoding="utf-8")
        embedded = dict(re.findall(r'<script id="(src-[a-z]+)" type="application/octet-stream">([^<]*)</script>', page))
        # Not the embedded app: a change to the main demo must not fail this page's test.
        self.assertEqual(base64.b64decode(embedded["src-biomes"]), self.build.ADDON.read_bytes(), "rebuild the page")
        self.assertEqual(json.loads(base64.b64decode(embedded["src-data"])), json.loads(json.dumps(self.data)), "rebuild the page")


class AddOnContractTest(unittest.TestCase):
    """What viewer/biomes/addon.js leans on in the main demo's files. If one of these fails,
    the main demo changed in a way the add-on must follow; the main demo itself is fine."""

    def test_the_app_still_exposes_what_the_add_on_uses(self):
        app = (REPO / "viewer" / "mars" / "app.js").read_text(encoding="utf-8")
        exposed = re.search(r"window\.LIGHTLAG = \{([^}]*)\}", app)
        self.assertIsNotNone(exposed)
        for name in ("state", "seek", "build", "startMission", "MISSIONS"):
            self.assertIn(name, exposed.group(1))
        for needle in ("class MarsScene", "this.tactical = new THREE.Group()", "this.cinematic = new THREE.Group()",
                       "P(x, y, h = 0)", "node.userData.px", "this.scene = sceneOf(run)", "screen.el = el",
                       "sample(t)", "seen(t)", "state.screens", "Object.assign(this, raw)", "this.cfg = replay.config"):
            self.assertIn(needle, app, needle)
        self.assertNotIn("onBeforeRender", app, "the add-on sets scene.onBeforeRender")

    def test_the_page_still_has_the_elements_the_add_on_uses(self):
        page = (REPO / "viewer" / "mars" / "index.html").read_text(encoding="utf-8")
        for needle in ('id="title"', 'id="missions"', 'class="timeline"', 'class="help"', "<!--DEV-->", "<!--/DEV-->"):
            self.assertIn(needle, page, needle)

    def test_every_biome_but_main_mars_has_a_palette_that_stays_slight(self):
        from lightlag_dynamic.biomes import BIOME_IDS, MAIN
        addon = (REPO / "viewer" / "biomes" / "addon.js").read_text(encoding="utf-8")
        block = addon[addon.index("const PALETTES = {"):]
        block = block[:block.index("\n};")]
        number = r"-?\d+(?:\.\d+)?"
        triple = rf"\[({number}), ({number}), ({number})\]"
        rows = re.findall(rf"^  (\w+):\s+\{{ ground: {triple}, sand: {triple}, rocks: {triple}, light: {triple}, "
                          rf"haze: \[0x[0-9a-f]{{6}}, ({number})\], sun: ({number}) \}}", block, flags=re.M)
        self.assertEqual([row[0] for row in rows], [biome for biome in BIOME_IDS if biome != MAIN])
        for name, *values in rows:
            numbers = [float(v) for v in values]
            multipliers, haze, sun = numbers[:12], numbers[12], numbers[13]
            with self.subTest(biome=name):
                # A shift, not a new planet: nothing darker than half, nothing brighter than a quarter more.
                self.assertTrue(all(0.45 <= m <= 1.25 for m in multipliers), multipliers)
                self.assertTrue(0.0 < haze <= 0.4 and 0.7 <= sun <= 1.15)
                # On the main demo's middle ground tone (#a34b2b) the result is still rust: red over twice blue.
                red, blue = 0xa3 / 255 * numbers[0], 0x2b / 255 * numbers[2]
                self.assertGreater(red, 2 * blue)

    def test_the_add_on_is_one_module_with_one_import(self):
        addon = (REPO / "viewer" / "biomes" / "addon.js").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^import .*$", addon, flags=re.M), ["import * as THREE from 'three';"])
        self.assertNotRegex(addon, r"https?://")


if __name__ == "__main__":
    unittest.main()
