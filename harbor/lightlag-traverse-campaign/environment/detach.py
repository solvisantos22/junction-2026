#!/usr/bin/env python3
"""Start a long-running program so that it outlives the shell command that started it.

    python3 /app/detach.py python3 autopilot.py                  # output goes to ./autopilot.log
    python3 /app/detach.py --log second.log python3 autopilot.py

Prints the process id and returns at once. Stop the program with `kill <pid>`.

Why this exists. An agent's shell tool runs one command at a time under a time limit. Such a
tool typically waits until everything the command started has let go of its output, and when
the limit is reached it stops the whole process group. A program started with `&` or `nohup`
is still in that group, and in a form like `cd /app && nohup python3 autopilot.py > log 2>&1 &`
the shell that waits for it still holds the tool's output. The call then hangs until the limit
and the program is killed with it, in the middle of a campaign that does not wait.

A program started here has its own session and no link to the caller's input or output: it
reads from nowhere and writes to the log file, unbuffered so the log is current. Standard
library only; needs a POSIX system.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Optional, Sequence


def start(command: Sequence[str], log: str = "autopilot.log") -> int:
    """Start `command` detached, appending its output to `log`; return its process id."""
    environment = dict(os.environ, PYTHONUNBUFFERED="1")
    with open(log, "ab") as stream:
        process = subprocess.Popen(list(command), stdin=subprocess.DEVNULL, stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True,
                                   close_fds=True, env=environment)
    return process.pid


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Start a program that keeps running after this command returns.",
        usage="python3 detach.py [--log FILE] command [argument ...]")
    parser.add_argument("--log", default="autopilot.log", help="file the program's output is appended to")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="the program and its arguments")
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("give the program to start, for example: python3 autopilot.py")
    try:
        pid = start(command, args.log)
    except OSError as failure:
        print("could not start {}: {}".format(command[0], failure), file=sys.stderr)
        return 1
    print("started pid {}; its output goes to {}; stop it with: kill {}".format(
        pid, os.path.abspath(args.log), pid))
    return 0


if __name__ == "__main__":
    sys.exit(main())
