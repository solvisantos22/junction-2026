"""Frozen study selection/gates and evidence, without running either full matrix."""

from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from lightlag_survey import study


def synthetic_rows(stage="development", pair=("r1", "r2")):
    config = study.configuration(stage, pair if stage == "check" else None)
    rows = []
    for spec in study.cases(config):
        score = 11 if spec["policy"] == "adaptive" else 10 if spec["policy"] == "no_probe" else 10.5
        plans = {region: {"feasible": True, "expected_value": 4 if region == "r1" else 2,
                          "targets": [region + "a", region + "b"], "sample_ticks": [8, 12],
                          "return_tick": 20, "movement_and_sample_energy": 30,
                          "home_energy_safe": 10, "idle_energy_to_horizon": 30,
                          "energy_reserve": 1, "battery": 100} for region in study.REGIONS}
        rows.append(dict(spec, status="ok", errors=[], raw_score=score, sampled_value=score,
                         normalized_score=score / 36, replay_verified=True, tool_errors=0,
                         alive=True, at_base=True, terminal_battery=10,
                         sampled_regions=list(study.REGIONS[:4]),
                         considered_regions=list(study.REGIONS), feasible_regions=list(study.REGIONS),
                         probe_set=["r2"] if spec["episode_seed"] % 2 else ["r3", "r4"],
                         initial_single_region_values={region: plan["expected_value"] for region, plan in plans.items()},
                         initial_single_region_plans=plans))
    return config, rows


def fake_episode(spec):
    config, rows = synthetic_rows("development" if spec["mission_seed"] < 4 else "check")
    row = next(row for row in rows if row["id"] == spec["id"])
    return row, {"episode": row, "replay": {"synthetic_test_only": True}, "transcript": [], "evaluation": {}, "decisions": []}


class StudyTests(unittest.TestCase):
    def test_fixed_matrix_and_pair_selection_exact_ties(self):
        config, rows = synthetic_rows()
        self.assertEqual(len(rows), 576)
        self.assertEqual(len(study.cases(study.configuration("check", ("r1", "r2")))), 128)
        self.assertEqual(study.select_fixed_pair(rows), ("r1", "r2"))
        for row in rows:
            if row["policy"] == "fixed:r5+r6":
                row["raw_score"] = 10.6
        self.assertEqual(study.select_fixed_pair(rows), ("r5", "r6"))
        with self.assertRaises(ValueError):
            study.select_fixed_pair(rows[:-1])
        with self.assertRaises(ValueError):
            study.policy_arguments("fixed:r2+r1")

    def test_missing_duplicate_errors_and_identity_changes_cannot_pass(self):
        config, rows = synthetic_rows("check")
        for changed in (rows[:-1], rows + [rows[0]], deepcopy(rows)):
            if len(changed) == 128:
                if changed[0]["status"] == "ok" and changed[0]["mission_seed"] == 4:
                    changed[0]["status"] = "error"
                    changed[0]["raw_score"] = None
            result = study.summarize(changed, config)
            self.assertFalse(result["complete"])
            self.assertFalse(result["check_gate_passed"])
        changed = deepcopy(rows)
        changed[0]["episode_seed"] += 1
        self.assertFalse(study.summarize(changed, config)["identities_match"])

    def test_structural_gate_uses_single_region_value_and_actual_probe_diversity(self):
        config, rows = synthetic_rows()
        result = study.summarize(rows, config)
        self.assertTrue(result["development_gate_passed"])
        self.assertEqual(result["structural_gate"]["sampled_regions"], ["r1", "r2", "r3", "r4"])
        # Every region remains feasible, but one is below HALF the best single-region plan.
        for row in rows:
            if row["mission_seed"] in (0, 1, 2):
                row["initial_single_region_values"]["r6"] = 1.99
                row["initial_single_region_plans"]["r6"]["expected_value"] = 1.99
        self.assertFalse(study.summarize(rows, config)["development_gate_passed"])
        _, rows = synthetic_rows()
        for row in rows:
            row["probe_set"] = ["r2"]
        self.assertFalse(study.summarize(rows, config)["development_gate_passed"])

    def test_check_thresholds_include_exact_margin_per_map_and_safety(self):
        config, rows = synthetic_rows("check")
        self.assertTrue(study.summarize(rows, config)["check_gate_passed"])
        adaptive = [row for row in rows if row["policy"] == "adaptive"]
        adaptive[0]["at_base"] = False
        self.assertTrue(study.summarize(rows, config)["check_gate_passed"])
        adaptive[1]["at_base"] = False
        self.assertFalse(study.summarize(rows, config)["check_gate_passed"])
        adaptive[0]["at_base"] = adaptive[1]["at_base"] = True
        adaptive[0]["alive"] = False
        self.assertFalse(study.summarize(rows, config)["check_gate_passed"])
        adaptive[0]["alive"] = True
        adaptive[0]["raw_score"] -= .01
        self.assertFalse(study.summarize(rows, config)["check_gate_passed"])
        for row in adaptive:
            row["raw_score"] = 10 if row["mission_seed"] in (4, 5) else 15
        result = study.summarize(rows, config)
        self.assertTrue(result["paired_comparisons"]["entropy"]["margin_pass"])
        self.assertFalse(result["paired_comparisons"]["entropy"]["maps_pass"])
        self.assertFalse(result["check_gate_passed"])

    def test_single_development_episode_reconstructs_full_public_tools_and_replay(self):
        spec = {"id": "m0-s100-no_probe", "mission_seed": 0, "episode_seed": 100, "policy": "no_probe"}
        row, full = study.run_episode(spec)
        self.assertEqual(row["status"], "ok", row["errors"])
        self.assertTrue(row["replay_verified"])
        self.assertEqual(full["evaluation"]["max_available_value"], 36)
        self.assertEqual(row["normalized_score"], row["raw_score"] / 36)
        self.assertEqual(set(row["initial_single_region_values"]), set(study.REGIONS))
        self.assertTrue(study.verify_replay(spec, full["transcript"], full["replay"]))
        damaged = deepcopy(full["transcript"])
        damaged[0]["result"]["max_ticks"] = 999
        with self.assertRaises(AssertionError):
            study.verify_replay(spec, damaged, full["replay"])
        self.assertNotIn("environment", study.PublicTools.__slots__)
        self.assertFalse(hasattr(study.PublicTools(lambda *args: None), "evaluate"))

    def test_policy_failure_is_retained_without_a_weak_score(self):
        spec = {"id": "m0-s100-adaptive", "mission_seed": 0, "episode_seed": 100, "policy": "adaptive"}

        def fail(tools, **arguments):
            tools.rules()
            tools.uplink([{"action": "inspect", "region": "r2"}])
            raise RuntimeError("synthetic policy failure")

        with patch.object(study, "run_policy", side_effect=fail):
            row, full = study.run_episode(spec)
        self.assertEqual(row["status"], "error")
        self.assertIsNone(row["raw_score"])
        self.assertTrue(row["replay_verified"])
        self.assertEqual(row["probe_set"], ["r2"])
        self.assertEqual(full["evaluation"]["tick"], 60)
        self.assertEqual(len(full["transcript"]), 2)

    def test_evidence_new_path_determinism_and_prepare_check_without_rollouts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(study, "run_episode", side_effect=fake_episode):
                for name in ("dev-a", "dev-b"):
                    result = study.run_study(root / name)
                    self.assertTrue(result["development_gate_passed"])
                self.assertEqual((root / 'dev-a/episodes.jsonl.gz').read_bytes(),
                                 (root / 'dev-b/episodes.jsonl.gz').read_bytes())
            with patch.object(study, "SurveyEnvironment", side_effect=AssertionError("no check world may be constructed")):
                protocol = study.prepare_check(root / "prepared", root / "dev-a")
            self.assertEqual(protocol["config"]["selected_pair"], ["r1", "r2"])
            self.assertEqual({p.name for p in (root / "prepared").iterdir()}, {"protocol.json", "protocol.sha256"})
            with self.assertRaises(FileExistsError):
                study.prepare_check(root / "prepared", root / "dev-a")
            with self.assertRaises(FileExistsError):
                study.run_study(root / "dev-a")
            with patch.object(study, "run_episode", side_effect=fake_episode):
                self.assertTrue(study.run_study(root / "prepared", "check")["check_gate_passed"])
            with self.assertRaises(ValueError):
                study.run_study(root / "prepared", "check")
            with gzip.open(root / "dev-a/episodes.jsonl.gz", "rt") as stream:
                self.assertEqual(len([json.loads(line) for line in stream]), 576)

    def test_source_freeze_and_incomplete_development_block_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(study, "run_episode", side_effect=fake_episode):
                study.run_study(root / "dev")
            study.prepare_check(root / "prepared", root / "dev")
            protocol = json.loads((root / "prepared/protocol.json").read_text())
            protocol["source_sha256"]["lightlag_survey/environment.py"] = "changed"
            (root / "prepared/protocol.json").write_text(json.dumps(protocol))
            with patch.object(study, "run_episode") as execute:
                with self.assertRaises(ValueError):
                    study.run_study(root / "prepared", "check")
                execute.assert_not_called()
            (root / "dev/rows.jsonl").write_text("")
            with self.assertRaises(ValueError):
                study.prepare_check(root / "bad-check", root / "dev")
            self.assertFalse((root / "bad-check").exists())
            with patch.object(study, "source_hashes", return_value={}):
                with self.assertRaises(ValueError):
                    study.run_study(root / "new")
            self.assertFalse((root / "new").exists())

    def test_final_progress_failure_cannot_be_reclassified_as_a_complete_development(self):
        def progress(item):
            if item["completed"] == 576:
                raise RuntimeError("synthetic final callback failure")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(study, "run_episode", side_effect=fake_episode):
                result = study.run_study(root / "dev", progress=progress)
            self.assertEqual(result["retained_rows"], 576)
            self.assertTrue(result["source_unchanged"])
            self.assertFalse(result["complete"])
            with self.assertRaises(ValueError):
                study.prepare_check(root / "prepared", root / "dev")
            self.assertFalse((root / "prepared").exists())

    def test_partial_worker_submission_preserves_completed_prefix_and_runner_error(self):
        for submitted in (0, 1):
            with self.subTest(submitted=submitted), tempfile.TemporaryDirectory() as temporary:
                executor = Mock()
                future = Mock()
                future.cancelled.return_value = False
                future.result.return_value = fake_episode(study.cases(study.configuration("development"))[0])
                executor.submit.side_effect = ([future] if submitted else []) + [RuntimeError("synthetic submit failure")]
                with patch.object(study, "ProcessPoolExecutor", return_value=executor):
                    result = study.run_study(Path(temporary) / "dev", workers=2)
                self.assertFalse(result["complete"])
                self.assertEqual(result["retained_rows"], submitted)
                self.assertEqual(result["runner_error"]["message"], "synthetic submit failure")
                executor.shutdown.assert_called_once_with(wait=True, cancel_futures=True)


if __name__ == "__main__":
    unittest.main()
