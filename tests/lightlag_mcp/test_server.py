"""The MCP layer: what a real MCP client sees. Needs the `mcp` package (2.x).

    uv run --with 'mcp>=2.3,<3' python -m unittest discover -s tests/lightlag_mcp -v

Skipped when `mcp` is not installed, so the standard-library suite still runs.
"""

import asyncio
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

try:
    import uvicorn
    from mcp import Client, StdioServerParameters

    from lightlag_mcp.client import RemoteToolError, connect
    from lightlag_mcp.server import build_server
    HAVE_MCP = True
except ImportError:  # pragma: no cover - exercised only without the dependency
    HAVE_MCP = False

from lightlag import Config, Environment

from lightlag_controllers import OPEN_LOOP_NOMINAL, REFERENCE, drive, make
from lightlag_mcp import EpisodeService

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DRIVE_WEST = [{"action": "drive", "heading_deg": 180, "metres": 2}]


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@unittest.skipUnless(HAVE_MCP, "the mcp package is not installed")
class InProcess(unittest.TestCase):
    def test_a_client_is_offered_exactly_the_five_tools_and_nothing_else(self):
        async def listing():
            async with Client(build_server(EpisodeService(seed=7))) as client:
                tools = (await client.list_tools()).tools
                resources = (await client.list_resources()).resources
                prompts = (await client.list_prompts()).prompts
                return tools, resources, prompts, client.instructions

        tools, resources, prompts, instructions = asyncio.run(listing())
        self.assertEqual([t.name for t in tools], ["rules", "map", "telemetry_log", "uplink", "advance"])
        self.assertEqual((list(resources), list(prompts)), ([], []))
        for tool in tools:
            self.assertGreater(len(tool.description), 60, tool.name)
        self.assertIn("delay_ticks + 1", instructions)

    def test_results_have_the_simulators_shape(self):
        env = Environment(seed=7, config=Config(delay_ticks=3))
        with connect(build_server(EpisodeService(seed=7, config=Config(delay_ticks=3)))) as tools:
            self.assertEqual(tools.rules(), env.rules())
            self.assertEqual(tools.map(), env.map())
            self.assertEqual(tools.uplink(DRIVE_WEST), env.uplink(DRIVE_WEST))
            self.assertEqual(tools.advance(5), env.advance(5))
            self.assertEqual(tools.telemetry_log(), env.telemetry_log())

    def test_a_rejected_call_tells_the_agent_why(self):
        with connect(build_server(EpisodeService(seed=7))) as tools:
            with self.assertRaises(RemoteToolError) as caught:
                tools.uplink([{"action": "drive", "heading_deg": 0, "metres": 9}])
            self.assertIn("metres must be in (0, 5.0]", str(caught.exception))
            with self.assertRaises(RemoteToolError) as caught:
                tools.advance(99)
            self.assertIn("ticks must be an integer from 1 to 5", str(caught.exception))
            self.assertEqual(tools.uplink(DRIVE_WEST)[0]["execute_tick"], 4)

    def test_scripted_controllers_score_the_same_through_mcp(self):
        for strategy in (REFERENCE, OPEN_LOOP_NOMINAL):
            direct = Environment(seed=5, config=Config(delay_ticks=3))
            drive(direct, make(strategy))
            service = EpisodeService(seed=5, config=Config(delay_ticks=3))
            with connect(build_server(service)) as tools:
                drive(tools, make(strategy))
            self.assertEqual(service.finish()["raw_score"], direct.evaluate()["raw_score"], strategy.name)


@unittest.skipUnless(HAVE_MCP, "the mcp package is not installed")
class OverHttp(unittest.TestCase):
    TOKEN = "test-only-evaluator-token"

    def setUp(self):
        self.service = EpisodeService(seed=7, config=Config(delay_ticks=0, max_ticks=20))
        self.port = free_port()
        app = build_server(self.service, evaluator_token=self.TOKEN).streamable_http_app()
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="error"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        deadline = time.time() + 10
        while not self.server.started and time.time() < deadline:
            time.sleep(0.05)
        self.assertTrue(self.server.started)

    def tearDown(self):
        self.server.should_exit = True
        self.thread.join(timeout=10)

    def request(self, path, method="GET", token=None):
        request = urllib.request.Request("http://127.0.0.1:{}{}".format(self.port, path), method=method, data=b"" if method == "POST" else None)
        if token is not None:
            request.add_header("Authorization", "Bearer {}".format(token))
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as failure:
            return failure.code, json.loads(failure.read() or b"null")

    def test_an_agent_plays_over_http_and_only_the_evaluator_can_finish(self):
        self.assertEqual(self.request("/healthz")[0], 200)
        with connect("http://127.0.0.1:{}/mcp".format(self.port)) as tools:
            self.assertEqual(tools.tool_names(), ["rules", "map", "telemetry_log", "uplink", "advance"])
            self.assertEqual(tools.uplink(DRIVE_WEST)[0]["execute_tick"], 1)
            self.assertEqual(tools.advance(2)["current_tick"], 2)

            self.assertEqual(self.request("/evaluator/finish", "POST")[0], 404)
            self.assertEqual(self.request("/evaluator/finish", "POST", token="wrong")[0], 404)
            self.assertFalse(self.service.closed)

            status, result = self.request("/evaluator/finish", "POST", token=self.TOKEN)
            self.assertEqual(status, 200)
            self.assertEqual((result["tick"], result["raw_score"]), (20, 0.0))
            self.assertNotIn("seed", json.dumps(result))
            with self.assertRaises(RemoteToolError) as caught:
                tools.advance(1)
            self.assertIn("closed", str(caught.exception))

    def test_without_a_configured_token_the_finish_route_does_not_exist(self):
        port = free_port()
        app = build_server(EpisodeService(seed=1)).streamable_http_app()
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            deadline = time.time() + 10
            while not server.started and time.time() < deadline:
                time.sleep(0.05)
            request = urllib.request.Request(
                "http://127.0.0.1:{}/evaluator/finish".format(port), method="POST", data=b"",
                headers={"Authorization": "Bearer "},
            )
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request, timeout=10)
            self.assertEqual(caught.exception.code, 404)
        finally:
            server.should_exit = True
            thread.join(timeout=10)


@unittest.skipUnless(HAVE_MCP, "the mcp package is not installed")
class HttpProcess(unittest.TestCase):
    def test_stopping_the_http_server_still_leaves_a_score(self):
        """A container stop sends SIGTERM; the episode must be graded before the process ends."""
        import subprocess

        with tempfile.TemporaryDirectory() as directory:
            port = free_port()
            process = subprocess.Popen(
                [sys.executable, "-m", "lightlag_mcp", "--transport", "http", "--port", str(port),
                 "--seed", "7", "--delay", "0", "--ticks", "20", "--artifact-dir", directory],
                cwd=REPO_ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            try:
                deadline = time.time() + 15
                while time.time() < deadline:
                    try:
                        socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                        break
                    except OSError:
                        time.sleep(0.1)
                with connect("http://127.0.0.1:{}/mcp".format(port)) as tools:
                    self.assertEqual(tools.advance(3)["current_tick"], 3)
                process.terminate()
                process.wait(timeout=15)
            finally:
                if process.poll() is None:
                    process.kill()
            with open(os.path.join(directory, "result.json"), encoding="utf-8") as stream:
                result = json.load(stream)
            self.assertEqual((result["tick"], result["raw_score"], result["tool_calls"]), (20, 0.0, 1))


@unittest.skipUnless(HAVE_MCP, "the mcp package is not installed")
class OverStdio(unittest.TestCase):
    def test_the_command_line_server_plays_and_leaves_a_score_when_it_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            parameters = StdioServerParameters(
                command=sys.executable,
                args=["-m", "lightlag_mcp", "--transport", "stdio", "--seed", "7", "--delay", "0",
                      "--ticks", "20", "--artifact-dir", directory],
                cwd=REPO_ROOT,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            )
            with connect(parameters) as tools:
                self.assertEqual(tools.rules()["max_ticks"], 20)
                tools.uplink([{"action": "drive", "heading_deg": 180, "metres": 5},
                              {"action": "drive", "heading_deg": 180, "metres": 1.1},
                              {"action": "sample"},
                              {"action": "drive", "heading_deg": 0, "metres": 5},
                              {"action": "drive", "heading_deg": 0, "metres": 1.1}])
                self.assertEqual(tools.advance(5)["current_tick"], 5)
            result_path = os.path.join(directory, "result.json")
            deadline = time.time() + 10
            while not os.path.exists(result_path) and time.time() < deadline:
                time.sleep(0.05)
            with open(result_path, encoding="utf-8") as stream:
                result = json.load(stream)
            self.assertEqual(result["tick"], 20)
            self.assertEqual(result["sampled_targets"], ["west"])
            self.assertEqual(result["raw_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
