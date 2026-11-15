#!/usr/bin/env python3
"""Rebuild an agent's own program from its trajectory, as Kristján did by hand for the Claude runs.

    python3 tools/tier_agents/rebuild_program.py docs/lightlag-runs/traverse-agent-gpt-6.1-sol-1

Kristján's note on his runs: "program/ was rebuilt from the trajectory (agent/trajectory.json):
the agent's file writes and later edits replayed in order, nothing executed". This does that
for OpenCode's file tools: `write` and `edit` (Claude, Gemini) and `apply_patch` (GPT), and for
`cat << EOF > file` blocks in shell commands. The program is the last .py file the agent started
(`python3 /app/detach.py [--log F] python3 X.py`, or `python3 X.py`) that sends commands, itself
or through a module beside it, to the mission (a report script run after the mission, or a
simulator of the agent's own, is not it); the files in
its folder are kept. A run that never started such a file drove by hand or never drove, and has
no program. A file changed by a script the agent ran (not by a write or edit) is not replayed.

Writes <run>/program/ and <run>/run.json in the shape of Kristján's run.json, and prints the
farm policy, `agent:<run>/program/<entry>`. An edit whose old text is not found exactly is
applied the way OpenCode's edit tool applies it (trimmed lines, then first and last lines), and
listed in run.json; one that does not apply at all (the agent's own edit failed) is skipped.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path, PurePosixPath

NAMES = {"gpt-6-luna": "GPT-6 Luna", "gpt-6.1-terra": "GPT-6.1 Terra", "gpt-6.1-sol": "GPT-6.1 Sol",
         "gemini-4-hydrogen": "Gemini 4 Hydrogen", "gemini-4-argon": "Gemini 4 Argon",
         "gemini-4-carbon": "Gemini 4 Carbon"}
LAUNCH = re.compile(r"python3?\s+(?:-u\s+)?(?:\S*detach\.py\s+(?:--\w+\s+\S+\s+)*python3?\s+(?:-u\s+)?)?(\S+\.py)\b")


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


HEREDOC_START = re.compile(r"""^\s*cat\s+(?:<<-?\s*['"]?(\w+)['"]?\s*>\s*(\S+)|>\s*(\S+)\s+<<-?\s*['"]?(\w+)['"]?)\s*$""")


def heredoc_writes(command: str):
    """`cat << 'EOF' > path` (or `cat > path << EOF`) blocks in a shell command: a file write."""
    lines = command.split("\n")
    i = 0
    while i < len(lines):
        match = HEREDOC_START.match(lines[i])
        i += 1
        if not match:
            continue
        marker, path = (match.group(1), match.group(2)) if match.group(1) else (match.group(4), match.group(3))
        body = []
        while i < len(lines) and lines[i].strip() != marker:
            body.append(lines[i])
            i += 1
        i += 1
        yield path, "\n".join(body) + "\n"


def modules_of(script: str, files: dict) -> list:
    """The script and the agent's own modules it imports, found beside it or in a folder it puts
    on sys.path (`sys.path.insert(0, "/tmp/opencode")`), recursively."""
    seen, todo = [], [script]
    while todo:
        path = todo.pop()
        if path in seen or path not in files:
            continue
        seen.append(path)
        text = files[path]
        folders = [str(PurePosixPath(path).parent)] + re.findall(r"sys\.path\.(?:insert\(\s*\d+\s*,|append\()\s*['\"]([^'\"]+)['\"]", text)
        for module in re.findall(r"^\s*(?:from|import)\s+(\w+)", text, re.M):
            for folder in folders:
                if folder.rstrip("/") + "/" + module + ".py" in files:
                    todo.append(folder.rstrip("/") + "/" + module + ".py")
                    break
    return seen


def drives(script: str, files: dict) -> bool:
    """True when the script, with the agent's modules it imports, talks to the mission
    (`lightlag_client`) and sends commands (`uplink`); a simulator of the agent's own is not it."""
    text = "\n".join(files[path] for path in modules_of(script, files))
    return "lightlag_client" in text and "uplink(" in text


def loose_match(content: str, old: str):
    """OpenCode's edit tool falls back when the old text is not found exactly: lines equal once
    trimmed, then a block whose first and last lines match (one such block only)."""
    lines, want = content.split("\n"), old.split("\n")
    while want and not want[-1].strip():
        want = want[:-1]
    n = len(want)
    trimmed = [i for i in range(len(lines) - n + 1)
               if all(lines[i + k].strip() == want[k].strip() for k in range(n))]
    if len(trimmed) == 1:
        return "trimmed-line", "\n".join(lines[trimmed[0]:trimmed[0] + n])
    if n >= 3:
        blocks = []
        for i, line in enumerate(lines):
            if line.strip() != want[0].strip():
                continue
            for j in range(i + 2, len(lines)):
                if lines[j].strip() == want[-1].strip():
                    blocks.append((i, j))
                    break
        if len(blocks) == 1:
            i, j = blocks[0]
            return "first-and-last-line", "\n".join(lines[i:j + 1])
    return None


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
                elif path in files and old and loose_match(files[path], old):
                    kind, found = loose_match(files[path], old)
                    files[path] = files[path].replace(found, new, 1)
                    skipped.append("edit to {} applied by {} match, as OpenCode's edit tool does".format(path, kind))
                else:
                    skipped.append("edit not applied to " + path)
            elif name == "apply_patch":
                apply_patch(files, args.get("patchText") or args.get("patch") or "", skipped)
            elif name == "bash":
                command, workdir = args.get("command", ""), args.get("workdir") or "/app"
                for path, text in heredoc_writes(command):
                    files[resolve(path, workdir)] = text
                for match in LAUNCH.finditer(command):
                    script = resolve(match.group(1), workdir)
                    if not script.endswith("/detach.py") and script in files and drives(script, files):
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
    entry = launches[-1] if launches else None
    folder = str(PurePosixPath(entry).parent) if entry else "/app"
    folders = {folder} | {str(PurePosixPath(path).parent) for path in (modules_of(entry, files) if entry else [])}
    app = {}
    for path, text in files.items():   # the entry's folder first, so its own files win a name clash
        if str(PurePosixPath(path).parent) in folders and (PurePosixPath(path).name not in {PurePosixPath(p).name for p in app}
                                                         or str(PurePosixPath(path).parent) == folder):
            app[path] = text

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
        prepare = (program / "farm_prepare.py").read_text(encoding="utf-8") if (program / "farm_prepare.py").exists() else None
        if program.exists():
            shutil.rmtree(program)
        program.mkdir()
        if prepare:   # added by hand for the farm, as Kristján did for Opus 3; kept
            (program / "farm_prepare.py").write_text(prepare, encoding="utf-8")
        for path, text in app.items():
            if path.endswith(".py"):
                (program / PurePosixPath(path).name).write_text(text, encoding="utf-8")
        meta["program"] = ("program/ was rebuilt from the trajectory (agent/trajectory.json) by "
                           "tools/tier_agents/rebuild_program.py: the agent's file writes and later edits replayed "
                           "in order, nothing executed. Entry: {} (the last program the agent started that sends commands; "
                           "{} such start(s) in all; files kept from {}).".format(PurePosixPath(entry).name, len(launches), ", ".join(sorted(folders))))
        if skipped:
            meta["program_skipped_edits"] = skipped
        if prepare and (run / "run.json").exists():   # keep the note on the hand-added farm_prepare.py
            before = json.loads((run / "run.json").read_text(encoding="utf-8"))
            note = before.get("program", "").partition(" farm_prepare.py was added")
            if note[1]:
                meta["program"] += note[1] + note[2]
            if before.get("farm_policy"):
                meta["farm_policy"] = before["farm_policy"]
        print("agent:{}/program/{}".format(run.as_posix(), PurePosixPath(entry).name))
    else:
        if (run / "program").exists():
            shutil.rmtree(run / "program")
        meta["program"] = "none: the agent never started a saved program that sends commands (it drove by hand or never drove)"
        print("no program: {}".format(run.name), file=sys.stderr)
    (run / "run.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
