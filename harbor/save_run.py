#!/usr/bin/env python3
"""Copy one Harbor trial into docs/lightlag-runs/ as shareable evidence.

    python3 harbor/save_run.py <trial-dir> <name>

Harbor writes a trial's logs with absolute local paths. This copies the trial,
replaces the local jobs directory with `<jobs-dir>`, and refuses to copy anything
that looks like a credential. Standard library only.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import List, Optional, Sequence

REPO = Path(__file__).resolve().parent.parent
RUNS = REPO / "docs" / "lightlag-runs"
TEXT_SUFFIXES = {".json", ".jsonl", ".txt", ".log", ".md", ".toml", ".yaml", ".yml"}
SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"sk-(?:proj|svcacct|admin)-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}"),
]


def find_secrets(text: str) -> List[str]:
    return [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("trial_dir", type=Path, help="a trial directory inside a Harbor jobs directory")
    parser.add_argument("name", help="folder name under docs/lightlag-runs/")
    parser.add_argument("--check-env", type=Path, metavar="ENV_FILE",
                        help="when a credential pattern matches, copy anyway only if no value from this .env "
                             "file appears in any file (a pattern can match a random blob, e.g. an encrypted "
                             "reasoning record); without it any match refuses")
    args = parser.parse_args(argv)
    source = args.trial_dir.resolve()
    if not (source / "result.json").is_file():
        print("not a Harbor trial directory: {}".format(source), file=sys.stderr)
        return 2
    if not re.fullmatch(r"[a-z0-9][a-z0-9.\-]*", args.name) or ".." in args.name:
        print("name must be lowercase letters, digits, dots and dashes", file=sys.stderr)
        return 2
    secrets = []
    if args.check_env:
        for line in args.check_env.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() and len(value.strip()) >= 16:
                secrets.append(value.strip())
    jobs_dir = str(source.parent.parent)
    files = sorted(p for p in source.rglob("*") if p.is_file())
    cleaned = {}
    for path in files:
        relative = path.relative_to(source)
        if relative.parts[:2] == ("agent", "opencode"):
            continue  # the agent's private working state (database, snapshots); not evidence
        if path.suffix.lower() not in TEXT_SUFFIXES:
            print("skipping non-text file: {}".format(relative))
            continue
        text = path.read_text(encoding="utf-8", errors="replace").replace(jobs_dir, "<jobs-dir>")
        if any(secret in text for secret in secrets):
            print("refusing to copy: {} contains a value from {}".format(relative, args.check_env), file=sys.stderr)
            return 1
        hits = find_secrets(text)
        if hits and not secrets:
            print("refusing to copy: {} matches {}".format(relative, hits), file=sys.stderr)
            return 1
        if hits:
            print("{} matches {}, but no value from {} is in it; copied".format(relative, hits, args.check_env))
        cleaned[relative] = text
    destination = RUNS / args.name
    if destination.exists():
        shutil.rmtree(destination)
    for relative, text in cleaned.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    print("saved {} files to {}".format(len(cleaned), destination.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
