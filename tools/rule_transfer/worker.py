"""Single-episode worker, copied into a restricted container with only policy.py.

The simulator and its private state remain outside this process. The policy sees
the five public tool replies through a JSON-lines broker. No repository imports.
"""

import importlib.util
import json
import sys
import traceback


_out = sys.stdout
sys.stdout = sys.stderr


def send(message):
    _out.write(json.dumps(message, separators=(",", ":")) + "\n")
    _out.flush()


class Tools:
    def _call(self, method, **params):
        send({"method": method, "params": params})
        line = sys.stdin.readline()
        if not line:
            raise RuntimeError("tool broker disconnected")
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
    try:
        spec = importlib.util.spec_from_file_location("policy", "/w/policy.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.play(Tools())
    except BaseException as failure:
        traceback.print_exc(file=sys.stderr)
        send({"method": "done", "status": "policy_error",
              "error": "{}: {}".format(type(failure).__name__, failure)[:2000]})
    else:
        send({"method": "done", "status": "returned"})


if __name__ == "__main__":
    main()
