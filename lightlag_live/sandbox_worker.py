"""Runs inside the sandbox container: loads /w/policy.py and lets it play a campaign.

Protocol: one JSON object per line on the real stdout; the broker (`lightlag_live.sandbox`)
answers one line per request. The policy's own prints go to stderr so they cannot corrupt
the protocol. `play(tools)` is called once per mission, fresh each time: an exception ends
its control of that mission only, which is kinder than a real run, where a crashed program
stays down until someone restarts it.

Standard library only; imports nothing from the repository.
"""

import importlib.util
import json
import sys
import traceback

_out = sys.stdout
sys.stdout = sys.stderr


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
    tools = Tools()
    errors = []
    try:
        spec = importlib.util.spec_from_file_location("policy", "/w/policy.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        while True:
            campaign = tools.rules()["campaign"]
            if campaign["complete"]:
                break
            mission = campaign["mission"]
            try:
                module.play(tools)
            except SystemExit:
                raise
            except BaseException as failure:  # the policy's failure is a result, not a harness crash
                errors.append({"mission": mission, "error": "{}: {}".format(type(failure).__name__, failure)[:400]})
                traceback.print_exc(file=sys.stderr)
            while True:  # sit out whatever is left of this mission
                campaign = tools.rules()["campaign"]
                if campaign["complete"] or campaign["mission"] != mission:
                    break
                if tools.advance(5)["campaign_complete"]:
                    break
    except SystemExit:
        pass
    except BaseException as failure:
        errors.append({"mission": None, "error": "{}: {}".format(type(failure).__name__, failure)[:400]})
        traceback.print_exc(file=sys.stderr)
    _send({"method": "done", "errors": errors})


if __name__ == "__main__":
    main()
