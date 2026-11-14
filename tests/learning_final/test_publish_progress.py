"""Publisher safety tests against disposable bare Git remotes and fake milestones."""
import copy
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.learning_final import publish_progress as publisher

NOW = 1794687000.


def git(root, *args):
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)
    return result.stdout.strip()


class PublisherTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="learning-progress-git-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.remote = self.root / "remote.git"
        git(self.root, "init", "--bare", "--initial-branch=main", str(self.remote))
        self.seed = self.root / "seed"
        git(self.root, "clone", str(self.remote), str(self.seed))
        for key, value in (("user.name", "Synthetic test"), ("user.email", "test@example.invalid")):
            git(self.seed, "config", key, value)
        (self.seed / "AGENTS.md").write_text("Synthetic workflow instructions\n")
        (self.seed / publisher.WORKFLOW).parent.mkdir(parents=True)
        (self.seed / publisher.WORKFLOW).write_text("Synthetic coordination workflow\n")
        (self.seed / "teammate.txt").write_text("preserve original teammate work\n")
        git(self.seed, "add", ".")
        git(self.seed, "commit", "-m", "initial fixture")
        git(self.seed, "push", "origin", "main")
        self.checkout = self.root / "publish"
        git(self.root, "clone", str(self.remote), str(self.checkout))
        git(self.checkout, "switch", "-c", "test-progress-publisher")
        for key, value in (("user.name", "Synthetic publisher"), ("user.email", "test@example.invalid")):
            git(self.checkout, "config", key, value)
        self.private = self.root / "private"
        self.private.mkdir()
        self.monitor = self.private / "monitor"
        self.monitor.mkdir()
        self.monitor_state()
        self.freeze = self.private / "freeze.json"
        self.freeze.write_text(json.dumps({"campaign": {"campaign_id": "synthetic-campaign", "deadline_unix": NOW + 7200}}))
        self.config = {"freeze_path": str(self.freeze), "monitor_directory": str(self.monitor),
                       "cache_directory": str(self.private / "cache"), "publish_root": str(self.checkout),
                       "state_path": str(self.private / "publisher.json"),
                       "agents_sha256": publisher.digest(self.checkout / "AGENTS.md")}
        self.snapshot = {"schema": "synthetic-progress-v1", "campaign_id": "synthetic-campaign",
                         "freeze_sha256": publisher.digest(self.freeze), "created_unix": NOW,
                         "monitor_status": "monitoring", "stage": "fit", "errors": [],
                         "runs": {f"{a}-{s}": {"status": "running"} for a in ("ppo", "replay") for s in (17,29,43)},
                         "algorithms": {}, "checkpoint": [["ppo", None], ["replay", None]]}
        self.collections = []
        # Collector correctness is tested separately; these hooks supply stable synthetic snapshots.
        for name, value in (("checkpoint_key", lambda data: data["checkpoint"]),
                            ("render", lambda data: f"Progress at {data['created_unix']}: {data['monitor_status']}\n")):
            patcher = patch.object(publisher.progress, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        fixed = self.private / "collector-source.py"
        fixed.write_text("frozen synthetic collector\n")
        patcher = patch.object(publisher.progress, "__file__", str(fixed))
        patcher.start()
        self.addCleanup(patcher.stop)

    def monitor_state(self, status="monitoring"):
        (self.monitor / "state.json").write_text(json.dumps({"status": status}))

    def collect(self, freeze, monitor, cache, volume, now=None):
        self.collections.append(now)
        self.assertEqual((freeze, monitor, cache), (str(self.freeze), str(self.monitor), self.config["cache_directory"]))
        return {**copy.deepcopy(self.snapshot), "created_unix": now}

    def tick(self, now=NOW):
        return publisher.tick(self.config, volume=object(), collector=self.collect, now=now)

    def state(self):
        return publisher.read(self.config["state_path"])

    def remote_count(self):
        return int(git(self.remote, "rev-list", "--count", "main"))

    def teammate_commit(self, name="teammate-next.txt", content="teammate incremental work\n"):
        git(self.seed, "pull", "--ff-only", "origin", "main")
        path = self.seed / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        git(self.seed, "add", "--", name)
        git(self.seed, "commit", "-m", "teammate increment")
        git(self.seed, "push", "origin", "main")
        return git(self.seed, "rev-parse", "HEAD")

    def test_initial_publish_scopes_files_and_throttles_with_fifteen_minute_refresh(self):
        state = self.tick()
        self.assertEqual(state["status"], "monitoring")
        self.assertEqual(self.remote_count(), 2)
        changed = git(self.remote, "diff", "--name-only", "main^", "main").splitlines()
        self.assertEqual(len(changed), 3)
        self.assertTrue(all(name.startswith(publisher.BASE + "/progress") for name in changed))
        self.assertEqual((self.checkout / "teammate.txt").read_text(), "preserve original teammate work\n")
        self.assertFalse(git(self.checkout, "status", "--porcelain"))
        self.tick(NOW + 300)
        self.tick(NOW + 899)
        self.assertEqual(self.remote_count(), 2)
        self.tick(NOW + 900)
        self.assertEqual(self.remote_count(), 3)
        self.assertEqual(len(list((self.checkout / publisher.BASE / "progress-snapshots").glob("*.json"))), 2)

    def test_checkpoint_and_status_changes_publish_without_waiting_then_terminal_exits(self):
        self.tick()
        self.snapshot["checkpoint"] = [["ppo", 512, ["hash17", "hash29", "hash43"]], ["replay", None]]
        self.tick(NOW + 300)
        self.assertEqual(self.remote_count(), 3)
        self.snapshot["monitor_status"] = "ready_for_final_evaluation"
        state = self.tick(NOW + 600)
        self.assertEqual((state["status"], self.remote_count()), ("complete", 4))
        self.tick(NOW + 900)
        self.assertEqual(len(self.collections), 3)

    def test_existing_initial_snapshot_is_synchronized_and_not_duplicated(self):
        self.teammate_commit(publisher.LATEST, json.dumps(self.snapshot))
        state = self.tick(NOW + 300)
        self.assertEqual(self.remote_count(), 2)
        self.assertEqual(state["last_published"]["unix"], NOW)
        self.assertFalse((self.checkout / publisher.BASE / "progress-snapshots").exists())

    def test_dirty_checkout_and_unrecorded_commits_stop_before_collection(self):
        (self.checkout / "unrelated-private.txt").write_text("do not stage\n")
        with self.assertRaisesRegex(ValueError, "dirty"):
            self.tick()
        self.assertEqual(self.state()["status"], "error")
        self.assertEqual(self.collections, [])
        self.assertEqual(self.remote_count(), 1)
        self.assertTrue((self.checkout / "unrelated-private.txt").exists())

    def test_remote_workflow_change_fails_closed_without_publishing(self):
        self.teammate_commit("AGENTS.md", "new rules requiring review\n")
        with self.assertRaisesRegex(ValueError, "workflow changed"):
            self.tick()
        self.assertEqual(self.state()["status"], "error")
        self.assertEqual(self.remote_count(), 2)
        self.assertEqual(self.collections, [])

    def test_push_race_rebases_only_own_single_commit_and_preserves_teammate(self):
        original, raced = publisher.git, []
        def racing(root, *args, **kwargs):
            if args[0] == "push" and not raced:
                raced.append(self.teammate_commit())
            return original(root, *args, **kwargs)
        with patch.object(publisher, "git", side_effect=racing):
            state = self.tick()
        self.assertEqual(state["status"], "monitoring")
        self.assertEqual(self.remote_count(), 3)
        self.assertEqual(git(self.remote, "rev-parse", "main^"), raced[0])
        self.assertEqual((self.checkout / "teammate-next.txt").read_text(), "teammate incremental work\n")
        self.assertFalse(git(self.checkout, "status", "--porcelain"))

    def test_rebase_conflict_is_preserved_and_automatic_progress_stops(self):
        original, raced = publisher.git, []
        def racing(root, *args, **kwargs):
            if args[0] == "push" and not raced:
                raced.append(self.teammate_commit(publisher.BASE + "/progress.md", "conflicting teammate progress\n"))
            return original(root, *args, **kwargs)
        with patch.object(publisher, "git", side_effect=racing), self.assertRaises(RuntimeError):
            self.tick()
        self.assertEqual(self.state()["status"], "error")
        self.assertTrue(git(self.checkout, "status", "--porcelain"))
        self.assertEqual(self.remote_count(), 2)
        self.assertEqual(self.tick(NOW + 300)["status"], "error")

    def test_crash_after_commit_recovers_only_recorded_unpublished_content(self):
        with patch.object(publisher, "push_pending", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.tick()
        self.assertIsNotNone(self.state()["pending"])
        self.assertEqual(self.remote_count(), 1)
        head = git(self.checkout, "rev-parse", "HEAD")
        state = self.tick(NOW + 300)
        self.assertEqual(self.remote_count(), 2)
        self.assertEqual(state["last_published"]["commit"], head)
        self.assertEqual(len(self.collections), 1)

    def test_crash_after_successful_push_reconciles_without_duplicate_commit(self):
        with patch.object(publisher, "finish_publication", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.tick()
        self.assertEqual(self.remote_count(), 2)
        state = self.tick(NOW + 300)
        self.assertIsNone(state["pending"])
        self.assertEqual(self.remote_count(), 2)
        self.assertEqual(len(self.collections), 1)

    def test_foreign_commit_during_crash_recovery_is_not_rebased_or_pushed(self):
        with patch.object(publisher, "push_pending", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.tick()
        (self.checkout / "unrelated.txt").write_text("foreign commit\n")
        git(self.checkout, "add", "unrelated.txt")
        git(self.checkout, "commit", "-m", "unexpected own branch edit")
        with self.assertRaisesRegex(ValueError, "unexpected unpublished"):
            self.tick(NOW + 300)
        self.assertEqual(self.state()["status"], "error")
        self.assertEqual(self.remote_count(), 1)
        self.assertTrue((self.checkout / "unrelated.txt").exists())

    def test_pause_disables_before_collection_and_remains_durable(self):
        (self.monitor / "progress-stop").touch()
        self.assertEqual(self.tick()["status"], "disabled")
        (self.monitor / "progress-stop").unlink()
        self.assertEqual(self.tick(NOW + 300)["status"], "disabled")
        self.assertEqual(self.collections, [])
        self.assertEqual(self.remote_count(), 1)

    def test_failed_push_attempts_are_bounded_and_retained(self):
        original, pushes = publisher.git, []
        def fail_push(root, *args, **kwargs):
            if args[0] == "push":
                pushes.append(args)
                return subprocess.CompletedProcess(args, 1, "", "synthetic network failure")
            return original(root, *args, **kwargs)
        with patch.object(publisher, "git", side_effect=fail_push), self.assertRaisesRegex(RuntimeError, "three normal push"):
            self.tick()
        self.assertEqual(len(pushes), 3)
        self.assertIsNotNone(self.state()["pending"])
        self.assertFalse(git(self.checkout, "status", "--porcelain"))
        self.assertEqual(self.remote_count(), 1)

    def test_git_network_options_are_local_to_fetch_and_push(self):
        options = ["-c", "http.curloptResolve=github.com:443:140.82.121.4", "-c", "http.version=HTTP/1.1"]
        self.config["git_options"] = options
        original, observed = publisher.git, []
        def capture(root, *args, **kwargs):
            if args[0] in ("fetch", "push"):
                observed.append((args[0], kwargs.get("options")))
            return original(root, *args, **kwargs)
        with patch.object(publisher, "git", side_effect=capture):
            self.tick()
        self.assertTrue(observed)
        self.assertTrue(all(value == options for _, value in observed))
        self.assertEqual(git(self.checkout, "config", "--local", "--get-regexp", "user.*"),
                         "user.name Synthetic publisher\nuser.email test@example.invalid")

    def test_unrecorded_local_commit_is_preserved_without_collection(self):
        (self.checkout / "unrelated.txt").write_text("unpublished teammate work\n")
        git(self.checkout, "add", "unrelated.txt")
        git(self.checkout, "commit", "-m", "unrecorded branch work")
        head = git(self.checkout, "rev-parse", "HEAD")
        with self.assertRaisesRegex(ValueError, "unrecorded local commits"):
            self.tick()
        self.assertEqual(git(self.checkout, "rev-parse", "HEAD"), head)
        self.assertEqual(self.remote_count(), 1)
        self.assertEqual(self.collections, [])

    def test_publisher_deadline_stops_even_if_supervisor_is_still_monitoring(self):
        self.tick()
        cutoff = NOW + 7800
        state = self.tick(cutoff)
        self.assertEqual((state["status"], state["reason"]), ("deadline", "publisher_deadline"))
        snapshot = publisher.read(self.checkout / publisher.LATEST)
        self.assertEqual(snapshot["monitor_status"], "monitoring")
        self.assertIn("does not establish training completion", snapshot["publisher_note"])
        self.assertIn(snapshot["publisher_note"], (self.checkout / publisher.BASE / "progress.md").read_text())
        count = self.remote_count()
        self.tick(cutoff + 300)
        self.assertEqual(self.remote_count(), count)
        self.assertEqual(len(self.collections), 2)

    def test_deadline_preserves_pending_commit_for_manual_review(self):
        with patch.object(publisher, "push_pending", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.tick()
        head = git(self.checkout, "rev-parse", "HEAD")
        state = self.tick(NOW + 7800)
        self.assertEqual(state["status"], "deadline")
        self.assertIsNotNone(state["pending"])
        self.assertEqual(git(self.checkout, "rev-parse", "HEAD"), head)
        self.assertEqual(self.remote_count(), 1)
        self.assertEqual(len(self.collections), 1)

    def test_follow_cadence_subtracts_time_spent_collecting_and_publishing(self):
        path = self.private / "config.json"
        path.write_text(json.dumps(self.config))
        states = [{"status": "monitoring", "last_published": None,
                   "identity": {"publisher_deadline_unix": NOW + 1000}},
                  {"status": "complete", "last_published": None}]
        with patch("sys.argv", ["publisher", "--config", str(path), "--follow"]), \
                patch.object(publisher, "tick", side_effect=states), \
                patch.object(publisher.time, "monotonic", side_effect=[0., 12., 300.]), \
                patch.object(publisher.time, "time", return_value=NOW), \
                patch.object(publisher.time, "sleep") as sleep, contextlib.redirect_stdout(io.StringIO()):
            publisher.main()
        sleep.assert_called_once_with(288.)


if __name__ == "__main__":
    unittest.main()
