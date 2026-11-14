"""Minimal stdlib-only container entry point; never contains episode identity."""

import importlib.util
import json
import random
import sys

INPUT = sys.stdin.buffer
OUTPUT = sys.stdout.buffer
sys.stdout = sys.stderr  # Policy print/debug output cannot accidentally become RPC.
random.seed(0)


def send(value):
    OUTPUT.write(json.dumps(value, separators=(",", ":"), allow_nan=False).encode() + b"\n")
    OUTPUT.flush()


class Tools:
    __slots__ = ("sequence",)

    def __init__(self):
        self.sequence = 0

    def _call(self, tool, arguments):
        self.sequence += 1
        send({"id": self.sequence, "tool": tool, "arguments": arguments})
        line = INPUT.readline(1024**2 + 1)
        if not line.endswith(b"\n") or len(line) > 1024**2:
            raise RuntimeError("broker response absent or over limit")
        reply = json.loads(line)
        if reply.get("id") != self.sequence:
            raise RuntimeError("broker response sequence mismatch")
        if not reply["ok"]:
            raise ValueError(reply["error"]["message"])
        return reply["response"]

    def rules(self):
        return self._call("rules", {})

    def map(self):
        return self._call("map", {})

    def telemetry_log(self):
        return self._call("telemetry_log", {})

    def uplink(self, commands):
        return self._call("uplink", {"commands": commands})

    def advance(self, ticks=1):
        return self._call("advance", {"ticks": ticks})


send({"ready": True, "python": sys.version.split()[0]})
if json.loads(INPUT.readline(1024)) != {"start": True}:
    raise RuntimeError("broker start handshake is invalid")
try:
    spec = importlib.util.spec_from_file_location("generated_policy", "/app/policy.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.play(Tools())
except BaseException as error:
    send({"done": True, "status": "policy_error",
          "error": {"type": type(error).__name__, "message": str(error)[:2048]}})
else:
    send({"done": True, "status": "returned", "error": None})
