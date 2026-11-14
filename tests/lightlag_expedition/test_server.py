"""Actual MCP clients, evaluator HTTP isolation and private-token CLI lifecycle."""

import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

from lightlag_expedition.environment import ExpeditionEnvironment
from lightlag_expedition.service import ExpeditionService

try:
    import uvicorn
    from mcp import Client
    from lightlag_mcp.client import connect, RemoteToolError
    from lightlag_expedition.server import build_server
    HAVE_MCP = True
except ImportError:
    HAVE_MCP = False


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(port, path, token=None):
    finish = path.endswith("finish")
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method="POST" if finish else "GET", data=b"" if finish else None)
    if token is not None:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


@unittest.skipUnless(HAVE_MCP, "mcp 2.3 dependency unavailable")
class McpTests(unittest.TestCase):
    def test_exactly_five_tools_and_no_private_resources_or_prompts(self):
        async def inspect():
            async with Client(build_server(ExpeditionService(100))) as client:
                return ((await client.list_tools()).tools,
                        (await client.list_resources()).resources,
                        (await client.list_prompts()).prompts, client.instructions)
        tools, resources, prompts, instructions = asyncio.run(inspect())
        self.assertEqual([tool.name for tool in tools], ["rules", "map", "telemetry_log", "uplink", "advance"])
        self.assertEqual((resources, prompts), ([], []))
        self.assertIn("two inspections total", instructions)
        self.assertIn("Wheel slip", instructions)
        self.assertIn("several route decisions", instructions)

    def test_packets_rejections_and_inspection_timing_through_real_client(self):
        service = ExpeditionService(100, mission_seed=2)
        direct = ExpeditionEnvironment(100, mission_seed=2)
        with connect(build_server(service)) as tools:
            for invalid in (99, True, "1", 1.5):
                with self.assertRaises(RemoteToolError):
                    tools.advance(invalid)
            self.assertEqual(tools.rules(), direct.rules())
            self.assertEqual(tools.map(), direct.map())
            self.assertEqual(tools.telemetry_log(), direct.telemetry_log())
            for commands in ([{"action": "inspect", "region": "r2"}],
                             [{"action": "drive", "heading_deg": 0, "metres": 1}, {"action": "sample"}]):
                self.assertEqual(tools.uplink(commands), direct.uplink(commands))
            with self.assertRaises(RemoteToolError):
                tools.uplink([{"action": "inspect", "region": "r2"}])
            self.assertEqual(tools.advance(5), direct.advance(5))
            self.assertEqual(tools.advance(2), direct.advance(2))
            packets = tools.telemetry_log()
            self.assertEqual(packets, direct.telemetry_log())
            events = [event for packet in packets for event in packet["events"] if event["type"] == "inspection_result"]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["region"], "r2")
        while direct.advance(5)["current_tick"] < 60:
            pass
        result = service.finish()
        self.assertEqual(result["raw_score"], direct.evaluate()["raw_score"])

    def test_http_evaluator_requires_token_and_closes_idempotently(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ExpeditionService(100, artifact_dir=directory)
            token = "test-only-evaluator-secret"
            port = free_port()
            server = uvicorn.Server(uvicorn.Config(build_server(service, token).streamable_http_app(), host="127.0.0.1", port=port, log_level="error"))
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            try:
                deadline = time.monotonic() + 10
                while not server.started and time.monotonic() < deadline:
                    time.sleep(.03)
                self.assertTrue(server.started)
                self.assertEqual(request(port, "/healthz"), (200, {"status": "ok"}))
                self.assertEqual(request(port, "/evaluator/finish")[0], 404)
                self.assertEqual(request(port, "/evaluator/finish", "wrong")[0], 404)
                self.assertFalse((Path(directory) / "result.json").exists())
                with connect(f"http://127.0.0.1:{port}/mcp") as tools:
                    tools.uplink([{"action": "inspect", "region": "r3"}])
                    status, result = request(port, "/evaluator/finish", token)
                    self.assertEqual((status, result["tick"], result["reward"]), (200, 60, 0))
                    self.assertEqual(request(port, "/evaluator/finish", token), (status, result))
                    with self.assertRaises(RemoteToolError):
                        tools.rules()
                replay = json.loads((Path(directory) / "replay.json").read_text())
                self.assertEqual(len(replay["expedition"]["inspection_executed"]), 1)
                self.assertNotIn(token, "".join(p.read_text() for p in Path(directory).iterdir()))
            finally:
                server.should_exit = True
                thread.join(timeout=10)

    def test_evaluator_without_configured_token_is_always_not_found(self):
        port = free_port()
        app = build_server(ExpeditionService(100)).streamable_http_app()
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started and time.monotonic() < deadline:
                time.sleep(.03)
            self.assertTrue(server.started)
            for token in (None, "anything"):
                self.assertEqual(request(port, "/evaluator/finish", token), (404, {"error": "not found"}))
        finally:
            server.should_exit = True
            thread.join(timeout=10)

    def test_cli_creates_private_token_and_grades_on_shutdown(self):
        with tempfile.TemporaryDirectory() as directory:
            token_file = Path(directory) / "private/token"
            artifacts = Path(directory) / "artifacts"
            port = free_port()
            env = dict(os.environ, EXPEDITION_MISSION_SEED="2", EXPEDITION_SEED="100", EXPEDITION_VISIBILITY="public", EXPEDITION_TOKEN_FILE=str(token_file), EXPEDITION_ARTIFACT_DIR=str(artifacts), PYTHONDONTWRITEBYTECODE="1")
            process = subprocess.Popen([sys.executable, "-m", "lightlag_expedition.serve", "--transport", "http", "--port", str(port)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    try:
                        if request(port, "/healthz")[0] == 200:
                            break
                    except OSError:
                        time.sleep(.05)
                self.assertIsNone(process.poll())
                self.assertEqual(token_file.stat().st_mode & 0o777, 0o600)
                with connect(f"http://127.0.0.1:{port}/mcp") as tools:
                    self.assertEqual(tools.rules()["science"]["visibility"], "public")
                    self.assertIn("public_qualities", tools.rules()["science"])
                    self.assertEqual(tools.map(), ExpeditionEnvironment(100, mission_seed=2, visibility="public").map())
                    tools.uplink([{"action": "inspect", "region": "r1"}])
                process.terminate()
                process.wait(timeout=10)
                self.assertEqual(json.loads((artifacts / "result.json").read_text())["tick"], 60)
                replay = json.loads((artifacts / "replay.json").read_text())
                self.assertEqual(len(replay["expedition"]["inspection_executed"]), 1)
                before = token_file.read_bytes()
                restart = subprocess.run([sys.executable, "-m", "lightlag_expedition.serve", "--transport", "http", "--port", str(port)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=10)
                self.assertNotEqual(restart.returncode, 0)
                self.assertEqual(token_file.read_bytes(), before)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
