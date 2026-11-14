"""Actual MCP transport and evaluator HTTP isolation (mcp 2.3)."""

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

from lightlag_information_allocation import Environment
from lightlag_information_allocation.policies import run_policy
from lightlag_information_allocation.service import InformationService

try:
    import uvicorn
    from mcp import Client
    from lightlag_mcp.client import connect, RemoteToolError
    from lightlag_information_allocation.server import build_server
    HAVE_MCP = True
except ImportError:
    HAVE_MCP = False


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(port, path, token=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method="POST" if path.endswith("finish") else "GET", data=b"" if path.endswith("finish") else None)
    if token is not None:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


@unittest.skipUnless(HAVE_MCP, "mcp 2.3 dependency unavailable")
class McpTests(unittest.TestCase):
    def test_exactly_five_tools_no_private_resources_or_prompts(self):
        async def inspect():
            async with Client(build_server(InformationService(100))) as client:
                return ((await client.list_tools()).tools,
                        (await client.list_resources()).resources,
                        (await client.list_prompts()).prompts, client.instructions)
        tools, resources, prompts, instructions = asyncio.run(inspect())
        self.assertEqual([tool.name for tool in tools], ["rules", "map", "telemetry_log", "uplink", "advance"])
        self.assertEqual((resources, prompts), ([], []))
        self.assertIn("Accepted route commitments cannot be changed", instructions)
        self.assertNotIn("wheel slip", instructions)

    def test_reference_and_rejections_through_real_client(self):
        for context in ("case_1", "case_2", "case_3", "case_4", "case_5", "case_6"):
            service = InformationService(100, context)
            env = Environment(100, context)
            with connect(build_server(service)) as tools:
                for invalid in (99, True, "1", 1.5):
                    with self.assertRaises(RemoteToolError):
                        tools.advance(invalid)
                run_policy(tools, "selective")
            run_policy(env, "selective")
            self.assertEqual(service.finish()["reward"], env.evaluate()["reward"])

    def test_http_evaluator_requires_token_and_never_reveals_it(self):
        with tempfile.TemporaryDirectory() as directory:
            service = InformationService(100, artifact_dir=directory)
            token = "test-only-evaluator-secret"
            port = free_port()
            app = build_server(service, token).streamable_http_app()
            server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
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
                    tools.uplink([{"action": "commit", "route": "detour"}])
                    status, result = request(port, "/evaluator/finish", token)
                    self.assertEqual((status, result["reward"]), (200, .4))
                    with self.assertRaises(RemoteToolError):
                        tools.rules()
                self.assertNotIn(token, ''.join(p.read_text() for p in Path(directory).iterdir()))
            finally:
                server.should_exit = True
                thread.join(timeout=10)

    def test_cli_creates_private_token_and_grades_on_shutdown(self):
        with tempfile.TemporaryDirectory() as directory:
            token_file = Path(directory) / "private/token"
            artifacts = Path(directory) / "artifacts"
            port = free_port()
            env = dict(os.environ, INFORMATION_CONTEXT="case_6", INFORMATION_SEED="100", INFORMATION_TOKEN_FILE=str(token_file), INFORMATION_ARTIFACT_DIR=str(artifacts), PYTHONDONTWRITEBYTECODE="1")
            process = subprocess.Popen([sys.executable, "-m", "lightlag_information_allocation.serve", "--transport", "http", "--port", str(port)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
                    self.assertEqual(tools.rules()["context"]["id"], "case_6")
                    tools.uplink([{"action": "commit", "route": "detour"}])
                process.terminate()
                process.wait(timeout=10)
                self.assertEqual(json.loads((artifacts / "result.json").read_text())["reward"], .4)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
