"""Runs inside the sandbox container: loads /w/policy.py and lets it play one traverse mission.

Protocol: one JSON object per line on the real stdout; the broker (`lightlag_traverse.sandbox`)
answers one line per request. The policy's own prints go to stderr so they cannot corrupt the
protocol. `play(tools)` is called once. Standard library only; imports nothing from the
repository except the published ground model, which sits beside the policy as
`lightlag_surface.py`, as it does in the task's container.
"""

import importlib.util
import json
import sys
import traceback

_out = sys.stdout
sys.stdout = sys.stderr
sys.path.insert(0, "/w")


def _send(message):
    _out.write(json.dumps(message) + "\n")
    _out.flush()


class Tools:
    def _call(self, method, **params):
        _send({"method": method, "params": params})
        line = sys.stdin.readline()
        if not line:
            raise SystemExit(0)
        reply = json.loads(line)
        if not reply["ok"]:
            raise ValueError(reply["error"])
        return reply["result"]

    def rules(self):
        return self._call("rules")

    def map(self):
        return self._call("map")

    def telemetry_log(self):
        return self._call("telemetry_log")

    def uplink(self, commands):
        return self._call("uplink", commands=commands)

    def advance(self, ticks=1):
        return self._call("advance", ticks=ticks)


def main():
    errors = []
    try:
        spec = importlib.util.spec_from_file_location("policy", "/w/policy.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.play(Tools())
    except SystemExit:
        pass
    except BaseException as failure:  # the policy's failure is a result, not a harness crash
        errors.append("{}: {}".format(type(failure).__name__, failure)[:400])
        traceback.print_exc(file=sys.stderr)
    _send({"method": "done", "errors": errors})


if __name__ == "__main__":
    main()
