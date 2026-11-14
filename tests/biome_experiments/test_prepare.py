"""A generated biome / navigation task, exercised as a standalone artifact without Docker.

    python3 -m unittest discover -s tests/biome_experiments -v

The dry runs play a task the way Harbor sequences it: the simulator image's own command, the
oracle solution, the collect hook and the verifier, on this machine's loopback interface and
from the task's own copies of the code. They need the mcp package (2.x); the fusing reference
also needs numpy. They do not build or start containers, so they do not replace a real
`harbor run`. About twenty seconds.
"""

import contextlib
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

REPO = Path(__file__).resolve().parents[2]
PREPARE = REPO / "tools/biome_experiments/prepare.py"
DYNAMIC = REPO / "tools/lightlag_experiments/prepare.py"
CANONICAL = REPO / "harbor/lightlag"
HAVE_MCP = importlib.util.find_spec("mcp") is not None
HAVE_NUMPY = importlib.util.find_spec("numpy") is not None
NO_NUMPY = "import sys; sys.modules['numpy'] = None; "  # the simulator image installs mcp and nothing else

sys.path.insert(0, str(REPO))
from lightlag import Config  # noqa: E402
from lightlag_dynamic.biomes.serve import BiomeEpisodeService  # noqa: E402
from lightlag_dynamic.controllers import POLICIES  # noqa: E402
from lightlag_dynamic.missions import PROFILES  # noqa: E402
from lightlag_dynamic.tools import PublicTools  # noqa: E402


def generate(destination, *args, tool=PREPARE):
    return subprocess.run([sys.executable, str(tool), str(destination), *args], cwd=REPO,
                          capture_output=True, text=True)


def settings_of(task):
    """The simulator's episode settings, as its docker-compose file sets them."""
    settings = {}
    for line in (task / "environment/docker-compose.yaml").read_text().splitlines():
        key, separator, value = line.strip().partition(": ")
        if separator and key.startswith("LIGHTLAG_") and value.startswith('"'):
            settings[key] = json.loads(value)
    return settings


def command_of(task):
    """The simulator image's own command: the CMD of its Dockerfile."""
    lines = [line for line in (task / "environment/simulator/Dockerfile").read_text().splitlines()
             if line.startswith("CMD ")]
    return json.loads(lines[-1][4:])


def files_of(task):
    return {str(path.relative_to(task)): path.read_bytes() for path in task.rglob("*") if path.is_file()}


def direct(policy, seed, delay, profile="rush_noisy", biome="main_mars", navigation="weak_gps"):
    """The same episode played in this process, straight on the environment."""
    service = BiomeEpisodeService(seed=seed, biome=biome, profile=profile,
                                  config=Config(delay_ticks=delay, max_ticks=PROFILES[profile][4]),
                                  no_gps=navigation == "no_gps", weak_gps=navigation == "weak_gps")
    env = service._env
    policy(PublicTools(env))
    while not env.advance(5)["episode_complete"]:
        pass
    return env.evaluate()


class Preparation(unittest.TestCase):
    def prepare(self, destination, *args, success=True, tool=PREPARE):
        self.assertTrue(tool.is_file(), "the task generator is missing")
        run = generate(destination, *args, tool=tool)
        if success:
            self.assertEqual(run.returncode, 0, run.stderr)
        else:
            self.assertNotEqual(run.returncode, 0, run.stdout)
        return run

    def test_simulator_runs_from_its_own_copies_and_solution_needs_no_simulator(self):
        with tempfile.TemporaryDirectory() as directory:
            task = Path(directory) / "task"
            self.prepare(task, "--navigation", "weak_gps", "--biome", "troy_crust+relay_pass",
                         "--profile", "rush_noisy", "--seed", "11", "--delay", "5")
            settings = settings_of(task)
            self.assertEqual(settings, {"LIGHTLAG_SEED": "11", "LIGHTLAG_DELAY": "5", "LIGHTLAG_PROFILE": "rush_noisy",
                                        "LIGHTLAG_TICKS": "50", "LIGHTLAG_BIOME": "troy_crust+relay_pass",
                                        "LIGHTLAG_NOISE_LEVEL": "1.0", "LIGHTLAG_WEAK_GPS": "1"})
            self.assertEqual(command_of(task)[:3], ["python", "-m", "lightlag_dynamic.biomes.serve"])
            env = {key: value for key, value in os.environ.items() if not key.startswith("LIGHTLAG_")}
            env.update(settings, PYTHONPATH="", PYTHONDONTWRITEBYTECODE="1")
            probe = subprocess.run(
                [sys.executable, "-c", NO_NUMPY + "import json, os; from lightlag import Config; "
                 "from lightlag_dynamic.biomes.serve import BiomeEpisodeService; e = os.environ; "
                 "s = BiomeEpisodeService(seed=int(e['LIGHTLAG_SEED']), biome=e['LIGHTLAG_BIOME'], "
                 "profile=e['LIGHTLAG_PROFILE'], weak_gps=e.get('LIGHTLAG_WEAK_GPS') == '1', "
                 "config=Config(delay_ticks=int(e['LIGHTLAG_DELAY']), max_ticks=int(e['LIGHTLAG_TICKS']))); "
                 "print(json.dumps(s.rules()))"],
                cwd=task / "environment/simulator", env=env, capture_output=True, text=True,
            )
            self.assertEqual(probe.returncode, 0, probe.stderr)
            rules = json.loads(probe.stdout)
            self.assertEqual((rules["mission_profile"], rules["max_ticks"], rules["delay_ticks"]), ("rush_noisy", 50, 5))
            self.assertEqual([entry["id"] for entry in rules["biome"]], ["troy_crust", "relay_pass"])
            self.assertEqual(rules["navigation"]["position_noise_m"], 2.0)
            probe = subprocess.run(
                [sys.executable, "-c", NO_NUMPY + "from lightlag_dynamic.controllers import POLICIES; "
                 "assert all(callable(POLICIES[p]) for p in ['kf_mpc', 'open_loop', 'leg_and_wait'])"],
                cwd=task / "solution", env=env, capture_output=True, text=True,
            )
            self.assertEqual(probe.returncode, 0, probe.stderr)
            # Nothing of the simulator, of the biomes or of the fusing reference is outside the simulator image.
            outside = [name for name in files_of(task) if not name.startswith("environment/simulator/")]
            self.assertFalse([name for name in outside if "biomes" in name or "manh_controllers" in name
                              or name.startswith("solution/lightlag/")
                              or name in ("solution/lightlag_dynamic/environment.py",
                                          "solution/lightlag_dynamic/missions.py")])
            for name, data in files_of(task).items():
                self.assertNotIn(b"ParticleFilter", data, name)
                self.assertFalse(name.endswith(("nogps_players.py", "estimators.py")), name)
            for name in ("environment/Dockerfile", "tests/grade.py", "tests/test.sh", "tests/Dockerfile"):
                self.assertEqual((task / name).read_bytes(), (CANONICAL / name).read_bytes(), name)
            self.assertIn('name = "neural-network-november/lightlag-biome-troy-crust-relay-pass-weak-gps-rush-noisy"',
                          (task / "task.toml").read_text())
            self.assertTrue(os.access(task / "solution/solve.sh", os.X_OK))

    def test_manifest_covers_exact_task_bytes_and_build_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = (Path(directory) / name for name in ["a", "b"])
            for task in [first, second]:
                self.prepare(task, "--policy", "leg_and_wait")
            self.assertEqual((first / "experiment.json").read_bytes(), (second / "experiment.json").read_bytes())
            manifest = json.loads((first / "experiment.json").read_text())
            self.assertEqual(manifest["settings"], {"biome": "main_mars", "profile": "rush_noisy", "seed": 2400,
                                                   "delay": 3, "horizon": 50, "navigation": "weak_gps",
                                                   "noise_level": 1.0, "policy": "leg_and_wait"})
            self.assertEqual(manifest["navigation_rules"], {"beacon_range_noise_m": 0.25, "heading_bias_deg": 15.0,
                                                           "position_noise_m": 2.0, "sun_compass_noise_deg": 12.0})
            actual = {name: hashlib.sha256(data).hexdigest() for name, data in files_of(first).items()
                      if name != "experiment.json"}
            self.assertEqual(manifest["task_sha256"], actual)
            for name, digest in manifest["source_sha256"].items():
                self.assertFalse(Path(name).is_absolute())
                self.assertEqual(hashlib.sha256((REPO / name).read_bytes()).hexdigest(), digest)
            self.assertIn("lightlag_dynamic/biomes/wording.py", manifest["source_sha256"])
            self.assertNotIn(str(REPO), (first / "experiment.json").read_text())
            self.assertFalse(any(Path(name).name.startswith(".env") for name in files_of(first)))

    def test_with_todays_fix_in_main_mars_the_agent_gets_the_dynamic_experiment(self):
        """The control arm: only the simulator's entry point, its settings and the task name differ."""
        differ = {"experiment.json", "task.toml", "environment/docker-compose.yaml",
                  "environment/simulator/Dockerfile", "environment/simulator/lightlag_dynamic/serve.py"}
        for profile in ("rush", "rush_noisy"):
            with tempfile.TemporaryDirectory() as directory:
                theirs, mine = Path(directory) / "dynamic", Path(directory) / "biome"
                self.prepare(theirs, "--profile", profile, "--seed", "11", "--delay", "5", tool=DYNAMIC)
                self.prepare(mine, "--navigation", "gps", "--profile", profile, "--seed", "11", "--delay", "5")
                expected, actual = files_of(theirs), files_of(mine)
                self.assertEqual(expected["instruction.md"], actual["instruction.md"])
                for name in sorted(set(expected) - differ):
                    self.assertEqual(expected[name], actual.get(name), name)
                added = sorted(set(actual) - set(expected))
                self.assertTrue(added and all(name.startswith(("environment/simulator/lightlag_dynamic/biomes/",
                                                              "environment/simulator/lightlag_dynamic/manh_controllers/"))
                                              for name in added), added)

    def test_a_navigation_setting_or_a_biome_adds_to_the_instruction_and_rewrites_nothing_true(self):
        with tempfile.TemporaryDirectory() as directory:
            texts = {}
            for name, args in {"gps": ("--navigation", "gps"), "weak": ("--navigation", "weak_gps"),
                               "none": ("--navigation", "no_gps", "--policy", "open_loop"),
                               "crust": ("--navigation", "gps", "--biome", "troy_crust")}.items():
                self.prepare(Path(directory) / name, "--seed", "11", *args)
                texts[name] = (Path(directory) / name / "instruction.md").read_text().splitlines()

            def changes(name):
                lines = [line for line in difflib.unified_diff(texts["gps"], texts[name], n=0, lineterm="")
                         if not line.startswith(("+++", "---", "@@"))]
                return ([line[1:] for line in lines if line.startswith("-")],
                        "\n".join(line[1:] for line in lines if line.startswith("+")))

            removed, added = changes("weak")
            self.assertEqual(removed, [])
            for fact in ("## Where the rover is", "noise of 2 m per axis", "beacon_range_m", "sun_heading_deg",
                         "navigation.position_noise_m"):
                self.assertIn(fact, added)
            removed, added = changes("none")
            self.assertEqual(removed, ["  If it is non-null, position and visual odometry are noisy, and actual drives can"])
            for fact in ("visual odometry is noisy", "position is null", "beacon_range_m", "sun_heading_deg"):
                self.assertIn(fact, added)
            self.assertNotIn("per axis", added)
            removed, added = changes("crust")
            self.assertEqual(removed, [])
            for fact in ("## Where this mission is set", "Troy Crust", "crust regions", 'rules()["biome"]'):
                self.assertIn(fact, added)
            self.assertNotIn("Where the rover is", added)

    def test_the_fixed_map_profile_is_not_described_as_a_rush(self):
        with tempfile.TemporaryDirectory() as directory:
            task = Path(directory) / "task"
            self.prepare(task, "--profile", "noisy", "--navigation", "weak_gps", "--seed", "11")
            text = (task / "instruction.md").read_text()
            self.assertEqual(settings_of(task)["LIGHTLAG_TICKS"], "80")
            for absent in ("time-pressured", "deadlines", "Additional targets"):
                self.assertNotIn(absent, text)
            self.assertIn("## Where the rover is", text)

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            task = Path(directory) / "task"
            task.mkdir()
            marker = task / "keep.txt"
            marker.write_text("keep this evidence")
            self.prepare(task, success=False)
            self.assertEqual(marker.read_text(), "keep this evidence")
            self.assertEqual(list(task.iterdir()), [marker])

    def test_invalid_parameters_do_not_create_a_task(self):
        with tempfile.TemporaryDirectory() as directory:
            task = Path(directory) / "task"
            for args in [("--profile", "dynamic"), ("--delay", "-1"), ("--seed", "-1"), ("--biome", "atlantis"),
                         ("--biome", "gale_rock_field+hidden_valley"), ("--navigation", "gps_off"),
                         ("--navigation", "no_gps"), ("--navigation", "no_gps", "--policy", "kf_mpc")]:
                self.prepare(task, *args, success=False)
                self.assertFalse(task.exists(), args)
        inside = REPO / "generated-task-that-must-not-exist"
        self.prepare(inside, success=False)
        self.assertFalse(inside.exists())


@unittest.skipUnless(HAVE_MCP, "the mcp package is not installed")
class DryRunWithoutContainers(unittest.TestCase):
    """Simulator command -> play -> collect hook -> verifier, as Harbor sequences them."""

    @contextlib.contextmanager
    def served(self, *args):
        """A freshly generated task with its simulator running; yields (task, base url, environment, folder)."""
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            task = folder / "task"
            run = generate(task, *args)
            self.assertEqual(run.returncode, 0, run.stderr)
            blocker = folder / "no-numpy"  # the simulator and agent images do not have numpy
            blocker.mkdir()
            (blocker / "numpy.py").write_text('raise ImportError("this image has no numpy")\n')
            environment = {key: value for key, value in os.environ.items() if not key.startswith("LIGHTLAG_")}
            environment.update(
                settings_of(task), PYTHONPATH=str(blocker), PYTHONDONTWRITEBYTECODE="1",
                LIGHTLAG_ARTIFACT_DIR=str(folder / "evaluator"), LIGHTLAG_TOKEN_FILE=str(folder / "run" / "token"),
                # solve.sh calls `python3`; in the container that is the interpreter with the mcp package.
                PATH=os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", ""),
            )
            port = socket.socket()
            port.bind(("127.0.0.1", 0))
            number = port.getsockname()[1]
            port.close()
            command = command_of(task)
            command[0] = sys.executable
            command[command.index("--host") + 1] = "127.0.0.1"
            command[command.index("--port") + 1] = str(number)
            log = open(folder / "simulator.log", "w")
            simulator = subprocess.Popen(command, cwd=task / "environment/simulator", env=environment,
                                         stdout=subprocess.DEVNULL, stderr=log)
            url = "http://127.0.0.1:{}".format(number)
            try:
                deadline = time.time() + 30
                while True:
                    try:
                        with urllib.request.urlopen(url + "/healthz", timeout=2) as response:
                            if response.status == 200:
                                break
                    except (urllib.error.URLError, OSError):
                        pass
                    if simulator.poll() is not None or time.time() > deadline:
                        log.flush()
                        self.fail("the simulator did not start: " + (folder / "simulator.log").read_text()[-800:])
                    time.sleep(0.1)
                yield task, url, environment, folder
            finally:
                simulator.terminate()
                try:
                    simulator.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    simulator.kill()
                log.close()

    def grade(self, task, url, environment, folder):
        """The collect hook, then the verifier; returns (reward text, the simulator's result)."""
        self.assertEqual(oct(os.stat(environment["LIGHTLAG_TOKEN_FILE"]).st_mode & 0o777), "0o600")
        collect = subprocess.run(
            [sys.executable, "-m", "lightlag_mcp.finish", "--url", url, "--token-file", environment["LIGHTLAG_TOKEN_FILE"]],
            cwd=task / "environment/simulator", env=environment, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(collect.returncode, 0, collect.stderr[-800:])
        evaluator = folder / "evaluator"
        verify = subprocess.run(
            [sys.executable, str(task / "tests/grade.py"), "--result", str(evaluator / "result.json"),
             "--reward", str(folder / "logs/reward.txt"), "--details", str(folder / "logs/details.json")],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(verify.returncode, 0, verify.stderr[-800:])
        self.assertEqual(sorted(os.listdir(evaluator)), ["replay.json", "result.json", "transcript.jsonl"])
        return (folder / "logs/reward.txt").read_text(), json.loads((evaluator / "result.json").read_text())

    def solve(self, task, url, environment):
        solve = subprocess.run(["bash", str(task / "solution/solve.sh")], cwd=task / "solution",
                               env=dict(environment, LIGHTLAG_MCP_URL=url + "/mcp"),
                               capture_output=True, text=True, timeout=300)
        self.assertEqual(solve.returncode, 0, solve.stderr[-800:])

    def look(self, url):
        """What an agent is told before it acts: the server's instructions and its tools' descriptions."""
        import asyncio

        from lightlag_mcp.client import connect
        with connect(url + "/mcp") as tools:
            listed = asyncio.run_coroutine_threadsafe(tools._client.list_tools(), tools._loop).result(timeout=30)
            return tools._client.instructions, {tool.name: tool.description for tool in listed.tools}

    def telemetry(self, url):
        """Every packet the server has delivered, read as an agent reads it (a free tool call)."""
        from lightlag_mcp.client import connect
        with connect(url + "/mcp") as tools:
            return tools.telemetry_log()

    def test_weak_gps_task_from_simulator_command_to_reward(self):
        with self.served("--navigation", "weak_gps", "--profile", "rush_noisy", "--seed", "7", "--delay", "3") as running:
            task, url, environment, folder = running
            instructions, described = self.look(url)
            self.assertEqual(sorted(described), ["advance", "map", "rules", "telemetry_log", "uplink"])
            for fact in ("noise of 2 m per axis", "beacon_range_m", "sun_heading_deg"):
                self.assertIn(fact, instructions)
            self.assertIn("position [x, y] (a noisy fix, see `rules`), beacon_range_m", described["telemetry_log"])
            self.assertIn("under `navigation`", described["rules"])
            self.solve(task, url, environment)
            packets = self.telemetry(url)
            text, result = self.grade(task, url, environment, folder)
            replay = json.loads((folder / "evaluator/replay.json").read_text())
        expected = direct(POLICIES["kf_mpc"], 7, 3)
        self.assertEqual((result["raw_score"], result["max_available_value"]),
                         (expected["raw_score"], expected["max_available_value"]))
        self.assertEqual(text, "{:.6f}\n".format(expected["raw_score"] / expected["max_available_value"]))
        self.assertEqual(result["tick"], 50)
        self.assertEqual(replay["navigation"]["position_noise_m"], 2.0, "the protected replay records the setting")
        self.assertTrue(all(len(packet["position"]) == 2 and packet["beacon_range_m"] >= 0 for packet in packets))
        self.assertTrue(any(packet["sun_heading_deg"] is not None for packet in packets))
        truth = {state["tick"]: state["position"] for state in replay["states"]}
        errors = [abs(packet["position"][0] - truth[packet["tick"]][0]) for packet in packets[1:]]
        self.assertGreater(max(errors), 1.0, "the fix on the wire is the coarse one")

    def test_no_gps_task_with_the_blind_plan(self):
        with self.served("--navigation", "no_gps", "--policy", "open_loop", "--seed", "7", "--delay", "3") as running:
            task, url, environment, folder = running
            instructions, described = self.look(url)
            self.assertIn("position is null", instructions)
            self.assertIn("position (null after the tick-0 briefing: there is no position fix)", described["telemetry_log"])
            self.solve(task, url, environment)
            packets = self.telemetry(url)
            text, result = self.grade(task, url, environment, folder)
            calls = [json.loads(line) for line in (folder / "evaluator/transcript.jsonl").read_text().splitlines()]
        self.assertTrue(calls and all(entry["ok"] for entry in calls))
        self.assertEqual(len(packets[0]["position"]), 2, "the launch briefing still says where the rover stands")
        self.assertTrue(len(packets) > 5 and all(packet["position"] is None for packet in packets[1:]))
        self.assertTrue(all("beacon_range_m" in packet and "sun_heading_deg" in packet for packet in packets))
        expected = direct(POLICIES["open_loop"], 7, 3, navigation="no_gps")
        self.assertEqual(text, "{:.6f}\n".format(expected["raw_score"] / expected["max_available_value"]))

    def test_doing_nothing_earns_zero_over_the_whole_horizon(self):
        with self.served("--navigation", "weak_gps", "--biome", "relay_pass", "--seed", "7") as running:
            task, url, environment, folder = running
            text, result = self.grade(task, url, environment, folder)
        self.assertEqual((text, result["tick"], result["tool_calls"]), ("0.000000\n", 50, 0))

    @unittest.skipUnless(HAVE_NUMPY, "the fusing reference needs numpy")
    def test_the_fusing_reference_plays_the_served_task_through_the_five_tools(self):
        from lightlag_dynamic.biomes.nogps_players import players
        from lightlag_mcp.client import connect
        with self.served("--navigation", "weak_gps", "--seed", "7", "--delay", "3") as running:
            task, url, environment, folder = running
            with connect(url + "/mcp") as tools:
                self.assertEqual(sorted(tools.tool_names()), ["advance", "map", "rules", "telemetry_log", "uplink"])
                players()["fused"](tools)
            text, result = self.grade(task, url, environment, folder)
        expected = direct(players()["fused"], 7, 3)
        self.assertEqual(text, "{:.6f}\n".format(expected["raw_score"] / expected["max_available_value"]))
        self.assertTrue(result["alive"])


if __name__ == "__main__":
    unittest.main()
