"""Evaluator-side command: close and grade the campaign on a running HTTP server.

    python -m lightlag_live.finish --token-file /run/lightlag/token

Meant to run inside the simulator's own container (a Harbor collect hook), after the agent's
container has stopped. It reads the token the server generated at start-up, asks the server
to finish, and prints the result. Every remaining tick of every remaining mission passes at
once; the server writes result.json and one replay per mission to its artifact directory.

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Optional, Sequence


def finish(url: str, token: str, timeout: float = 60.0) -> dict:
    request = urllib.request.Request(
        url.rstrip("/") + "/evaluator/finish", data=b"", method="POST",
        headers={"Authorization": "Bearer {}".format(token)},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="lightlag_live.finish", description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="base URL of the server")
    parser.add_argument("--token-file", default=os.environ.get("LIGHTLAG_TOKEN_FILE"),
                        help="file holding the evaluator token (default: $LIGHTLAG_TOKEN_FILE)")
    args = parser.parse_args(argv)
    token = os.environ.get("LIGHTLAG_EVALUATOR_TOKEN")
    if not token and args.token_file:
        with open(args.token_file, encoding="utf-8") as stream:
            token = stream.read().strip()
    if not token:
        print("no evaluator token: set LIGHTLAG_EVALUATOR_TOKEN or pass --token-file", file=sys.stderr)
        return 2
    try:
        result = finish(args.url, token)
    except urllib.error.HTTPError as failure:
        print("server refused to finish the campaign (HTTP {})".format(failure.code), file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError) as failure:
        print("could not reach the server at {}: {}".format(args.url, failure), file=sys.stderr)
        return 1
    print(json.dumps({"reward": result["reward"], "finished_by": result["finished_by"],
                      "missions": [round(m["reward"], 6) for m in result["missions"]]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
