#!/usr/bin/env python3
"""Rebuild an agent's own program from its trajectory, as Kristján did by hand for the Claude runs.

    python3 tools/tier_agents/rebuild_program.py docs/lightlag-runs/traverse-agent-gpt-6.1-sol-1

Kristján's note on his runs: "program/ was rebuilt from the trajectory (agent/trajectory.json):
the agent's file writes and later edits replayed in order, nothing executed". This does that
for OpenCode's file tools: `write` and `edit` (Claude, Gemini) and `apply_patch` (GPT). Files
under /app are kept (the agent's working folder in the task); scratch files elsewhere are not.
The program is the last .py file the agent started under /app (`python3 /app/detach.py python3
X.py`, or `python3 X.py`); a run that never started one drove by hand and has no program.

Writes <run>/program/ and <run>/run.json in the shape of Kristján's run.json, and prints the
farm policy, `agent:<run>/program/<entry>`. An edit that does not apply (its old text is
missing, as when the agent's own edit failed) is skipped and listed in run.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath

NAMES = {"gpt-6-luna": "GPT-6 Luna", "gpt-6.1-terra": "GPT-6.1 Terra", "gpt-6.1-sol": "GPT-6.1 Sol",
         "gemini-4-hydrogen": "Gemini 4 Hydrogen", "gemini-4-argon": "Gemini 4 Argon",
         "gemini-4-carbon": "Gemini 4 Carbon"}
LAUNCH = re.compile(r"python3?\s+(?:-u\s+)?(?:/app/detach\.py\s+python3?\s+(?:-u\s+)?)?(\S+\.py)\b")


def resolve(path: str, workdir: str = "/app") -> str:
    full = PurePosixPath(path) if path.startswith("/") else PurePosixPath(workdir) / path
    parts = []
    for part in full.parts:
        if part == "..":
            parts.pop()
        elif part != ".":
            parts.append(part)
    return str(PurePosixPath(*parts))


def apply_patch(files: dict, text: str, skipped: list) -> None:
    """OpenAI's patch format: *** Add File / *** Update File (@@ hunks) / *** Delete File."""
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("*** Add File: "):
            path = resolve(line[len("*** Add File: "):].strip())
            body = []
            i += 1
            while i < len(lines) and not lines[i].startswith("*** "):
                body.append(lines[i][1:] if lines[i].startswith("+") else lines[i])
                i += 1
            files[path] = "\n".join(body) + "\n"
        elif line.startswith("*** Delete File: "):
            files.pop(resolve(line[len("*** Delete File: "):].strip()), None)
            i += 1
        elif line.startswith("*** Update File: "):
            path = resolve(line[len("*** Update File: "):].strip())
            i += 1
            target = path
            if i < len(lines) and lines[i].startswith("*** Move to: "):
                target = resolve(lines[i][len("*** Move to: "):].strip())
                i += 1
            content = files.get(path)
            hunks, hunk = [], None
            while i < len(lines) and not lines[i].startswith("*** "):
                if lines[i].startswith("@@"):
                    hunk = ([], [])
                    hunks.append(hunk)
                elif hunk is not None and lines[i] != "":
                    tag, rest = lines[i][0], lines[i][1:]
                    if tag in " -":
                        hunk[0].append(rest)
                    if tag in " +":
                        hunk[1].append(rest)
                elif hunk is not None:
                    hunk[0].append("")
                    hunk[1].append("")
                i += 1
            if content is None:
                skipped.append("update of a file never written: " + path)
                continue
            for old, new in hunks:
                while old and old[-1] == "" and new and new[-1] == "":
                    old, new = old[:-1], new[:-1]
                before, after = "\n".join(old), "\n".join(new)
                if before and before in content:
                    content = content.replace(before, after, 1)
                else:
                    skipped.append("patch hunk not found in " + path)
            files.pop(path, None)
            files[target] = content
        else:
            i += 1


def replay(trajectory: dict):
    files, skipped, launches = {}, [], []
    for step in trajectory.get("steps", []):
        for call in step.get("tool_calls") or []:
            name, args = call.get("function_name"), call.get("arguments") or {}
            if name == "write" and "filePath" in args:
                files[resolve(args["filePath"])] = args.get("content", "")
            elif name == "edit" and "filePath" in args:
                path = resolve(args["filePath"])
                old, new = args.get("oldString", ""), args.get("newString", "")
                if path in files and old and old in files[path]:
                    files[path] = files[path].replace(old, new) if args.get("replaceAll") else files[path].replace(old, new, 1)
                else:
                    skipped.append("edit not applied to " + path)
            elif name == "apply_patch":
                apply_patch(files, args.get("patchText") or args.get("patch") or "", skipped)
            elif name == "bash":
                command, workdir = args.get("command", ""), args.get("workdir") or "/app"
                for match in LAUNCH.finditer(command):
                    script = resolve(match.group(1), workdir)
                    if not script.endswith("/detach.py") and script in files:
                        launches.append(script)
    return files, skipped, launches


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run", type=Path, help="a saved run folder under docs/lightlag-runs/")
    args = parser.parse_args(argv)
    run = args.run
    trajectory = json.loads((run / "agent" / "trajectory.json").read_text(encoding="utf-8"))
    config = json.loads((run / "config.json").read_text(encoding="utf-8"))
    result = json.loads((run / "result.json").read_text(encoding="utf-8"))
    files, skipped, launches = replay(trajectory)
    app = {path: text for path, text in files.items() if path.startswith("/app/") and path.count("/") == 2}
    entry = launches[-1] if launches and launches[-1] in app else None

    model = config["agent"]["model_name"]
    short = model.split("/", 1)[1]
    number = re.search(r"-(\d+)$", run.name).group(1)
    task = config["task"]["path"].rstrip("/").split("/")[-1]
    version = re.search(r'^version = "([^"]+)"', (Path(__file__).resolve().parents[2] / "harbor" / task / "task.toml")
                        .read_text(encoding="utf-8"), re.M).group(1)
    ledger = Path(__file__).resolve().parents[2] / "docs" / "tier-comparison" / "runs.jsonl"
    cost = next((json.loads(line).get("cost_usd_from_prices") for line in ledger.read_text().splitlines()
                 if json.loads(line)["name"] == run.name), None) if ledger.exists() else None
    meta = {"kind": "gpt" if short.startswith("gpt") else "gemini",
            "label": "{} · agent {}".format(NAMES.get(short, short), number),
            "model": NAMES.get(short, short), "how": "OpenCode agent",
            "source": "harbor run -p harbor/{} -a opencode -m {} --ak version=1.19.5 (Harbor 0.25.0); "
                      "tools/tier_agents/run.sh".format(task, model),
            "cost_usd": cost, "harbor_exception": (result.get("exception_info") or {}).get("exception_type"),
            "task_version": version}
    if entry:
        program = run / "program"
        program.mkdir(exist_ok=True)
        for path, text in app.items():
            if path.endswith(".py"):
                (program / PurePosixPath(path).name).write_text(text, encoding="utf-8")
        meta["program"] = ("program/ was rebuilt from the trajectory (agent/trajectory.json) by "
                           "tools/tier_agents/rebuild_program.py: the agent's file writes and later edits replayed "
                           "in order, nothing executed. Entry: {} (the last program the agent started; started {} "
                           "time(s) in all).".format(PurePosixPath(entry).name, len(launches)))
        if skipped:
            meta["program_skipped_edits"] = skipped
        print("agent:{}/program/{}".format(run.as_posix(), PurePosixPath(entry).name))
    else:
        meta["program"] = "none: the agent never started a program under /app (it drove by hand or left none)"
        print("no program: {}".format(run.name), file=sys.stderr)
    (run / "run.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
