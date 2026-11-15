"""manh_demo_1 and the second draft, the parts that need no browser, no Docker and no sound card.

    python3 -m unittest discover -s tests/manh_demo -v

The logo registry, the build-time copies of Kristján's pages (and that his files are left as
they were), this cut's changes to his storyboard, and the synthesised sound. The sound tests
need numpy, scipy and soundfile and are skipped without them.
"""

import base64
import hashlib
import json
import math
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from tools.demo_video import storyboard as base  # noqa: E402
from tools.manh_demo import cut, makers, pages  # noqa: E402

try:
    import numpy as np
    import soundfile as sf
    from tools.manh_demo import sound
except ImportError:                                  # the sound tests are skipped
    np = sf = sound = None

KRISTJANS = [REPO / "viewer" / "traverse-campaign.html", REPO / "tools" / "demo_video" / "film.html",
             REPO / "tools" / "demo_video" / "overlay.js", REPO / "tools" / "demo_video" / "storyboard.py"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fake_words(lines=None):
    """Word timings as the voice model would report them: every token a third of a second after the last."""
    words, lengths = {}, {}
    for key, text in (base.LINES if lines is None else lines).items():
        tokens = []
        for number, found in enumerate(re.finditer(r"[\w'’-]+|[^\w\s]", text)):
            after = text[found.end():found.end() + 1]
            tokens.append({"w": found.group(0), "space": after.isspace(), "t0": round(number * 0.3, 3), "t1": round(number * 0.3 + 0.25, 3)})
        words[key], lengths[key] = tokens, round(len(tokens) * 0.3, 3)
    return lengths, words


class MakersTest(unittest.TestCase):
    def test_a_label_names_its_maker(self):
        self.assertEqual(makers.maker_of("Opus 5.5 · agent 2"), "anthropic")
        self.assertEqual(makers.maker_of("Haiku 5.5 · one shot"), "anthropic")
        self.assertEqual(makers.maker_of("GPT-6.1 Sol · agent 1"), "openai")
        self.assertEqual(makers.maker_of("Gemini 4 Carbon · agent 1"), "google")
        self.assertIsNone(makers.maker_of("Reference"))
        self.assertIsNone(makers.maker_of("Greedy stand-in"))

    def test_every_maker_has_a_tile(self):
        tiles = makers.for_page()
        self.assertEqual(set(tiles), {"anthropic", "openai", "google", "reference", "rl", "modal"})
        self.assertEqual(tiles["modal"]["text"], "#7FEE64")
        self.assertNotEqual(tiles["anthropic"]["text"], tiles["google"]["text"])            # each lab's name in its own colour
        for key in makers.MAKERS:
            svg = makers.tile_svg(key)
            self.assertIn(makers.mark_path(key), svg)
            self.assertIn(makers.MAKERS[key]["ink"], svg)
            self.assertTrue(tiles[key]["tile"].startswith("data:image/svg+xml;base64,"))
        for own in (None, "rl"):                                                        # our own drivers carry no lab's mark
            self.assertFalse(any(makers.mark_path(key) in makers.tile_svg(own) for key in makers.MAKERS))

    def test_the_lineup_is_three_labs_by_three_tiers(self):
        found = makers.lineup()
        self.assertEqual(len(found["tiers"]), 3)
        self.assertEqual([lab["key"] for lab in found["labs"]], list(makers.MAKERS))
        for lab in found["labs"]:
            self.assertEqual(len(lab["models"]), 3)
            for model in lab["models"]:
                self.assertEqual(makers.maker_of(model), lab["key"], model)             # every model is filed under its own lab
        # the same nine models as the tier comparison runs
        runs = (REPO / "tools" / "tier_agents" / "run_tiers.py").read_text(encoding="utf-8")
        for short in ("gpt-6-luna", "gpt-6.1-terra", "gpt-6.1-sol", "gemini-4-hydrogen", "gemini-4-argon", "gemini-4-carbon"):
            self.assertIn(short, runs)
            self.assertTrue(any(short.replace("-", " ") == model.lower().replace("-", " ") for lab in found["labs"] for model in lab["models"]), short)

    def test_the_floating_icons_carry_the_family_marks_unless_asked_for_the_labs(self):
        family, labs, scene = makers.icon_settings(), makers.icon_settings(company=True), makers.scene_icon_settings()
        self.assertEqual([lab["name"] for lab in family["labs"]], ["CLAUDE", "GEMINI", "GPT"])
        self.assertEqual([lab["name"] for lab in labs["labs"]], ["ANTHROPIC", "GOOGLE DEEPMIND", "OPENAI"])
        self.assertEqual(family["labs"][0]["path"], makers.mark_path("anthropic"))
        self.assertNotEqual(family["labs"][0]["path"], labs["labs"][0]["path"])
        self.assertEqual(set(scene["marks"]), {"anthropic", "google", "openai", "reference"})
        self.assertTrue(scene["marks"]["reference"]["route"])                              # the planner carries no lab's mark
        self.assertEqual(scene["marks"]["anthropic"]["path"], makers.mark_path("anthropic"))
        for settings in (family, labs, scene):
            self.assertIn("return SVGLoader;", settings["loader"])
            self.assertNotIn("from 'three'", settings["loader"])

    def test_the_numbers_on_the_drivers_card_come_from_the_results(self):
        facts = makers.facts()
        self.assertGreater(facts["reference"], facts["rl"])
        self.assertGreater(facts["rl"], facts["best_claude"])


class PagesTest(unittest.TestCase):
    def test_copies_are_made_and_kristjans_files_are_untouched(self):
        before = {path: digest(path) for path in KRISTJANS}
        with tempfile.TemporaryDirectory() as folder:
            page = pages.campaign_page(Path(folder)).read_text(encoding="utf-8")
            film = pages.film_page(Path(folder)).read_text(encoding="utf-8")
            overlay = pages.overlay_script()
            self.assertTrue(Path(pages.font_environment(Path(folder))["FONTCONFIG_FILE"]).exists())
        block = re.search(r'<script id="src-app" type="application/octet-stream">([A-Za-z0-9+/=\s]+)</script>', page)
        app = base64.b64decode(block.group(1)).decode("utf-8")
        self.assertIn("window.LIGHTLAG_TRAVERSE_APP = { THREE, camera, scene, renderer, ACTORS,", app)
        self.assertIn('"Barlow Condensed", "DIN Condensed"', app)
        self.assertIn('--display: "Barlow Condensed", "DIN Condensed"', page)
        self.assertIn("window.__onset(at)", film)
        self.assertIn('"Barlow Condensed", "DIN Condensed"', overlay)
        self.assertEqual(before, {path: digest(path) for path in KRISTJANS})

    def test_a_page_that_has_moved_on_stops_the_build(self):
        with self.assertRaises(SystemExit):
            pages.patch_app("window.LIGHTLAG_TRAVERSE_APP = { somethingElse };")
        with self.assertRaises(SystemExit):
            pages.swap("one two two", "two", "three", 1, "a test")

    def test_the_fonts_are_in_the_folder(self):
        self.assertEqual(len(pages.fonts()), 8)


class CutTest(unittest.TestCase):
    def setUp(self):
        self.lengths, self.words = fake_words()
        self.base = {shot["name"]: shot for shot in base.shots(self.lengths, self.words)}
        self.mine = {shot["name"]: shot for shot in cut.shots(self.lengths, self.words)}

    def test_the_story_is_kristjans(self):
        self.assertIs(cut.LINES, base.LINES)
        self.assertEqual(list(self.mine), list(self.base))
        for name, shot in self.mine.items():
            self.assertEqual([beat.get("vo") for beat in shot["beats"]], [beat.get("vo") for beat in self.base[name]["beats"]])

    def test_the_map_is_held_for_the_trackers(self):
        mine, his = self.mine["world"]["beats"][0], self.base["world"]["beats"][0]
        self.assertAlmostEqual(mine["vo_at"], his["vo_at"] + cut.TITLE_LEAD)
        later = mine["at"][0]["t"] - his["at"][0]["t"]
        self.assertAlmostEqual(later, cut.TITLE_LEAD + cut.MAP_HOLD, places=2)
        title = next(cue for cue in mine["overlay"] if cue["kind"] == "title")
        self.assertGreater(mine["at"][0]["t"] - title["to"], 1.5)                    # the trackers get this long over the map

    def test_the_last_card_takes_the_stretch(self):
        longer = {shot["name"]: shot for shot in cut.shots(self.lengths, self.words, stretch=1.25)}
        self.assertAlmostEqual(longer["end"]["beats"][-1]["pad"] - self.mine["end"]["beats"][-1]["pad"], 1.25)

    def test_the_pieces_are_drafts_outside_the_film(self):
        film = set(self.mine)
        for name, piece in cut.PIECES.items():
            self.assertNotIn(name, film)
            self.assertIn(piece["page"], ("film", "campaign"))
            self.assertTrue(piece["beats"])
            if piece.get("addon"):
                self.assertTrue((REPO / "tools" / "manh_demo" / piece["addon"]).exists(), name)
        scene = cut.PIECES["icons_scene"]["beats"]                                         # each kind gets the same two moments
        self.assertEqual(len(scene), 8)
        self.assertEqual({beat["js"] for beat in scene[0::2]}, {scene[0]["js"]})
        self.assertEqual({beat["js"] for beat in scene[1::2]}, {scene[1]["js"]})
        self.assertAlmostEqual(sum(beat["min"] for beat in scene[:2]), cut.PIECES["icons_scene"]["addon_settings"]["show"])

    def test_the_length_leaves_a_second_under_two_minutes(self):
        self.assertLess(cut.LIMIT_SECONDS, 120.0)
        self.assertGreaterEqual(cut.TARGET_SECONDS, 119.0)
        self.assertLess(cut.TARGET_SECONDS, 119.5)


RUNS = REPO / "docs" / "lightlag-runs"


def mission(run, site):
    folder = RUNS / run / "artifacts" / "evaluator" / "missions" / "{:02d}".format(site)
    return json.loads((folder / "replay.json").read_text(encoding="utf-8"))


def ticks_of(replay, kind):
    return [state["tick"] for state in replay["states"] for event in state["events"] if event["type"] == kind]


class SecondDraftTest(unittest.TestCase):
    """The next draft (manh_demo_2): its script, its cast of nine models and what it says about them."""

    def setUp(self):
        self.kept = base.LINES
        base.LINES = cut.LINES2                             # as make.use(2) does: the word timings are looked up in the film's own lines
        self.lengths, self.words = fake_words(cut.LINES2)
        self.shots = cut.shots2(self.lengths, self.words)

    def tearDown(self):
        base.LINES = self.kept

    def test_every_line_is_spoken_once_and_in_order(self):
        spoken = [beat["vo"] for shot in self.shots for beat in shot["beats"] if beat.get("vo")]
        self.assertEqual(spoken, list(cut.LINES2))
        self.assertEqual(set(cut.SUBTITLES2), set(cut.LINES2))
        names = [shot["name"] for shot in self.shots]
        self.assertEqual(len(names), len(set(names)))
        base.LINES = self.kept
        first = {shot["name"] for shot in cut.shots(*fake_words())}
        base.LINES = cut.LINES2
        self.assertFalse(set(names) & first)                 # the first cut's recordings are not overwritten
        longer = cut.shots2(self.lengths, self.words, stretch=2.0)
        self.assertAlmostEqual(longer[-1]["beats"][-1]["pad"] - self.shots[-1]["beats"][-1]["pad"], 2.0)

    def test_the_cast_is_one_saved_run_per_model(self):
        lineup = {name for models in makers.LINEUP.values() for name in models}
        self.assertEqual(set(makers.CAST), lineup)
        for model, run in makers.CAST.items():
            self.assertTrue((RUNS / run / "artifacts" / "evaluator" / "missions" / "03" / "replay.json").exists(), run)
            self.assertEqual(makers.maker_of(model), next(key for key, models in makers.LINEUP.items() if model in models))
        self.assertEqual(set(makers.cast_tiers().values()), set(makers.TIERS))
        for run in (cut.FAST, cut.MID, cut.FLAGSHIP, cut.FLAT):
            self.assertIn(run, makers.CAST.values())

    def test_the_ladder_shows_what_the_replays_hold(self):
        fast = mission(cut.FAST, 3)                          # "misses, by three centimetres ... nine tries, one rock"
        misses, state = ticks_of(fast, "sample_failed"), fast["states"][104]
        self.assertIn(104, misses)
        reach = min(math.hypot(t["x"] - state["position"][0], t["y"] - state["position"][1]) for t in fast["world"]["targets"])
        self.assertEqual(round((reach - fast["config"]["target_radius"]) * 100), 3)
        self.assertEqual((len(misses), len(fast["result"]["samples"])), (8, 1))
        stops = ticks_of(mission(cut.MID, 3), "safety_stop")       # "freezes ... thirty times"
        self.assertEqual((stops[0], len(stops)), (302, 30))
        flagship = mission(cut.FLAGSHIP, 1)                  # "thirteen metres from home, twenty-one samples on board"
        died = next(s for s in flagship["states"] if not s["alive"])
        home = flagship["world"]["base"]
        self.assertEqual(died["tick"], 409)
        self.assertEqual(round(math.hypot(died["position"][0] - home[0], died["position"][1] - home[1])), 13)
        self.assertEqual(len(flagship["result"]["samples"]), 21)
        flat = mission(cut.FLAT, 3)                          # "drove until its battery was flat"
        self.assertEqual(next(s["tick"] for s in flat["states"] if not s["alive"]), 62)

    def test_what_the_narration_says_about_the_scores_holds(self):
        claude, reference = {}, None
        for path in sorted(RUNS.glob("campaign-*/run.json")):
            meta = json.loads(path.read_text(encoding="utf-8"))
            if meta.get("kind") == "claude":
                claude.setdefault(meta["model"].upper(), []).append(meta["reward"])
            elif meta.get("kind") == "reference":
                reference = meta["reward"]
        table = makers.tier_table(claude, reference, makers.facts()["rl"])
        self.assertEqual(len(table["rows"]), 9)
        self.assertLess(table["best_run"]["score"], reference)                              # "none beat our driver"
        for key, said in cut.SAID2["tiers"].items():                                         # "ours brought home forty-eight percent"
            self.assertEqual(table[key], said, key)
        self.assertEqual([row["mean"] for row in table["rows"]], sorted((row["mean"] for row in table["rows"]), reverse=True))
        with self.assertRaises(SystemExit):
            makers.tier_table(claude, table["best_run"]["score"], 0.3)                       # a run at the planner's score stops the build

    def test_two_of_kristjans_slides_are_in_it(self):
        scenes = {shot["name"]: shot.get("scene") for shot in self.shots}
        self.assertEqual((scenes["v2_quote"], scenes["v2_learning"], scenes["v2_reference"], scenes["v2_end"]), ("quote", "learning3", "planner", "end"))
        mine = (REPO / "tools" / "manh_demo" / "scenes.js").read_text(encoding="utf-8")
        self.assertIn("SCENES.reference(t, D, data, cues);", mine)                           # the planner slide is his scene with the methods named on top
        pilot = (REPO / "lightlag_traverse" / "pilot.py").read_text(encoding="utf-8") + (REPO / "lightlag_traverse" / "planning.py").read_text(encoding="utf-8")
        for said, found in (("EXTENDED KALMAN FILTER", "3 by 3 covariance"), ("ONLINE SLIP ESTIMATE", "_learn_slip"), ("DIJKSTRA", "Dijkstra"),
                            ("BEAM + ITERATED LOCAL SEARCH", "Iterated local search"), ("BEAM", "def beam_route")):
            self.assertIn(said, mine)
            self.assertIn(found, pilot)                                                       # the methods named are the ones in the code
        film = (REPO / "tools" / "demo_video" / "film.html").read_text(encoding="utf-8")
        for name in ("quote", "learning3", "reference", "end"):
            self.assertIn("SCENES.{} = ".format(name), film)                                  # his scenes, read from his page
        names = [shot["name"] for shot in self.shots]
        self.assertEqual(names.index("v2_quote"), names.index("v2_flagship") + 1)           # the flagship's own report follows its rover
        quote = next(shot for shot in self.shots if shot["name"] == "v2_quote")["beats"][0]
        self.assertGreater(quote["cues"][2], 60)                                              # his verdict line is left to this film's end card
        self.assertEqual(set(cut.SAID2), {"tiers", "worlds", "final"})

    def test_the_300_worlds_hold_every_model(self):
        table = makers.worlds_table()
        self.assertEqual({row["name"] for row in table["rows"]}, {name.upper() for models in makers.LINEUP.values() for name in models})
        for key, said in cut.SAID2["worlds"].items():                                        # "three hundred fresh worlds ... ninety-five times in a hundred"
            self.assertEqual(table[key], said, key)
        for row in table["rows"]:
            self.assertEqual(len(row["cells"]), table["worlds"])
            self.assertEqual(row["cells"].count("x"), row["lost"])
            self.assertEqual(row["reference_higher"] + row["wins"] + row["ties"], table["worlds"])
            self.assertGreaterEqual(row["left"], 1)
        self.assertEqual(table["pairs"], 9 * table["worlds"])
        self.assertEqual(table["reference_higher"], sum(row["reference_higher"] for row in table["rows"]))
        self.assertGreater(table["all"]["programs"], 9)                                      # the best of several, and the count over all of them is kept beside it
        self.assertGreaterEqual(table["all"]["reference_higher"] / table["all"]["pairs"], table["reference_higher"] / table["pairs"])
        scenes = (REPO / "tools" / "manh_demo" / "scenes.js").read_text(encoding="utf-8")
        self.assertIn("SCENES.worlds", scenes)
        self.assertEqual(next(shot for shot in self.shots if shot["name"] == "v2_farm")["scene"], "worlds")

    def test_the_replay_page_carries_nine_models_and_the_trained_agent(self):
        before = {path: digest(path) for path in KRISTJANS}
        with tempfile.TemporaryDirectory() as folder:
            page = pages.cast_page(Path(folder), makers.CAST)
            html = page.read_text(encoding="utf-8")
            self.assertIn("'AI run you follow'", base64.b64decode(re.search(r'id="src-app" type="application/octet-stream">([^<]+)<', html).group(1)).decode("utf-8"))
            for site in (1, 2, 3):
                data = json.loads(base64.b64decode(re.search(r'id="src-data-%d" type="application/octet-stream">([^<]+)<' % site, html).group(1)))
                labels = [run["label"] for run in data["runs"]]
                self.assertEqual(labels[0], "Reference")
                self.assertEqual(set(labels[1:]), set(makers.CAST) | {"RL agent · PPO"})
        self.assertEqual(before, {path: digest(path) for path in KRISTJANS})


class LongFilmTest(unittest.TestCase):
    """The ten-minute film (manh_demo_long): its script, its shots and the tables behind its slides."""

    def setUp(self):
        self.kept = base.LINES
        base.LINES = cut.LINES3
        self.lengths, self.words = fake_words(cut.LINES3)
        self.shots = cut.shots3(self.lengths, self.words)

    def tearDown(self):
        base.LINES = self.kept

    def test_every_line_is_spoken_once_and_in_order(self):
        spoken = []
        for shot in self.shots:
            for beat in shot["beats"]:
                if beat.get("vo"):
                    spoken.append((beat["vo"], beat.get("vo_at", 0.0)))
                previous = beat.get("vo_at", 0.0) + self.lengths.get(beat.get("vo"), 0.0)
                for extra in beat.get("more", []):
                    self.assertGreaterEqual(extra["at"], previous)                           # a line starts after the one before it has ended
                    spoken.append((extra["vo"], extra["at"]))
                    previous = extra["at"] + self.lengths[extra["vo"]]
        self.assertEqual([line for line, _ in spoken], list(cut.LINES3))
        self.assertEqual(set(cut.SUBTITLES3), set(cut.LINES3))
        names = [shot["name"] for shot in self.shots]
        self.assertEqual(len(names), len(set(names)))
        film = (REPO / "tools" / "demo_video" / "film.html").read_text(encoding="utf-8")
        mine = (REPO / "tools" / "manh_demo" / "scenes.js").read_text(encoding="utf-8")
        for shot in self.shots:
            if shot["page"] == "film":
                self.assertIn("SCENES.{} = ".format(shot["scene"]), film + mine, shot["name"])

    def test_how_every_site_ended_is_counted_from_the_results(self):
        table = makers.outcomes_table()
        self.assertEqual(len(table["rows"]), 9)
        self.assertEqual(sum(len(row["runs"]) for row in table["rows"]), 25)
        for row in table["rows"]:
            for run in row["runs"]:
                self.assertEqual(len(run["sites"]), 3)
                self.assertLessEqual(set(run["sites"]), {"home", "away", "lost", "idle"})
            self.assertEqual(sum(row["count"].values()), 3 * len(row["runs"]))
        by = {row["name"]: row for row in table["rows"]}
        self.assertEqual([run["sites"][0] for run in by["GPT-6.1 SOL"]["runs"]], ["away"] * 3)          # "on the first map it ended every run away from the lander"
        self.assertEqual(by["GPT-6.1 SOL"]["count"]["lost"] + by["GPT-6.1 SOL"]["count"]["idle"], 0)    # "never lost, never idle"
        self.assertEqual(table["labs"]["google"]["never_started"], 3)                                    # "three of nine runs never left the lander"
        self.assertEqual(table["labs"]["anthropic"]["lost"], 4)                                          # "loses rovers to the battery: four of them"
        self.assertEqual(by["CLAUDE HAIKU 5.5"]["count"], {"home": 0, "away": 0, "lost": 0, "idle": 3})
        self.assertEqual(table["rows"][0]["name"], "GEMINI 4 HYDROGEN")                                  # the best average is the fast model's
        self.assertEqual(table["rows"][0]["never_started"], 0)                                           # "all three of its runs had a program driving"
        self.assertEqual(round(table["costs"]["GPT-6 LUNA"] * 100), 3)
        self.assertEqual(round(table["costs"]["GEMINI 4 ARGON"] * 100), 191)

    def test_the_game_in_numbers(self):
        game = makers.game_facts()
        self.assertEqual((game["ticks"], game["delay"], game["tilt_percent"], game["targets_at_launch"], game["sites"]), (420, 3, 36, 38, 3))
        self.assertEqual(game["tools"], ["rules", "map", "telemetry_log", "uplink", "advance"])
        instruction = (REPO / "harbor" / "lightlag-traverse-campaign" / "instruction.md").read_text(encoding="utf-8")
        for tool in game["tools"]:
            self.assertIn("`{}`".format(tool), instruction)
        self.assertEqual(game["reference_lines"] // 100, cut.SAID3["long"]["reference_lines_hundreds"])  # "about thirteen hundred lines"
        self.assertEqual(makers.CAST3["Gemini 4 Carbon"], cut.BEST)


class NarrationKitTest(unittest.TestCase):
    """docs/manh-demo/narration-kit/: what a teammate records the narration from."""

    KIT = REPO / "docs" / "manh-demo" / "narration-kit"

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("lay_narration", self.KIT / "lay_narration.py")
        self.tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.tool)

    def test_the_kit_holds_the_films_lines_in_order(self):
        timing = json.loads((self.KIT / "timing.json").read_text(encoding="utf-8"))
        self.assertEqual([line["id"] for line in timing["lines"]], list(cut.LINES2))
        self.assertEqual({line["id"]: line["text"] for line in timing["lines"]}, cut.SUBTITLES2)
        self.assertLess(timing["seconds"], 120.0)
        for line, following in zip(timing["lines"], timing["lines"][1:]):
            self.assertLess(line["start"] + line["placeholder_seconds"], following["start"])      # the placeholder itself fits
            self.assertLessEqual(line["must_end_by"], following["start"])
        for name in (timing["film"], "narration.md", "narration.srt", "guide_voice.m4a", "README.md"):
            self.assertTrue((self.KIT / name).exists(), name)
        self.assertIn("no_narrator", timing["film"])
        sheet = (self.KIT / "narration.md").read_text(encoding="utf-8")
        for text in cut.SUBTITLES2.values():
            self.assertIn(text, sheet)

    def test_line_pauses_are_told_from_short_ones(self):
        # five lines with two-second pauses between them, a breath of 0.7 s inside the third, and silence at both ends
        quiet = [(0.0, 0.4), (5.0, 7.0), (11.0, 13.0), (15.0, 15.7), (18.0, 20.1), (24.0, 26.0), (30.0, 31.0)]
        blocks, limit = self.tool.spoken_blocks(quiet, 31.0, 5, None)
        self.assertEqual(blocks, [(0.4, 5.0), (7.0, 11.0), (13.0, 18.0), (20.1, 24.0), (26.0, 30.0)])
        self.assertAlmostEqual(limit, 1.0)
        said_twice = quiet[:3] + [(15.0, 17.0)] + quiet[4:]             # the breath is now a full pause: six blocks, and the tool says so
        self.assertEqual(len(self.tool.spoken_blocks(said_twice, 31.0, 5, None)[0]), 6)
        self.assertEqual(len(self.tool.spoken_blocks(quiet, 31.0, 5, 0.5)[0]), 6)                # --pause set too low splits at the breath

    def test_a_long_line_is_tightened_at_its_pauses_first(self):
        piece = {"start": 10.0, "end": 22.9, "pauses": [(11.5, 12.8), (15.2, 15.9), (17.5, 18.4), (21.5, 22.3)]}      # the first real take's line n8
        self.assertAlmostEqual(self.tool.tightened(piece, 0.35), 12.9 - (0.95 + 0.35 + 0.55 + 0.45))
        self.assertAlmostEqual(self.tool.tightened(piece, 2.0), 12.9)                                                  # a breath longer than every pause changes nothing
        self.assertEqual(self.tool.inner_pauses([(0.0, 1.0), (4.0, 4.6), (9.0, 12.0)], 1.0, 9.0), [(4.0, 4.6)])       # the silence around a line is not inside it

    def test_the_voice_chain_ends_at_the_films_loudness(self):
        full = {"afftdn", "agate", "deesser", "acompressor", "rubberband"}
        chain, skipped = self.tool.voice_chain(full, False, 1.0, 0.0)
        self.assertEqual(skipped, [])
        self.assertIn("loudnorm=I=-16", chain)
        self.assertLess(chain.index("afftdn"), chain.index("acompressor"))                       # cleaned before it is levelled
        self.assertIn("rubberband=pitch=0.94387", chain)
        raw, _ = self.tool.voice_chain(full, True, 0.0, 0.0)
        self.assertNotIn("equalizer", raw)
        self.assertIn("loudnorm=I=-16", raw)
        bare, skipped = self.tool.voice_chain(set(), False, 1.0, 0.0)                            # a minimal ffmpeg: the steps it lacks are named, the rest still runs
        self.assertEqual(set(skipped), {"afftdn", "agate", "deesser", "acompressor"})
        self.assertIn("asetrate", bare)


@unittest.skipIf(sound is None, "numpy, scipy and soundfile are needed for the sound tests")
class SoundTest(unittest.TestCase):
    def drive(self, speed, alive=True, chase=1.0, seconds=4):
        frames, x, t = [], 0.0, 100.0
        for _ in range(sound.FPS * seconds):
            t += 2 / sound.FPS
            x += speed * 2 / sound.FPS
            frames.append({"t": round(t, 3), "playing": True, "chase": chase, "weight": 0.0, "follow": "a", "x": x, "y": 0.0,
                           "alive": alive, "moving": speed > 0, "ground": 0, "slope": 0.0, "battery": 0.5, "locks": [], "events": []})
        return frames

    @staticmethod
    def level(x):
        return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)

    def test_the_meter_reads_a_known_tone(self):
        t = np.arange(10 * sound.RATE) / sound.RATE
        tone = np.stack([np.sin(2 * np.pi * 997 * t)] * 2, axis=1) * sound.db(-18)
        self.assertAlmostEqual(sound.loudness(tone), -18.0, delta=0.1)               # BS.1770: full scale in both channels reads 0

    def test_a_clip_of_any_length_has_a_bed_of_the_same_length(self):
        for seconds in (10.2, 14.533, 3.0):                                              # 10.2 s is 489599.99... samples before rounding
            n = int(round(seconds * sound.RATE))
            self.assertEqual(sound.wind(seconds, np.ones(n), 7).shape, (n, 2))
            self.assertEqual(sound.music(seconds, np.ones(n), 3).shape, (n, 2))
            self.assertEqual(sound.ramps(seconds, [(0.0, 0.0), (seconds, 1.0)]).shape, (n,))

    def test_every_sound_renders(self):
        rng = np.random.default_rng(1)
        for kind in ("tick", "tock", "chime", "chime_soft", "bar", "flow", "swell", "riser", "hit", "hit_soft", "typing", "whoosh", "cut",
                     "transition", "lock", "card", "way", "sample", "late", "miss", "stop", "warn", "thump"):
            clip, lead = sound.render({"kind": kind, "len": 1.0}, rng)
            self.assertEqual(clip.shape[1], 2, kind)
            self.assertTrue(np.isfinite(clip).all(), kind)
            self.assertLess(np.abs(clip).max(), 0.5, kind)
            self.assertGreaterEqual(lead, 0.0, kind)
        with self.assertRaises(ValueError):
            sound.render({"kind": "no such sound"}, rng)

    def test_the_rover_is_heard_only_when_it_drives_and_from_close(self):
        driving, parked = self.level(sound.rover_shot(self.drive(4.8), 1)), self.level(sound.rover_shot(self.drive(0.0), 1))
        dead, above = self.level(sound.rover_shot(self.drive(0.0, alive=False), 1)), self.level(sound.rover_shot(self.drive(4.8, chase=0.0), 1))
        self.assertGreater(driving, parked + 12)
        self.assertLess(dead, -90)
        self.assertGreater(driving, above + 6)
        self.assertLess(driving, -30)                                                # it stays a background sound

    def test_a_small_film_is_mixed_with_the_voice_on_top(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            (folder / "voice").mkdir()
            (folder / "tele").mkdir()
            rng = np.random.default_rng(3)
            t = np.arange(int(2.0 * 24000)) / 24000
            speech = np.sin(2 * np.pi * 180 * t) * (0.3 + 0.2 * np.sin(2 * np.pi * 3 * t)) + 0.05 * rng.standard_normal(len(t))
            sf.write(str(folder / "voice" / "a1.wav"), speech, 24000, subtype="PCM_16")
            import json
            (folder / "tele" / "cold.json").write_text(json.dumps(self.drive(4.8, seconds=3)))
            timeline = [{"name": "cold", "page": "campaign", "seconds": 3.0, "lines": [{"line": "a1", "at": 0.4}], "thumps": [2.5], "sfx": []},
                        {"name": "results", "page": "film", "seconds": 3.0, "lines": [], "thumps": [], "sfx": [{"at": 0.7, "kind": "bar", "score": 0.4}]}]
            report = sound.build(timeline, [{"line": "a1", "at": 0.4}], folder)
            mix, rate = sf.read(str(report["mix"]))
            self.assertEqual((rate, mix.shape), (sound.RATE, (6 * sound.RATE, 2)))
            voice, _ = sf.read(str(folder / "audio" / "voice.wav"))
            self.assertAlmostEqual(sound.loudness(voice), sound.VOICE_LUFS, delta=1.0)
            self.assertLess(np.abs(mix).max(), 1.0)
            quiet, _ = sf.read(str(sound.build(timeline, [{"line": "a1", "at": 0.4}], folder, mute=["rover", "charts", "music", "wind"])["mix"]))
            self.assertLess(self.level(quiet[int(4.0 * rate):int(5.0 * rate)]), -80)  # with every layer muted, nothing but the voice
            alone, _ = sf.read(str(sound.build(timeline, [{"line": "a1", "at": 0.4}], folder, mute=["voice"], into="audio-clip", whole=False)["mix"]))
            said = slice(int(0.6 * rate), int(2.2 * rate))
            self.assertLess(self.level(alone[said]), self.level(mix[said]) - 10)      # the film without its narration
            self.assertTrue((folder / "audio-clip" / "mix.wav").exists())
            with self.assertRaises(SystemExit):
                sound.build(timeline, [], folder, mute=["drums"])
            with self.assertRaises(SystemExit):
                sound.voice_bus([{"line": "a1", "at": 0.4}], folder / "voice", 6.0, "robot")


if __name__ == "__main__":
    unittest.main()
