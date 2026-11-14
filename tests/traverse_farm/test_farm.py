"""The Traverse rollout farm: jobs, program isolation, the search and the local command.

    python3 -m unittest discover -s tests/traverse_farm -v

Standard library only. Modal itself is not needed; the Modal app is only imported when the
package is installed. Model-written code is never run here: the program tests use tiny stand-ins.
"""

import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent.parent
sys.path[:0] = [str(REPO / "tools"), str(REPO)]

from traverse_farm import jobs, search  # noqa: E402
from traverse_farm.common import parse_policies, parse_seeds  # noqa: E402

ALLOW = {"TRAVERSE_FARM_ALLOW_PROGRAMS": "1"}


class Parsing(unittest.TestCase):
    def test_seeds(self):
        self.assertEqual(parse_seeds("100-103,7"), [100, 101, 102, 103, 7])

    def test_policies_keep_json_options_whole(self):
        policies = parse_policies('pilot,greedy,pilot:{"floor": 6, "home_margin": 5}')
        self.assertEqual(policies['pilot:{"floor": 6, "home_margin": 5}'], {"policy": "pilot", "options": {"floor": 6, "home_margin": 5}})
        self.assertEqual(policies["greedy"], {"policy": "greedy"})

    def test_program_and_agent_specs_read_their_files(self):
        with tempfile.TemporaryDirectory() as folder:
            one = Path(folder) / "traverse-oneshot-x" / "policy.py"
            one.parent.mkdir()
            one.write_text("def play(tools):\n    pass\n")
            agent = Path(folder) / "traverse-agent-y" / "program"
            agent.mkdir(parents=True)
            (agent / "auto.py").write_text("print(1)\n")
            (agent / "helper.py").write_text("X = 1\n")
            (agent / "lightlag_client.py").write_text("raise SystemExit\n")
            policies = parse_policies("program:{},agent:{}".format(one, agent / "auto.py"))
        self.assertEqual(policies["program:traverse-oneshot-x"]["program"], "def play(tools):\n    pass\n")
        spec = policies["agent:traverse-agent-y"]
        self.assertEqual((spec["entry"], sorted(spec["files"])), ("auto.py", ["auto.py", "helper.py"]))


class Jobs(unittest.TestCase):
    def test_a_scripted_job_returns_a_graded_row_with_its_code_version(self):
        row = jobs.run_job({"policy": "nothing", "seed": 100, "candidate": "idle"})
        self.assertEqual((row["reward"], row["alive"], row["at_base"], row["candidate"]), (0.0, True, True, "idle"))
        self.assertEqual(len(row["source"]), 12)
        self.assertIn("Python", row["host"])

    def test_an_option_the_pilot_does_not_have_is_refused(self):
        with self.assertRaises(ValueError):
            jobs.policy_name({"policy": "pilot", "options": {"no_such_option": 1}})
        with self.assertRaises(ValueError):
            jobs.policy_name({"policy": "greedy", "options": {"floor": 3}})

    def test_a_mission_can_be_played_on_changed_rules(self):
        row = jobs.run_job({"policy": "nothing", "seed": 100, "mission": {"sun_margin_ticks": 0}})
        self.assertEqual((row["mission"], row["alive"], row["reward"]), ({"sun_margin_ticks": 0}, True, 0.0))
        with mock.patch.dict(os.environ, ALLOW):
            seen = jobs.run_job({"policy": "program", "seed": 100, "mission": {"sun_margin_ticks": 0},
                                 "program": "def play(tools):\n    assert tools.rules()['sun_margin_ticks'] == 0\n"})
        self.assertIsNone(seen["error"])

    def test_changed_rules_are_another_mission_and_saved_keys_stay_the_same(self):
        plain = {"policy": "pilot", "seed": 1}
        self.assertEqual(jobs.job_key(plain), '{"options": {}, "policy": "pilot", "program": null, "seed": 1}')
        self.assertNotEqual(jobs.job_key(plain), jobs.job_key(dict(plain, mission={"sun_margin_ticks": 0})))

    def test_crashes_come_back_as_rows(self):
        rows = jobs.local_map([{"policy": "pilot", "options": {"no_such_option": 1}, "seed": 100}], workers=1)
        self.assertIn("no_such_option", rows[0]["crash"])


class Programs(unittest.TestCase):
    def run_program(self, source=None, files=None, entry=None, time_limit=30):
        job = {"policy": "program", "seed": 100, "time_limit": time_limit}
        if files:
            job.update(files=files, entry=entry)
        else:
            job["program"] = source
        with mock.patch.dict(os.environ, ALLOW):
            return jobs.run_job(job)

    def test_refused_outside_the_container(self):
        with mock.patch.dict(os.environ, {"TRAVERSE_FARM_ALLOW_PROGRAMS": ""}):
            with self.assertRaises(PermissionError):
                jobs.run_job({"policy": "program", "program": "def play(tools):\n    pass\n", "seed": 100})

    def test_a_failing_program_is_still_graded(self):
        row = self.run_program("def play(tools):\n    tools.rules()\n    raise RuntimeError('boom')\n")
        self.assertEqual(row["error"], "RuntimeError: boom")
        self.assertEqual((row["reward"], row["public_calls"]), (0.0, 1))

    def test_a_program_that_never_returns_is_stopped(self):
        if not hasattr(__import__("signal"), "SIGALRM"):
            self.skipTest("needs SIGALRM")
        row = self.run_program("def play(tools):\n    while True:\n        pass\n", time_limit=1)
        self.assertIn("time limit", row["error"])

    def test_an_agent_script_gets_a_stand_in_client(self):
        script = ("from lightlag_client import connect\n"
                  "from lightlag_surface import Surface\n"
                  "with connect('http://lightlag:8000/mcp') as tools:\n"
                  "    tools.rules()\n"
                  "    tools.advance(5)\n")
        row = self.run_program(files={"auto.py": script}, entry="auto.py")
        self.assertIsNone(row["error"])
        self.assertEqual(row["public_calls"], 2)

    def test_replies_are_copies_so_a_program_cannot_edit_the_world(self):
        source = ("def play(tools):\n"
                  "    world = tools.map()\n"
                  "    world['base'][0] = -999\n"
                  "    assert tools.map()['base'][0] != -999, 'the world changed'\n")
        self.assertIsNone(self.run_program(source)["error"])

    def test_a_failed_program_says_where_it_stopped_and_what_it_printed(self):
        row = self.run_program("import sys\n"
                               "def play(tools):\n"
                               "    tools.advance(5)\n"
                               "    tools.advance(2)\n"
                               "    print('plan A')\n"
                               "    print('low battery', file=sys.stderr)\n"
                               "    raise RuntimeError('boom')\n")
        self.assertEqual((row["error"], row["program_tick"], row["died_tick"]), ("RuntimeError: boom", 7, None))
        self.assertTrue(row["alive"])
        self.assertIn("plan A", row["printed"])
        self.assertIn("low battery", row["printed"])

    def test_a_program_that_ends_normally_keeps_its_output_out_of_the_row(self):
        row = self.run_program("def play(tools):\n    print('fine')\n")
        self.assertIsNone(row["error"])
        self.assertNotIn("printed", row)

    def test_a_chatty_program_keeps_only_the_end_of_its_output(self):
        tail = jobs._Tail(size=10)
        for number in range(1000):
            tail.write("line {}\n".format(number))
        self.assertEqual(tail.tail(), "\nline 999\n")
        self.assertLess(len(tail.getvalue()), 200)

    def test_replays_are_saved_as_the_demo_builder_reads_them(self):
        import importlib.util
        from traverse_farm import replays
        row = jobs.run_job({"policy": "nothing", "seed": 100, "candidate": "nothing", "keep_replay": True})
        reference = dict(row, candidate="pilot")   # the writer only needs a reference-kind run; nothing drives here
        policies = {"pilot": {"policy": "pilot"}, "nothing": {"policy": "nothing"}}
        spec = importlib.util.spec_from_file_location("build_traverse", REPO / "viewer" / "build_traverse.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as folder:
            written = replays.write([reference, row], policies, Path(folder))
            world = Path(folder) / "world-100"
            meta = json.loads((world / "traverse-pilot" / "run.json").read_text())
            data = builder.gather(builder.run_folders(world))   # the demo's own checks: kinds, one world, every tick
        self.assertEqual(sorted(path.name for path in written), ["traverse-nothing", "traverse-pilot"])
        self.assertEqual((meta["kind"], meta["seed"]), ("reference", 100))
        self.assertEqual(len(data["runs"]), 2)

    def test_a_replayed_program_keeps_the_label_of_the_run_it_came_from(self):
        from traverse_farm import replays
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder) / "traverse-agent-opus-9"
            (run / "program").mkdir(parents=True)
            (run / "run.json").write_text(json.dumps({"label": "Opus 5.5 · agent 9", "model": "Claude Opus 5.5"}))
            spec = {"policy": "program", "label": str(run / "program" / "auto.py")}
            meta = replays.run_meta("agent:traverse-agent-opus-9", spec, {"seed": 7, "died_tick": 120})
        self.assertEqual((meta["kind"], meta["label"], meta["died_tick"]), ("claude", "Opus 5.5 · agent 9", 120))
        self.assertIn("without the agent", meta["how"])
        self.assertEqual(replays.folder_name("agent:traverse-agent-opus-9"), "traverse-agent-opus-9")

    def test_nothing_a_program_imports_leaks_into_the_next_job(self):
        self.run_program("import lightlag_surface\ndef play(tools):\n    pass\n")
        for name in ("policy", "lightlag_surface", "lightlag_client"):
            self.assertNotIn(name, sys.modules)


def synthetic_defaults():
    defaults = {"route": "optimise", "terrain": True, "stop_ticks": 1}
    for name, (scale, low, high) in search.SPACE.items():
        defaults[name] = int(round((low + high) / 2)) if scale.endswith("int") else round((low + high) / 2, 4)
    return defaults


class Search(unittest.TestCase):
    def fake_run_many(self, target, calls=None):
        """Reward rises towards `target` in the unit cube; seconds grow with plan_steps."""
        def run_many(batch):
            if calls is not None:
                calls.append(len(batch))
            rows = []
            for job in batch:
                point = search.encode(job["options"])
                distance = sum((point[i] - t) ** 2 for i, t in target.items())
                noise = ((job["seed"] * 7919) % 101) / 101 * 0.02
                rows.append(dict({k: job[k] for k in ("candidate", "generation", "block") if k in job},
                                 seed=job["seed"], policy="pilot", options=job["options"], reward=0.6 - 0.3 * distance + noise,
                                 alive=True, at_base=True, seconds=job["options"]["plan_steps"] / 30000))
            return rows
        return run_many

    def test_it_finds_and_confirms_a_better_setting(self):
        names = list(search.SPACE)
        target = {names.index("floor"): 0.9, names.index("energy_weight"): 0.1}
        with tempfile.TemporaryDirectory() as folder:
            result = search.search(self.fake_run_many(target), synthetic_defaults(), search_seeds=range(100, 130),
                                   select_seeds=range(400, 410), confirm_seeds=range(600, 640), generations=3,
                                   population=10, block=10, elites=3, finalists=2, out=Path(folder), log=lambda _: None)
            saved = json.loads((Path(folder) / "confirmation.json").read_text())
        self.assertTrue(result["confirmation"]["confirmed"])
        self.assertGreater(result["confirmation"]["gain"], 0)
        self.assertEqual(saved["confirmed"], True)

    def test_a_search_on_changed_rules_plays_every_mission_on_them(self):
        seen = []
        inner = self.fake_run_many({0: 0.5})

        def run_many(batch):
            seen.extend(job.get("mission") for job in batch)
            rows = inner(batch)
            for job, row in zip(batch, rows):   # as run_job does: a row says which rules it was played on
                row["mission"] = job["mission"]
            return rows

        with tempfile.TemporaryDirectory() as folder:
            search.search(run_many, synthetic_defaults(), search_seeds=range(100, 120), select_seeds=range(400, 405),
                          confirm_seeds=range(600, 610), generations=2, population=4, block=10, elites=2, finalists=1,
                          out=Path(folder), mission={"sun_margin_ticks": 0}, log=lambda _: None)
            plan = json.loads((Path(folder) / "plan.json").read_text())
        self.assertTrue(seen)
        self.assertEqual(set(json.dumps(m) for m in seen), {'{"sun_margin_ticks": 0}'})
        self.assertEqual(plan["mission"], {"sun_margin_ticks": 0})

    def test_a_slower_setting_is_disqualified(self):
        names = list(search.SPACE)
        target = {names.index("plan_steps"): 1.0}            # the best reward needs the largest search budget
        defaults = synthetic_defaults()
        result = search.search(self.fake_run_many(target), defaults, search_seeds=range(100, 130), select_seeds=range(400, 410),
                               confirm_seeds=range(600, 620), generations=3, population=10, block=10, elites=3,
                               finalists=2, max_slowdown=1.2, log=lambda _: None)
        chosen = result["confirmation"].get("options")
        if chosen:
            self.assertLessEqual(chosen["plan_steps"], 1.2 * defaults["plan_steps"] + 1)

    def test_a_stopped_search_resumes_without_replaying_worlds(self):
        calls = []
        run_many = self.fake_run_many({0: 0.5}, calls)
        with tempfile.TemporaryDirectory() as folder:
            policies = {"a": {"policy": "pilot", "options": synthetic_defaults()}}
            policies["a"]["options"] = {k: v for k, v in policies["a"]["options"].items() if k in search.SPACE}
            search.evaluate(run_many, policies, list(range(10)), out=Path(folder))
            search.evaluate(run_many, policies, list(range(10)), out=Path(folder))
        self.assertEqual(calls, [10])

    def test_a_long_run_is_saved_part_by_part(self):
        saved_before_each_part = []

        with tempfile.TemporaryDirectory() as folder:
            rows_file = Path(folder) / "rows.jsonl"

            def run_many(batch):
                saved_before_each_part.append(len(rows_file.read_text().splitlines()) if rows_file.exists() else 0)
                return [dict(candidate=job["candidate"], seed=job["seed"], policy="greedy", options={},
                             reward=0.1, alive=True, at_base=True, seconds=1.0) for job in batch]

            ledger = search.Ledger(Path(folder), part=2)
            jobs_ = [{"policy": "greedy", "candidate": "greedy", "seed": seed} for seed in range(5)]
            played = ledger.play(run_many, jobs_)
            self.assertEqual(len(rows_file.read_text().splitlines()), 5)
        self.assertEqual(saved_before_each_part, [0, 2, 4])
        self.assertEqual([row["seed"] for row in played], [0, 1, 2, 3, 4])

    def test_different_players_on_the_same_world_are_different_missions(self):
        calls = []

        def run_many(batch):
            calls.append([job["policy"] for job in batch])
            return [dict(candidate=job["candidate"], seed=job["seed"], policy=job["policy"], options={},
                         reward=0.1 if job["policy"] == "greedy" else 0.2, alive=True, at_base=True, seconds=1.0)
                    for job in batch]

        with tempfile.TemporaryDirectory() as folder:
            result = search.evaluate(run_many, {"greedy": {"policy": "greedy"}, "straight": {"policy": "straight"}},
                                     [5], out=Path(folder))
        self.assertEqual(sorted(calls[0]), ["greedy", "straight"])
        self.assertEqual((result["table"]["greedy"]["mean"], result["table"]["straight"]["mean"]), (0.1, 0.2))

    def test_saved_program_rows_find_their_programs_again(self):
        """A row holds a program's id, not its code; two programs on one world must stay apart on disk."""
        calls = []

        def run_many(batch):
            calls.append(len(batch))
            return [dict({k: job[k] for k in jobs.PASSTHROUGH if k in job}, seed=job["seed"], policy="program",
                         options={}, program_id=jobs.program_id(job), reward=0.1 if "files" in job else 0.3,
                         alive=True, at_base=True, seconds=1.0, error=None) for job in batch]

        policies = {"script": {"policy": "program", "files": {"auto.py": "print(1)\n"}, "entry": "auto.py"},
                    "play": {"policy": "program", "program": "def play(t):\n    pass\n"}}
        with tempfile.TemporaryDirectory() as folder:
            first = search.evaluate(run_many, policies, [5, 6], out=Path(folder))
            again = search.evaluate(run_many, policies, [5, 6], out=Path(folder))
        for result in (first, again):
            self.assertEqual((result["table"]["script"]["worlds"], result["table"]["script"]["mean"]), (2, 0.1))
            self.assertEqual((result["table"]["play"]["worlds"], result["table"]["play"]["mean"]), (2, 0.3))
        self.assertEqual(calls, [4])

    def test_each_policy_is_compared_with_the_baseline_world_by_world(self):
        rewards = {"pilot": [0.5, 0.5, 0.5, 0.5], "claude": [0.6, 0.5, 0.2, 0.1]}

        def run_many(batch):
            return [dict(candidate=job["candidate"], seed=job["seed"], policy=job["policy"], options={},
                         reward=rewards[job["candidate"]][job["seed"]], alive=True, at_base=True, seconds=1.0)
                    for job in batch]

        result = search.evaluate(run_many, {"pilot": {"policy": "pilot"}, "claude": {"policy": "greedy"}}, [0, 1, 2, 3])
        row = result["versus"]["claude"]
        self.assertEqual((row["worlds"], row["higher"], row["equal"], row["lower"]), (4, 1, 1, 2))
        self.assertAlmostEqual(row["difference"], -0.15)
        self.assertNotIn("pilot", result["versus"])

    def test_programs_are_told_apart_by_their_code(self):
        a = {"policy": "program", "program": "def play(t):\n    pass\n", "seed": 1}
        b = {"policy": "program", "program": "def play(t):\n    t.rules()\n", "seed": 1}
        self.assertNotEqual(jobs.job_key(a), jobs.job_key(b))
        self.assertEqual(jobs.job_key(a), jobs.job_key(dict(a, candidate="x")))

    def test_a_missing_option_is_named(self):
        defaults = synthetic_defaults()
        del defaults["beam"]
        with self.assertRaisesRegex(ValueError, "beam"):
            search.check_space(defaults)

    def test_paired_bootstrap_brackets_a_clear_gain(self):
        low, high = search.bootstrap([0.05 + 0.01 * ((i * 37) % 5 - 2) for i in range(100)])
        self.assertTrue(0 < low < 0.05 < high)

    def test_the_unit_cube_round_trips_inside_the_bounds(self):
        options = synthetic_defaults()
        again = search.decode(search.encode(options))
        for name, (scale, low, high) in search.SPACE.items():
            self.assertTrue(low <= again[name] <= high)
            self.assertTrue(math.isclose(again[name], options[name], rel_tol=0.01, abs_tol=1))


class LocalCommand(unittest.TestCase):
    def test_evaluate_plays_and_prints_a_table(self):
        out = subprocess.run([sys.executable, str(REPO / "tools/traverse_farm/local.py"), "evaluate",
                              "--policies", "nothing,straight", "--seeds", "100-101", "--workers", "2"],
                             capture_output=True, text=True, timeout=300)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("straight", out.stdout)

    def test_it_refuses_to_run_model_written_code(self):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as handle:
            handle.write("def play(tools):\n    pass\n")
        out = subprocess.run([sys.executable, str(REPO / "tools/traverse_farm/local.py"), "evaluate",
                              "--policies", "program:" + handle.name, "--seeds", "100"],
                             capture_output=True, text=True, timeout=120)
        os.unlink(handle.name)
        self.assertEqual(out.returncode, 2)
        self.assertIn("only on Modal", out.stderr)


@unittest.skipUnless(__import__("importlib").util.find_spec("modal"), "the modal package is not installed")
class ModalApp(unittest.TestCase):
    def test_the_app_defines_its_function_and_commands(self):
        sys.path.insert(0, str(REPO / "tools" / "traverse_farm"))
        import modal_app
        self.assertEqual(modal_app.app.name, "lightlag-traverse-farm")
        for name in ("mission", "smoke", "evaluate", "search", "replays"):
            self.assertTrue(hasattr(modal_app, name), name)


if __name__ == "__main__":
    unittest.main()
