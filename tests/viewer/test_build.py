"""The replay viewer's build step. Standard library only.

    python3 -m unittest discover -s tests/viewer -v

The page itself is checked by opening it in a browser; these tests cover what the
build embeds.
"""

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "viewer"))
import build  # noqa: E402


def embedded(page):
    match = re.search(r'<script id="embedded-replays" type="application/json">(.*?)</script>', page, re.S)
    return json.loads(match.group(1).replace("<\\/", "</"))


class Build(unittest.TestCase):
    def test_a_recorded_policy_is_embedded_with_its_belief_track(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "page.html"
            self.assertEqual(build.main(["--out", str(out), "--seed", "3", "--delay", "3", "Reference=policy:reference"]), 0)
            entries = embedded(out.read_text(encoding="utf-8"))
        self.assertEqual([e["label"] for e in entries], ["Reference"])
        replay = entries[0]["replay"]
        self.assertEqual(replay["version"], "lightlag-replay-v1")
        self.assertEqual(len(replay["states"]), replay["config"]["max_ticks"] + 1)
        belief = entries[0]["belief"]
        self.assertGreater(len(belief), 5)
        for note in belief:
            truth = replay["states"][note["tick"]]["position"]
            error = ((note["position"][0] - truth[0]) ** 2 + (note["position"][1] - truth[1]) ** 2) ** 0.5
            self.assertLess(error, 0.75, note)

    def test_a_replay_file_is_embedded_unchanged_and_without_a_belief_track(self):
        source = REPO / "docs" / "lightlag-runs" / "reference-seed7-delay3" / "artifacts" / "evaluator" / "replay.json"
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "page.html"
            build.main(["--out", str(out), "Harbor run={}".format(source)])
            entries = embedded(out.read_text(encoding="utf-8"))
        self.assertEqual(entries[0]["replay"], json.loads(source.read_text(encoding="utf-8")))
        self.assertEqual(entries[0]["belief"], [])

    def test_the_locally_recorded_reference_reproduces_the_harbor_run(self):
        """Same seed and delay: the container run and a local run give the same rover states."""
        source = REPO / "docs" / "lightlag-runs" / "reference-seed7-delay3" / "artifacts" / "evaluator" / "replay.json"
        harbor = json.loads(source.read_text(encoding="utf-8"))
        local = build.record("reference", seed=harbor["seed"], delay=harbor["config"]["delay_ticks"])["replay"]
        self.assertEqual(local["states"], harbor["states"])
        self.assertEqual(local["result"], harbor["result"])

    def test_non_replay_input_and_unknown_policies_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "bad.json"
            bad.write_text("{}", encoding="utf-8")
            with self.assertRaises(SystemExit):
                build.main(["--out", str(Path(directory) / "page.html"), "x={}".format(bad)])
            with self.assertRaises(SystemExit):
                build.main(["--out", str(Path(directory) / "page.html"), "x=policy:teleport"])


if __name__ == "__main__":
    unittest.main()
