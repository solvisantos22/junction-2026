"""The MAX-map model baseline: the request, the frozen protocol, the paid step's guards and the sandbox.

    python3 -m unittest discover -s tests/lightlag_traverse_max -p "test_oneshot.py" -v

Standard library only. Nothing here sends anything to an API: the paid step is driven by a stand-in.
The sandbox tests need bwrap, prlimit and Python 3.12 and are skipped without them; one replays
Kristján's normal-map Opus program (about 15 seconds).
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from lightlag_traverse import oneshot as kristjans  # noqa: E402
from lightlag_traverse_max import oneshot, sandbox  # noqa: E402
from lightlag_traverse_max.environment import make_env  # noqa: E402

KRISTJANS_OPUS = REPO / "docs" / "lightlag-runs" / "traverse-oneshot-opus-1"


class RequestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = oneshot.build_request()

    def test_every_placeholder_is_filled_and_the_max_map_is_described(self):
        for token in ("MAX_TICKS", "WIDTH", "HEIGHT", "TARGETS", "RULES_JSON", "MAP_TEXT", "FIRST_PACKET",
                      "ACK_JSON", "ADVANCE_JSON", "ADVANCE8_JSON", "SURFACE_SOURCE"):
            self.assertNotIn(token, self.text)
        self.assertIn("## This is the MAX map", self.text)
        self.assertIn('"crust_regions"', self.text)
        self.assertIn('{"current_tick": 8, "episode_complete": false, "packets": [{"tick": 1,', self.text)

    def test_kristjans_instruction_is_all_there_with_the_max_section_added(self):
        normal = kristjans.build_request().split("## The rules")[0].splitlines()
        hard = iter(self.text.split("## The rules")[0].splitlines())
        self.assertTrue(all(line in hard for line in normal), "every line of his, in order")

    def test_the_rules_shown_are_the_max_maps_public_rules_and_hide_what_is_hidden(self):
        env = make_env(kristjans.EXAMPLE_SEED, "max")
        shown = json.loads(self.text.split("## The rules: the output of `rules()`\n\n```json\n")[1].split("\n```")[0])
        self.assertEqual(shown, env.rules())
        self.assertEqual(shown["map_option"], "max")
        self.assertEqual(shown["physics"]["slip_grade_gain"]["sand"], 3.5)
        self.assertNotEqual(env._physics["slip_grade_gain"]["sand"], 3.5)

    def test_the_request_is_the_same_every_time(self):
        self.assertEqual(oneshot.build_request(), self.text)


@unittest.skipUnless((oneshot.BASELINE / "freeze.json").exists(), "the baseline is not frozen yet")
class FrozenTest(unittest.TestCase):
    def test_the_frozen_request_and_mission_are_what_the_code_makes_today(self):
        frozen = oneshot.load_frozen()
        self.assertEqual((oneshot.BASELINE / "request.md").read_text(encoding="utf-8"), oneshot.build_request())
        self.assertEqual(frozen["mission_files_sha256"], oneshot.mission_hashes(),
                         "the mission changed after the freeze: results would not be comparable")
        self.assertEqual((frozen["hard_worlds"], frozen["task_world"], frozen["models"], frozen["effort"],
                          frozen["max_tokens"], frozen["samples_per_model"]),
                         (list(oneshot.HARD_WORLDS), oneshot.TASK_WORLD, dict(oneshot.MODELS), oneshot.EFFORT,
                          oneshot.MAX_TOKENS, oneshot.SAMPLES))


class AskTest(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp(prefix="max-baseline-tests-"))
        self.addCleanup(shutil.rmtree, self.out, ignore_errors=True)
        text = "a stand-in request"
        (self.out / "request.md").write_text(text, encoding="utf-8")
        (self.out / "freeze.json").write_text(json.dumps({
            "request": {"sha256": oneshot.sha256(text.encode()), "characters": len(text)},
            "effort": "medium", "max_tokens": oneshot.MAX_TOKENS}), encoding="utf-8")
        self.sent = []

    def send(self, request, folder, model, error=None):
        self.sent.append(folder.name)
        folder.mkdir(parents=True)
        meta = {"model": model, "error": error} if error else {
            "model": model, "cost_usd": 0.01, "stop_reason": "end_turn", "has_play": True}
        (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        return 1 if error else 0

    def quietly(self, *args, **kwargs):
        with redirect_stdout(io.StringIO()):
            return oneshot.ask(*args, **kwargs)

    def test_every_reply_is_asked_once(self):
        self.assertEqual(self.quietly(100.0, self.out, send=self.send), 0)
        self.assertEqual(sorted(self.sent), sorted("{}-{}".format(m, k) for m, _ in oneshot.MODELS for k in (1, 2, 3)))
        self.sent.clear()
        self.assertEqual(self.quietly(100.0, self.out, send=self.send), 0)
        self.assertEqual(self.sent, [])
        self.assertEqual(len((self.out / "asks.jsonl").read_text().splitlines()), 9)

    def test_no_call_is_sent_whose_worst_case_would_pass_the_budget(self):
        haiku = oneshot.worst_case_usd("claude-haiku-5-5", len("a stand-in request"))
        self.assertLess(haiku, 0.07)
        self.assertGreater(oneshot.worst_case_usd("claude-sonnet-5-5", 10), 1.2)
        self.assertEqual(self.quietly(1.5 * haiku, self.out, send=self.send), 1)
        self.assertEqual(sorted(self.sent), ["haiku-1", "haiku-2", "haiku-3"])

    def test_a_call_that_brought_no_reply_is_asked_again_and_its_attempt_kept(self):
        models = (("haiku", "claude-haiku-5-5"),)
        failing = lambda request, folder, model: self.send(request, folder, model, error="api status 529")  # noqa: E731
        self.assertEqual(self.quietly(100.0, self.out, send=failing, models=models, samples=1), 1)
        self.assertEqual(self.quietly(100.0, self.out, send=self.send, models=models, samples=1), 0)
        self.assertTrue((self.out / "replies" / "haiku-1.no-reply-1" / "meta.json").exists())
        self.assertEqual(json.loads((self.out / "replies" / "haiku-1" / "meta.json").read_text())["cost_usd"], 0.01)

    def test_a_changed_request_is_refused(self):
        (self.out / "request.md").write_text("another request", encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.quietly(100.0, self.out, send=self.send)
        self.assertEqual(self.sent, [])

    def test_the_key_is_read_from_the_file_and_never_printed(self):
        env_file = self.out / ".env"
        env_file.write_text("OTHER=1\nexport ANTHROPIC_API_KEY='sk-test-not-a-key'\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(oneshot.KEY, None)
            printed = io.StringIO()
            with redirect_stdout(printed):
                oneshot.load_key(env_file)
            self.assertEqual(os.environ[oneshot.KEY], "sk-test-not-a-key")
        self.assertNotIn("sk-test", printed.getvalue())


POLICIES = {
    "probe": """
import os, socket
def play(tools):
    seen = [(p, os.path.exists(p)) for p in ("/home", "/etc/passwd", "/root")]
    try:
        socket.create_connection(("1.1.1.1", 80), timeout=2)
        net = "open"
    except OSError:
        net = "blocked"
    tools.uplink([{"action": "wait"}])
    raise RuntimeError("seen={} net={} uid={}".format(seen, net, os.getuid()))
""",
}


@unittest.skipUnless(sandbox.available(), "needs bwrap, prlimit and {}".format(sandbox.PYTHON))
class SandboxTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="max-sandbox-tests-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_the_program_has_no_network_no_home_and_runs_as_nobody(self):
        policy = self.root / "probe.py"
        policy.write_text(POLICIES["probe"], encoding="utf-8")
        summary = sandbox.run(policy, self.root / "out", 515)
        self.assertEqual(summary["status"], "returned")
        self.assertEqual(summary["map"], "max")
        (error,) = summary["errors"]
        self.assertIn("('/home', False), ('/etc/passwd', False), ('/root', False)", error)
        self.assertIn("net=blocked", error)
        self.assertIn("uid=65534", error)

    def test_the_mission_behind_it_is_the_map_asked_for(self):
        self.assertEqual(sandbox.MaxEpisodeService(5).call("rules")["map_option"], "max")
        self.assertNotIn("map_option", sandbox.MaxEpisodeService(5, option="normal").call("rules"))

    @unittest.skipUnless((KRISTJANS_OPUS / "policy.py").exists(), "Kristján's Opus run is not here")
    def test_it_replays_kristjans_docker_run_of_his_opus_program_byte_for_byte(self):
        summary = sandbox.run(KRISTJANS_OPUS / "policy.py", self.root / "opus", 2026, "normal")
        self.assertEqual(summary["status"], "returned")
        for name in ("replay.json", "result.json"):
            self.assertEqual((self.root / "opus" / "artifacts" / "evaluator" / name).read_bytes(),
                             (KRISTJANS_OPUS / "artifacts" / "evaluator" / name).read_bytes(), name)


if __name__ == "__main__":
    unittest.main()
