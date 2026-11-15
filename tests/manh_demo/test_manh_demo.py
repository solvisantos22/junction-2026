"""manh_demo_1, the parts that need no browser, no Docker and no sound card.

    python3 -m unittest discover -s tests/manh_demo -v

The logo registry, the build-time copies of Kristján's pages (and that his files are left as
they were), this cut's changes to his storyboard, and the synthesised sound. The sound tests
need numpy, scipy and soundfile and are skipped without them.
"""

import base64
import hashlib
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


def fake_words():
    """Word timings as the voice model would report them: every token a third of a second after the last."""
    words, lengths = {}, {}
    for key, text in base.LINES.items():
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
