"""Evaluation logic uses fixtures/historical canaries only; never builds fresh maps."""

import copy
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from tools.lightlag_experiments import overnight_synthesis as base

SPEC = importlib.util.find_spec("tools.lightlag_experiments.overnight_synthesis_evaluate")
if SPEC:
    from tools.lightlag_experiments import overnight_synthesis_evaluate as study
else:
    study = None


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(study, "evaluation phase is not implemented")

    def test_plan_has_every_cell_twice_and_exactly_four_verification_runs(self):
        rows = study.planned_rows()
        self.assertEqual(len(rows), 80)
        self.assertEqual(len({(r["profile"], r["seed"]) for r in rows}), 40)
        self.assertEqual({r["policy"] for r in rows}, {"generated", "kf_mpc"})
        self.assertTrue(all(r["reward"] is None for r in rows))
        repeats = study.verification_plan()
        self.assertEqual([(r["profile"], r["seed"]) for r in repeats],
                         [("rush", 60000), ("rush", 60019), ("rush_noisy", 60000), ("rush_noisy", 60019)])

    def test_real_terminal_grade_survives_policy_error_but_infrastructure_is_null(self):
        episode = base.read_json(REPO / "docs/lightlag-runs/overnight-synthesis/preparation-v1/historical/historical-rush-501.json")
        episode["execution"]["status"] = "policy_error"
        row = study.episode_row({"profile": "rush", "seed": 501, "policy": "generated"}, episode, "fixture.json")
        self.assertAlmostEqual(row["reward"], 10 / 12)
        self.assertEqual(row["policy_status"], "policy_error")
        self.assertEqual(row["policy_calls"], episode["policy_calls"])
        self.assertEqual(row["graded_service_call_count"], episode["result"]["tool_calls"])
        episode["grading_status"] = "infrastructure_null"
        episode["execution"]["status"] = "infrastructure_error"
        row = study.episode_row({"profile": "rush", "seed": 501, "policy": "generated"}, episode, "fixture.json")
        self.assertIsNone(row["reward"])
        self.assertIsNone(row["alive"])
        self.assertTrue(row["protected_diagnostic_grade_retained"])

    def test_incomplete_statistics_keep_twenty_cell_denominator_and_bounds(self):
        rows = study.planned_rows()
        for row in rows:
            if row["profile"] == "rush" and row["seed"] == 60000:
                row.update(reward=0.75 if row["policy"] == "generated" else 0.5,
                           alive=True, at_base=True, policy_status="returned")
        groups = study.paired_statistics(rows)
        rush = next(group for group in groups if group["profile"] == "rush")
        generated = rush["policies"]["generated"]
        self.assertIsNone(generated["mean_reward"])
        self.assertEqual(generated["mean_reward_bounds"], [0.75 / 20, 19.75 / 20])
        self.assertEqual(rush["complete_pairs"], 1)
        self.assertEqual(rush["generated_wins"], 1)
        self.assertEqual(rush["incomplete_pairs"], 19)
        self.assertEqual(rush["paired_mean_bounds"], [(-19 + 0.25) / 20, (19 + 0.25) / 20])

    def test_differing_verification_is_retained_as_nonexact_without_replacement(self):
        primary = base.read_json(REPO / "docs/lightlag-runs/overnight-synthesis/preparation-v1/historical/historical-rush-501.json")
        primary["replay_verification"] = {"exact": True}
        repeat = copy.deepcopy(primary)
        repeat["execution"]["elapsed_seconds"] += 1
        self.assertTrue(study.compare_verification(base, primary, repeat)["exact"])
        repeat["replay"]["states"][1]["battery"] -= 1
        report = study.compare_verification(base, primary, repeat)
        self.assertFalse(report["exact"])
        self.assertIn("replay", report["different_fields"])

    def test_infrastructure_only_comparisons_cannot_establish_reproducibility(self):
        primary = base.read_json(REPO / "docs/lightlag-runs/overnight-synthesis/preparation-v1/historical/historical-rush-501.json")
        primary["grading_status"] = "infrastructure_null"
        primary["replay_verification"] = {"exact": True}
        comparison = study.compare_verification(base, primary, copy.deepcopy(primary))
        self.assertIsNone(comparison["exact"])
        repeats = study.verification_plan()
        for row in repeats:
            row.update(policy_status="infrastructure_error", comparison=comparison)
        self.assertIsNone(study.summary(study.planned_rows(), repeats, "complete")["policy_exactly_reproducible_in_four_checks"])
        repeats[0]["comparison"] = {"exact": False, "available": True}
        self.assertFalse(study.summary(study.planned_rows(), repeats, "complete")["policy_exactly_reproducible_in_four_checks"])

    def test_finish_interrupt_and_prior_cleanup_failure_remain_stop_conditions(self):
        for failure, execution in [
            (KeyboardInterrupt(), {"status": "returned", "error": None}),
            (OSError("fixture finish"), {"status": "infrastructure_error", "error": None,
                                         "cleanup": {"confirmed_absent": False}}),
        ]:
            class BrokenFinish:
                def __init__(self, *args):
                    self.policy_calls, self.transcript = 0, []
                def finish(self, execution):
                    raise failure
            fake = SimpleNamespace(Broker=BrokenFinish, run_container=lambda *args: execution, error_record=base.error_record)
            episode = study.run_candidate(fake, None, 501, "rush", None, None, None, None)
            self.assertTrue(study.must_stop(episode), episode)

    def test_synthesis_failure_reports_all_rows_without_loading_a_simulator(self):
        report = study.summary(study.planned_rows(), [], "unrun_synthesis_failed")
        self.assertEqual(report["n_cells"], 40)
        self.assertEqual(report["n_primary_planned"], 80)
        self.assertEqual(report["n_primary_scored"], 0)
        self.assertEqual(report["n_primary_unrun"], 80)
        self.assertEqual(len(report["rows"]), 80)

    def test_attempt_error_has_no_stale_episode_and_verification_failure_keeps_grade(self):
        self.assertTrue(hasattr(study, "verified_attempt"), "per-attempt preservation is not implemented")
        prior = base.read_json(REPO / "docs/lightlag-runs/overnight-synthesis/preparation-v1/historical/historical-rush-501.json")
        case = {"profile": "rush", "seed": 501, "policy": "generated"}
        fake = SimpleNamespace(replay_episode=lambda runtime, episode: {"exact": True},
                               verify_source=lambda *args: None, error_record=base.error_record)
        good = study.verified_attempt(fake, None, case, lambda: copy.deepcopy(prior), Path("unused"), {})
        self.assertIsNotNone(good["result"])
        def fail():
            raise RuntimeError("fixture construction failure")
        broken = study.verified_attempt(fake, None, case, fail, Path("unused"), {})
        self.assertIsNone(broken["result"])
        self.assertEqual(broken["grading_status"], "infrastructure_null")
        fake.verify_source = lambda *args: fail()
        after = study.verified_attempt(fake, None, case, lambda: copy.deepcopy(prior), Path("unused"), {})
        self.assertEqual(after["result"], prior["result"])
        self.assertEqual(after["grading_status"], "infrastructure_null")

    def test_evaluation_cli_without_root_flag_never_reads_inputs(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            study.main(["--preparation", "/absent", "--generation", "/absent", "--source-root", "/absent",
                        "--repo", "/absent", "--output", "/absent"])
        self.assertEqual(caught.exception.code, 2)

    def test_reference_distinguishes_service_failure_from_public_call_error(self):
        self.assertTrue(hasattr(study, "run_trusted_reference"), "reference error classification is not implemented")
        for failure, status, grade in [(OSError("fixture service failure"), "infrastructure_error", "infrastructure_null"),
                                       (base.PublicCallError("fixture bad argument"), "policy_error", "scored")]:
            class Broker:
                def __init__(self, *args):
                    pass
                def call(self, *args):
                    raise failure
                def tools(self):
                    return SimpleNamespace(rules=lambda: self.call("rules", {}))
                def finish(self, execution):
                    return {"execution": execution, "grading_status": "scored", "result": {"tick": 50}}
            fake = SimpleNamespace(Broker=Broker, PublicCallError=base.PublicCallError, error_record=base.error_record)
            runtime = SimpleNamespace(reference=lambda tools: tools.rules())
            episode = study.run_trusted_reference(fake, runtime, 501, "rush")
            self.assertEqual(episode["execution"]["status"], status)
            self.assertEqual(episode["grading_status"], grade)

    def run_whole_loop_fixture(self, interrupt_at=None):
        # No environment is constructed: both policy runners and replay are
        # fixture callbacks. This checks scheduling/accounting, not performance.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            preparation = root / "preparation-v1"
            shutil.copytree(REPO / "docs/lightlag-runs/overnight-synthesis/preparation-v1", preparation)
            source = root / "source"
            base.freeze_source(REPO, source)
            generation = root / "generation"
            generation.mkdir()
            policy = preparation / "error-probes/accepted-then-error.py"
            shutil.copyfile(policy, generation / "policy.py")
            manifest = base.read_json(preparation / "preparation.json")
            base.write_json(generation / "preparation-link.json", {
                "preparation_sha256": base.sha256((preparation / "preparation.json").read_bytes()),
                "request_sha256": manifest["request_sha256"]})
            base.write_json(generation / "synthesis.json", {
                "status": "response_frozen", "evaluation_eligible": True,
                "policy_sha256": base.sha256(policy.read_bytes()),
                "artifact_sha256": {"policy.py": base.sha256(policy.read_bytes())}})
            fixture = base.read_json(preparation / "historical/historical-rush-501.json")
            counts = {"generated": {}, "reference": 0, "replay": 0}
            def generated(_base, _runtime, seed, profile, *unused):
                key = (profile, seed)
                counts["generated"][key] = counts["generated"].get(key, 0) + 1
                episode = copy.deepcopy(fixture)
                episode.update(seed=seed, profile=profile, test_fixture=True)
                if (profile, seed) == ("rush", 60005):
                    episode["grading_status"] = "infrastructure_null"
                    episode["execution"]["status"] = "infrastructure_error"
                if key == ("rush", 60019) and counts["generated"][key] == 2:
                    episode["replay"]["states"][1]["battery"] -= 1
                return episode
            def reference(_base, _runtime, seed, profile):
                counts["reference"] += 1
                episode = copy.deepcopy(fixture)
                episode.update(seed=seed, profile=profile, test_fixture=True)
                return episode
            def replay(*unused):
                counts["replay"] += 1
                return {"exact": True, "fixture_callback": True}
            original_write = base.write_json
            def write(path, value):
                if Path(path).parent.name == interrupt_at and not counts.get("interrupted"):
                    counts["interrupted"] = True
                    raise KeyboardInterrupt("fixture artifact-write interruption")
                return original_write(path, value)
            with patch.object(base, "load_runtime", return_value=SimpleNamespace()), patch.object(base, "replay_episode", side_effect=replay), \
                 patch.object(study, "run_candidate", side_effect=generated), patch.object(study, "run_trusted_reference", side_effect=reference), \
                 patch.object(base, "write_json", side_effect=write), redirect_stdout(io.StringIO()):
                report = study.evaluate(base, preparation, generation, source, REPO, root / "evaluation", "/unused")
            counts["episode_files"] = len(list((root / "evaluation/episodes").glob("*.json")))
            counts["verification_files"] = len(list((root / "evaluation/verification").glob("*.json")))
            counts["starts"] = len((root / "evaluation/attempt-starts.jsonl").read_text().splitlines())
            counts["rows"] = len((root / "evaluation/completed-rows.jsonl").read_text().splitlines())
            return report, counts

    def test_whole_loop_fixture_retains_infrastructure_null_and_differing_repeat(self):
        report, counts = self.run_whole_loop_fixture()
        self.assertEqual(report["status"], "complete", report.get("error"))
        self.assertEqual(report["n_primary_attempted"], 80)
        self.assertEqual(report["n_primary_scored"], 79)
        self.assertEqual(report["n_primary_infrastructure_null"], 1)
        self.assertEqual(sum(counts["generated"].values()), 44)
        self.assertEqual(counts["reference"], 40)
        self.assertEqual(counts["replay"], 92)
        self.assertFalse(report["policy_exactly_reproducible_in_four_checks"])
        self.assertEqual(counts["episode_files"], 80)
        self.assertEqual(counts["verification_files"], 4)
        self.assertIsNone(report["groups"][0]["policies"]["generated"]["mean_reward"])

    def test_interruption_before_primary_artifact_retains_started_unknown_row(self):
        report, counts = self.run_whole_loop_fixture("episodes")
        self.assertEqual(sum(counts["generated"].values()), 1)
        self.assertEqual(report["n_primary_attempted"], 1)
        self.assertEqual(report["n_primary_unrun"], 79)
        self.assertEqual(report["n_primary_scored"], 0)
        self.assertEqual(report["rows"][0]["grading_status"], "infrastructure_null")
        self.assertEqual(counts["starts"], 1)
        self.assertEqual(counts["rows"], 1)

    def test_interruption_before_verification_artifact_is_attempted_not_completed(self):
        report, counts = self.run_whole_loop_fixture("verification")
        self.assertEqual(report["n_primary_attempted"], 80)
        self.assertEqual(report["n_verification_attempted"], 1)
        self.assertEqual(report["n_verification_completed"], 0)
        self.assertEqual(report["verification_status"], "incomplete")
        self.assertIsNone(report["policy_exactly_reproducible_in_four_checks"])
        self.assertEqual(counts["starts"], 81)
        self.assertEqual(counts["rows"], 81)

    @unittest.skipUnless(os.environ.get("SYNTHESIS_TEST_IMAGE"), "set pinned image for historical Docker canary")
    def test_historical_execution_path_distinguishes_policy_and_container_errors(self):
        # A child interpreter avoids cross-test imports from different frozen trees.
        script = '''from pathlib import Path
import json, tempfile
from tools.lightlag_experiments import overnight_synthesis as b
from tools.lightlag_experiments import overnight_synthesis_evaluate as e
p=Path("docs/lightlag-runs/overnight-synthesis/preparation-v1")
m=b.read_json(p/"preparation.json")
temporary=tempfile.TemporaryDirectory()
source=Path(temporary.name)/"source"
b.freeze_source(Path.cwd(),source)
r=b.load_runtime(source,m["source_sha256"])
results=[]
for docker in ("/usr/local/bin/docker", "/nonexistent-synthesis-docker"):
 ep=e.run_candidate(b,r,501,"rush",p/"error-probes/accepted-then-error.py",p/"worker.py",m["worker_image"]["reference"],docker)
 results.append(e.episode_row({"seed":501,"profile":"rush","policy":"generated"},ep,"canary"))
print(json.dumps(results))
'''
        process = subprocess.run([sys.executable, "-B", "-c", script], cwd=REPO, capture_output=True, text=True, timeout=20)
        self.assertEqual(process.returncode, 0, process.stderr)
        policy, infra = json.loads(process.stdout)
        self.assertEqual(policy["policy_status"], "policy_error")
        self.assertIsNotNone(policy["reward"])
        self.assertEqual(infra["policy_status"], "infrastructure_error")
        self.assertIsNone(infra["reward"])


if __name__ == "__main__":
    unittest.main()
