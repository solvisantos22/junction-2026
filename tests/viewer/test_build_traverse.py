"""The traverse demo's data and build step. Standard library only.

    python3 -m unittest discover -s tests/viewer -p "test_build_traverse.py" -v

The page's looks are checked by opening it in a browser. These tests cover what it is fed: that
the scores shown are the saved ones, that every run shown played the reference's world, and that
the standalone page holds exactly its sources. They need no saved run: two cheap ones are played
here with the simulator (a rover that drives straight at its targets stands in as the reference,
one that never moves as a scripted run) and saved the way real runs are. The committed page is
checked against its sources once real runs exist under docs/lightlag-runs/traverse-*.
"""

import base64
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
import build_traverse  # noqa: E402
from lightlag_traverse.environment import TraverseEnvironment  # noqa: E402
from lightlag_traverse.play import POLICIES, run_episode, save_run  # noqa: E402

SEED = 5
SHORT = 60                      # ticks of the short mission that checks nothing is sized for 420
COMMITTED = build_traverse.run_folders(build_traverse.RUNS)
# The committed page is built from the repository's own runs once they include the reference they are measured against.
REFERENCED = any(json.loads((folder / "run.json").read_text(encoding="utf-8")).get("kind") == "reference" for folder in COMMITTED)
ROOT = FOLDERS = DATA = RUNS = None


def play(folder: Path, policy: str, seed: int, kind: str) -> Path:
    run = run_episode(POLICIES[policy], seed, keep_replay=True)
    save_run(folder, run, {"kind": kind, "label": policy, "model": "", "how": "played by the tests"})
    return folder


def setUpModule():
    global ROOT, FOLDERS, DATA, RUNS
    ROOT = Path(tempfile.mkdtemp(prefix="traverse-demo-tests-"))
    unittest.addModuleCleanup(shutil.rmtree, ROOT, ignore_errors=True)
    play(ROOT / "runs" / "traverse-straight", "straight", SEED, "reference")
    play(ROOT / "runs" / "traverse-nothing", "nothing", SEED, "scripted")
    (ROOT / "runs" / "traverse-unfinished").mkdir()          # no run.json: not a run
    (ROOT / "runs" / "live-other-task").mkdir()
    (ROOT / "runs" / "live-other-task" / "run.json").write_text("{}", encoding="utf-8")
    FOLDERS = build_traverse.run_folders(ROOT / "runs")
    DATA = build_traverse.gather(FOLDERS)
    RUNS = {run["id"]: run for run in DATA["runs"]}


def saved(folder: Path, name: str):
    return json.loads((folder / "artifacts" / "evaluator" / name).read_text(encoding="utf-8"))


def altered(name: str, source: str, change) -> Path:
    """A copy of one of the played runs with its run.json, result and replay passed through `change`."""
    folder = ROOT / "altered" / name
    shutil.copytree(ROOT / "runs" / source, folder)
    meta = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    result, replay = saved(folder, "result.json"), saved(folder, "replay.json")
    change(meta, result, replay)
    (folder / "run.json").write_text(json.dumps(meta), encoding="utf-8")
    (folder / "artifacts" / "evaluator" / "result.json").write_text(json.dumps(result), encoding="utf-8")
    (folder / "artifacts" / "evaluator" / "replay.json").write_text(json.dumps(replay), encoding="utf-8")
    return folder


class GatheredRuns(unittest.TestCase):
    def test_only_traverse_folders_with_a_run_json_are_runs(self):
        self.assertEqual([folder.name for folder in FOLDERS], ["traverse-nothing", "traverse-straight"])

    def test_the_reference_comes_first_and_the_others_follow_best_first(self):
        kinds = [run["kind"] for run in DATA["runs"]]
        self.assertEqual(kinds[0], "reference")
        self.assertNotIn("reference", kinds[1:])
        rewards = [run["reward"] for run in DATA["runs"][1:]]
        self.assertEqual(rewards, sorted(rewards, reverse=True))
        self.assertEqual(DATA["best"], DATA["runs"][1]["id"])

    def test_the_scores_shown_are_the_saved_ones(self):
        for folder in FOLDERS:
            result, run = saved(folder, "result.json"), RUNS[folder.name]
            self.assertEqual(run["reward"], result["raw_score"] / result["max_available_value"])
            self.assertEqual((run["raw"], run["max"]), (result["raw_score"], result["max_available_value"]))
            self.assertEqual((run["alive"], run["home"]), (result["alive"], result["at_base"]))
            self.assertEqual([(s["id"], s["t"], s["v"], s["ok"]) for s in run["samples"]],
                             [(s["target_id"], s["tick"], s["credited_value"], s["on_time"]) for s in result["samples"]])
        self.assertEqual(RUNS["traverse-nothing"]["reward"], 0)          # a rover that never moves samples nothing

    def test_every_run_has_one_state_per_tick_and_starts_at_base(self):
        ticks, base = DATA["config"]["ticks"], DATA["world"]["base"]
        self.assertEqual(ticks, saved(FOLDERS[0], "replay.json")["config"]["max_ticks"])
        for run in DATA["runs"]:
            self.assertEqual(len(run["p"]), 2 * (ticks + 1), run["id"])
            self.assertEqual(len(run["b"]), ticks + 1, run["id"])
            self.assertEqual(run["p"][:2], base, run["id"])
            self.assertEqual(run["seen"][:2], base, run["id"])               # the tick-0 briefing is exact
            self.assertEqual(len(run["seen"]), 2 * (ticks + 1 - DATA["config"]["delay"]), run["id"])

    def test_the_tracks_are_the_replays_positions(self):
        for folder in FOLDERS:
            states, run = saved(folder, "replay.json")["states"], RUNS[folder.name]
            for tick in (0, 1, len(states) // 2, len(states) - 1):
                self.assertAlmostEqual(run["p"][2 * tick], states[tick]["position"][0], delta=0.006)
                self.assertAlmostEqual(run["p"][2 * tick + 1], states[tick]["position"][1], delta=0.006)
                self.assertAlmostEqual(run["b"][tick], states[tick]["battery"], delta=0.051)

    def test_the_height_grid_is_embedded_once_and_whole(self):
        world, replay = DATA["world"], saved(FOLDERS[0], "replay.json")
        self.assertEqual(world["elevation_cm"], [value for row in replay["world"]["elevation_cm"] for value in row])
        self.assertEqual(len(world["elevation_cm"]), world["nx"] * world["ny"])
        self.assertEqual((len(world["terrain"]), len(world["terrain"][0])), (world["ny"] - 1, world["nx"] - 1))
        self.assertEqual((world["width"], world["height"]), ((world["nx"] - 1) * world["cell"], (world["ny"] - 1) * world["cell"]))
        self.assertEqual([t["id"] for t in world["targets"]], [t["id"] for t in replay["world"]["targets"]])
        self.assertEqual(json.dumps(DATA).count(json.dumps(world["elevation_cm"][:200])[1:-1]), 1)
        for run in DATA["runs"]:
            self.assertNotIn("world", run)

    def test_samples_stops_and_losses_are_inside_the_mission(self):
        ids, ticks = {target["id"] for target in DATA["world"]["targets"]}, DATA["config"]["ticks"]
        for run in DATA["runs"]:
            for sample in run["samples"]:
                self.assertIn(sample["id"], ids)
                self.assertTrue(0 < sample["t"] <= ticks)
            for event in run["events"]:
                self.assertIn(event["k"], ("miss", "stop", "dead"))
                self.assertTrue(0 < event["t"] <= ticks)
            self.assertEqual(any(event["k"] == "dead" for event in run["events"]), not run["alive"], run["id"])
        replay = saved(ROOT / "runs" / "traverse-straight", "replay.json")
        stops = [state["tick"] for state in replay["states"] for event in state["events"] if event["type"] == "safety_stop"]
        self.assertEqual([event["t"] for event in RUNS["traverse-straight"]["events"] if event["k"] == "stop"], stops)

    def test_a_scripted_run_is_called_a_stand_in_and_never_a_claude_run(self):
        self.assertEqual(RUNS["traverse-nothing"]["who"], "scripted stand-in")
        self.assertIn("scripted stand-in", DATA["pitch"])
        self.assertNotIn("Claude", DATA["pitch"])
        with_claude = build_traverse.gather(FOLDERS + [altered("traverse-model", "traverse-nothing",
                                                              lambda meta, result, replay: meta.update(kind="claude"))])
        self.assertEqual({run["id"]: run["who"] for run in with_claude["runs"]},
                         {"traverse-straight": "reference", "traverse-nothing": "scripted stand-in", "traverse-model": "Claude run"})
        self.assertEqual(with_claude["best"], "traverse-model")          # the page opens on a model's run when there is one
        self.assertIn("1 of the others is a scripted stand-in, not a model run", with_claude["pitch"])


class Refusals(unittest.TestCase):
    def refused(self, folders, words):
        with self.assertRaises(SystemExit) as caught:
            build_traverse.gather(folders)
        self.assertIn(words, str(caught.exception))

    def test_a_run_on_a_different_seed_is_refused(self):
        elsewhere = play(ROOT / "elsewhere" / "traverse-nothing", "nothing", SEED + 1, "scripted")
        self.refused(FOLDERS + [elsewhere], "did not play the reference's world")

    def test_a_run_on_changed_ground_or_under_changed_rules_is_refused(self):
        def raise_a_vertex(meta, result, replay):
            replay["world"]["elevation_cm"][3][3] += 1

        def longer_delay(meta, result, replay):
            replay["config"]["delay_ticks"] += 1

        self.refused(FOLDERS + [altered("traverse-ground", "traverse-nothing", raise_a_vertex)], "did not play the reference's world")
        self.refused(FOLDERS + [altered("traverse-rules", "traverse-nothing", longer_delay)], "did not play the reference's world")

    def test_exactly_one_reference_is_needed(self):
        self.refused([ROOT / "runs" / "traverse-nothing"], "exactly one run must have kind 'reference'")
        second = altered("traverse-second", "traverse-nothing", lambda meta, result, replay: meta.update(kind="reference"))
        self.refused(FOLDERS + [second], "exactly one run must have kind 'reference'")
        self.refused([], "no runs found")

    def test_a_kind_the_page_has_no_words_for_is_refused(self):
        self.refused(FOLDERS + [altered("traverse-kind", "traverse-nothing", lambda meta, result, replay: meta.update(kind="human"))],
                     "kind must be one of")

    def test_a_result_that_disagrees_with_its_replay_is_refused(self):
        def better_score(meta, result, replay):
            result["raw_score"] += 1.0

        self.refused(FOLDERS + [altered("traverse-score", "traverse-nothing", better_score)], "disagree on raw_score")

    def test_a_replay_cut_short_is_refused(self):
        def cut(meta, result, replay):
            del replay["states"][-1]

        self.refused(FOLDERS + [altered("traverse-cut", "traverse-nothing", cut)], "one state per tick")


class ShorterMission(unittest.TestCase):
    """Nothing is sized for one mission: a 60-tick mission with the reference alone gathers at its own length."""

    def setUp(self):
        folder = ROOT / "short" / "traverse-reference"
        if not folder.exists():
            env = TraverseEnvironment(SEED, mission={"max_ticks": SHORT})
            while not env.advance(5)["episode_complete"]:
                pass
            save_run(folder, {"result": env.evaluate(), "replay": env.replay()}, {"kind": "reference", "label": "Reference"})
        self.data = build_traverse.gather(build_traverse.run_folders(folder.parent))

    def test_it_is_gathered_at_its_own_length(self):
        run = self.data["runs"][0]
        self.assertEqual(self.data["config"]["ticks"], SHORT)
        self.assertEqual((len(run["p"]), len(run["b"])), (2 * (SHORT + 1), SHORT + 1))
        self.assertIn("{} ticks".format(SHORT), self.data["pitch"])
        self.assertTrue(all(t["deadline"] is None or t["deadline"] <= SHORT for t in self.data["world"]["targets"]))

    def test_the_reference_alone_is_a_page_with_nobody_to_follow(self):
        self.assertEqual([run["kind"] for run in self.data["runs"]], ["reference"])
        self.assertIsNone(self.data["best"])
        self.assertIn("No other run", self.data["pitch"])
        self.assertNotIn("Claude", self.data["pitch"])


class StandalonePage(unittest.TestCase):
    def setUp(self):
        self.page = build_traverse.standalone(DATA)

    def embedded(self, element):
        match = re.search(r'<script id="{}" type="application/octet-stream">([^<]+)</script>'.format(element), self.page)
        return base64.b64decode(match.group(1))

    def test_it_is_one_file_with_no_outside_references(self):
        self.assertNotIn("<!--DEV-->", self.page)
        self.assertNotIn('href="style.css"', self.page)
        self.assertNotIn("importmap", self.page)
        self.assertNotIn("fetch(", self.page.split("<body>")[0].split('<script id="src-core"')[0])
        for needle in ('src="http', "href=\"http", "cdn.", "url(http", "@import"):
            self.assertNotIn(needle, self.page)
        for source in (build_traverse.TRAVERSE / "app.js", build_traverse.TRAVERSE / "style.css"):
            text = source.read_text(encoding="utf-8")
            for needle in ("http://", "https://", "fetch(", "XMLHttpRequest", "WebSocket"):
                self.assertNotIn(needle, text, source.name)

    def test_the_embedded_data_is_exactly_the_gathered_runs(self):
        self.assertEqual(json.loads(self.embedded("src-data")), json.loads(json.dumps(DATA)))

    def test_the_embedded_app_and_library_are_the_files_in_the_repository(self):
        for element, path in (("src-app", build_traverse.TRAVERSE / "app.js"),
                              ("src-three", build_traverse.VENDOR / "three.module.js"),
                              ("src-core", build_traverse.VENDOR / "three.core.js")):
            self.assertEqual(self.embedded(element), path.read_bytes(), path.name)
        self.assertIn(build_traverse.TRAVERSE.joinpath("style.css").read_text(encoding="utf-8"), self.page)

    def test_the_app_names_its_library_once_so_the_page_can_point_it_at_the_embedded_copy(self):
        self.assertEqual((build_traverse.TRAVERSE / "app.js").read_text(encoding="utf-8").count("'three'"), 1)


@unittest.skipUnless(REFERENCED, "no traverse reference run under docs/lightlag-runs/traverse-* yet")
class CampaignPages(unittest.TestCase):
    """One page per world of a campaign, all in one file, from runs saved the way the campaign task saves them."""

    @classmethod
    def setUpClass(cls):
        from lightlag_traverse.campaign import TraverseCampaignService
        from lightlag_traverse.pilot import fly_campaign
        cls.root = ROOT / "campaign"
        short = {"max_ticks": SHORT}

        def save(name, kind, play):
            folder = cls.root / name
            service = TraverseCampaignService((SEED, SEED + 1), artifact_dir=str(folder / "artifacts" / "evaluator"),
                                              mission=short)
            play(service)
            service.finish()
            (folder / "run.json").write_text(json.dumps({"kind": kind, "label": name, "how": "played by the tests"}),
                                             encoding="utf-8")

        quick = {"plan_steps": 2000, "replan_steps": 400, "beam": 10, "rebeam": 5}
        save("campaign-pilot", "reference", lambda service: fly_campaign(service, quick))
        save("campaign-idle", "claude", lambda service: None)
        save("campaign-nothing", "baseline", lambda service: None)       # a kind the page does not show
        cls.pages = build_traverse.campaign(cls.root)

    def test_there_is_one_page_per_world_and_each_says_which_it_is(self):
        self.assertEqual([page["site"] for page in self.pages], [1, 2])
        self.assertEqual([page["seed"] for page in self.pages], [SEED, SEED + 1])
        for page in self.pages:
            self.assertEqual(page["brand"], "SITE {} / 2".format(page["site"]))
            self.assertEqual([site["n"] for site in page["sites"]], [1, 2])
            self.assertEqual([run["id"] for run in page["runs"]], ["campaign-pilot", "campaign-idle"])

    def test_each_run_carries_its_score_over_the_whole_campaign(self):
        folder = self.root / "campaign-pilot" / "artifacts" / "evaluator"
        overall = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        for page in self.pages:
            pilot = next(run for run in page["runs"] if run["id"] == "campaign-pilot")
            self.assertAlmostEqual(pilot["campaign"], overall["raw_score"] / overall["max_available_value"], places=6)
            idle = next(run for run in page["runs"] if run["id"] == "campaign-idle")
            self.assertEqual(idle["campaign"], 0.0)
        self.assertEqual([page["runs"][0]["reward"] for page in self.pages], overall["mission_rewards"])

    def test_the_page_holds_every_world_and_opens_the_one_asked_for(self):
        html = build_traverse.standalone(self.pages)
        for number, page in enumerate(self.pages, 1):
            element = re.search(r'<script id="src-data-{}" type="application/octet-stream">([^<]*)</script>'.format(number), html)
            self.assertEqual(json.loads(base64.b64decode(element.group(1))), json.loads(json.dumps(page)))
        self.assertIn("text('src-data-' + site)", html)
        self.assertIn("Math.min(2,", html)

    def test_a_world_where_one_run_played_other_ground_is_refused(self):
        bad = self.root.parent / "campaign-bad"
        shutil.copytree(self.root, bad)
        replay = bad / "campaign-idle" / "artifacts" / "evaluator" / "missions" / "02" / "replay.json"
        data = json.loads(replay.read_text(encoding="utf-8"))
        data["seed"] += 100
        replay.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(SystemExit):
            build_traverse.campaign(bad)


class CommittedPage(unittest.TestCase):
    def test_the_committed_campaign_page_is_up_to_date(self):
        if not build_traverse.run_folders(build_traverse.RUNS, "campaign-"):
            self.skipTest("no campaign runs saved yet")
        self.assertEqual((REPO / "viewer" / "traverse-campaign.html").read_text(encoding="utf-8"),
                         build_traverse.standalone(build_traverse.campaign(build_traverse.RUNS)),
                         "run: python3 viewer/build_traverse.py --campaign")

    def test_the_committed_page_and_data_are_up_to_date(self):
        data, hint = build_traverse.gather(COMMITTED), "run: python3 viewer/build_traverse.py"
        self.assertEqual((REPO / "viewer" / "traverse-demo.html").read_text(encoding="utf-8"), build_traverse.standalone(data), hint)
        self.assertEqual(json.loads((build_traverse.TRAVERSE / "data.json").read_text(encoding="utf-8")),
                         json.loads(json.dumps(data)), hint)

    def test_no_run_is_shown_as_a_claude_run_unless_its_run_json_says_so(self):
        data = build_traverse.gather(COMMITTED)
        for folder in COMMITTED:
            kind = json.loads((folder / "run.json").read_text(encoding="utf-8"))["kind"]
            self.assertEqual(next(run["who"] for run in data["runs"] if run["id"] == folder.name), build_traverse.KINDS[kind])


if __name__ == "__main__":
    unittest.main()
