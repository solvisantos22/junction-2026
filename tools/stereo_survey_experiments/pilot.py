"""Prepare, sandbox and (only with an explicit budget) request stereo solvers.

The model does not run on the host. Generation never receives search.py,
reference plans, check missions or check outcomes. No retries or fallback calls.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import tempfile
import time
import uuid

from stereo_survey.mission import generate
from stereo_survey.search import Problem, exact
from stereo_survey.verify import verify

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MODEL = "claude-opus-5-5"
MAX_TOKENS = 64_000
MAX_BUDGET = 5.0
IMAGE = "sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b"
PRICES = {"input": 4.0, "output": 20.0}  # USD / million tokens, standard global.
PRICE_SOURCE = "https://platform.claude.com/docs/en/models/opus-5-5/overview"
HINT = """
## Additional solver hint

Precompute the useful-cell bitmask of every compatible image pair. Enumerate
feasible local sequences per camera, choosing skip or one image at each tick.
Then optimize the union of internal and cross-camera pair coverage over pairs
of local sequences. Cache weighted coverage values and use optimistic coverage
bounds or another suitable search strategy to meet the runtime limit. The
validator is useful for checking resource semantics; avoid recomputing all
geometry inside every search node. This hint supplies no solution or optimum.
"""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def source_hashes():
    paths = [*sorted((ROOT / "stereo_survey").glob("*.py")),
             *sorted(HERE.glob("*.py")), HERE / "task.md"]
    return {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in paths}


def prepare(bundle):
    bundle.mkdir(parents=True, exist_ok=False)
    public = bundle / "public" / "stereo_survey"
    public.mkdir(parents=True)
    (public / "__init__.py").write_text("")
    prompt = (HERE / "task.md").read_text()
    for name in ("geometry.py", "verify.py"):
        source = (ROOT / "stereo_survey" / name).read_text()
        (public / name).write_text(source)
        prompt += f"\n## Public stereo_survey/{name}\n\n```python\n{source}```\n"
    shutil.copyfile(HERE / "worker.py", bundle / "public" / "worker.py")
    for seed, profile in ((0, "compact"), (1, "expanded")):
        mission = generate(seed, profile)
        save(bundle / f"development-{profile}.json", mission)
        prompt += f"\n## Development example: {profile}\n\n```json\n{json.dumps(mission)}\n```\n"
    (bundle / "plain.md").write_text(prompt)
    (bundle / "hinted.md").write_text(prompt + HINT)
    protocol = {
        "version": "stereo-agent-falsification-v2", "model": MODEL,
        "effort": "high", "max_tokens": MAX_TOKENS,
        "attempts": [{"id": "plain-1", "prompt": "plain.md"},
                     {"id": "plain-2", "prompt": "plain.md"},
                     {"id": "hinted-1", "prompt": "hinted.md"}],
        "check": {"start": 62000, "count": 24, "profiles": ["compact", "expanded"]},
        "reference": {"max_local": 10_000, "max_joint": 10_000_000},
        "sandbox": {"image": IMAGE, "image_label": "python:3.12-slim", "seconds": 30, "memory": "512m",
                    "cpus": "1", "output_bytes": 65_536},
        "source_hashes": source_hashes(),
        "bundle_hashes": {str(p.relative_to(bundle)): digest(p.read_bytes())
                          for p in sorted(bundle.rglob("*")) if p.is_file()},
        "prices_per_million": PRICES, "price_source": PRICE_SOURCE,
        "price_checked": "2026-11-14", "proposed_budget_usd": MAX_BUDGET,
        "authorization": "not granted by preparation; requires explicit user approval",
        "interpretation": "One-shot success falsifies difficulty; failure requires a feedback-enabled coding-agent control.",
    }
    save(bundle / "protocol.json", protocol)
    return protocol


def check_bundle(bundle):
    protocol = json.loads((bundle / "protocol.json").read_text())
    if protocol["source_hashes"] != source_hashes():
        raise ValueError("source changed after protocol freeze")
    for name, expected in protocol["bundle_hashes"].items():
        if digest((bundle / name).read_bytes()) != expected:
            raise ValueError(f"frozen bundle changed: {name}")
    return protocol


def extract_program(response):
    blocks = re.findall(r"```python\s*\n(.*?)```", response, flags=re.S)
    if len(blocks) != 1:
        raise ValueError("expected exactly one Python code block; preserve response, do not repair")
    program = blocks[0]
    if not re.search(r"^def solve\s*\(", program, flags=re.M):
        raise ValueError("missing top-level solve(mission)")
    compile(program, "policy.py", "exec")  # Syntax check only; never execute on host.
    return program


def sandbox(bundle, program, mission, settings):
    """Bound stdout/stderr and kill both CLI and named container on every path."""
    started = time.monotonic()
    name = "stereo-probe-" + uuid.uuid4().hex
    status, stdout, stderr = "ok", bytearray(), bytearray()
    with tempfile.TemporaryDirectory(prefix="stereo-policy-") as directory:
        workspace = Path(directory)
        shutil.copytree(bundle / "public", workspace, dirs_exist_ok=True)
        (workspace / "policy.py").write_text(program)
        # macOS temporary directories are private; the Docker non-root user needs traversal.
        workspace.chmod(0o755)
        command = ["docker", "run", "--rm", "--pull", "never", "-i", "--name", name,
                   "--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                   "--user", "65534:65534", "--memory", settings["memory"], "--memory-swap", settings["memory"],
                   "--cpus", settings["cpus"], "--pids-limit", "64", "--read-only",
                   "--tmpfs", "/tmp:rw,size=16m", "-v", f"{workspace}:/w:ro",
                   settings["image"], "python", "-I", "/w/worker.py"]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            process.stdin.write(json.dumps(mission).encode())
            process.stdin.close()
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ, stdout)
                selector.register(process.stderr, selectors.EVENT_READ, stderr)
                while selector.get_map():
                    if time.monotonic() - started > settings["seconds"]:
                        status = "timeout"
                        break
                    for key, _ in selector.select(timeout=0.1):
                        chunk = os.read(key.fd, 8192)
                        if not chunk:
                            selector.unregister(key.fileobj)
                        else:
                            remaining = settings["output_bytes"] - len(stdout) - len(stderr)
                            key.data.extend(chunk[:remaining])
                            if len(chunk) > remaining:
                                status = "output_limit"
                                break
                    if status != "ok":
                        break
            if status == "ok":
                remaining = max(0.01, settings["seconds"] - (time.monotonic() - started))
                try:
                    process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    status = "timeout"
        finally:
            subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=15, check=False)
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            process.stdout.close()
            process.stderr.close()
        if status == "ok" and process.returncode:
            status = "sandbox_error" if process.returncode == 125 else "runtime_error"
    result = {"status": status, "exit_code": process.returncode,
              "seconds": time.monotonic() - started,
              "stdout": stdout.decode(errors="replace"), "stderr": stderr.decode(errors="replace")}
    if status == "ok":
        try:
            result["plan"] = json.loads(result["stdout"])
        except ValueError:
            result["status"] = "invalid_output"
    return result


def ask(bundle, attempt, budget):
    """One bounded request, called only after the operator obtains spend approval."""
    import anthropic

    protocol = check_bundle(bundle)
    if list((bundle / "attempts").glob("*/evaluation.json")):
        raise RuntimeError("freeze all generations before the first fresh evaluation")
    preflight_path = bundle / "preflight.json"
    preflight_result = json.loads(preflight_path.read_text()) if preflight_path.exists() else {}
    if (not preflight_result.get("passed") or preflight_result.get("protocol_sha256")
            != digest((bundle / "protocol.json").read_bytes())):
        raise RuntimeError("a successful free sandbox preflight is required")
    entry = next(item for item in protocol["attempts"] if item["id"] == attempt)
    if (bundle / "attempts" / attempt).exists():
        raise FileExistsError("attempt already started; no automatic retry")
    prompt = (bundle / entry["prompt"]).read_text()
    used = 0.0
    for previous in (bundle / "attempts").glob("*/meta.json"):
        metadata = json.loads(previous.read_text())
        if "cost_usd" not in metadata:
            raise RuntimeError("prior request has unknown spend; reconcile it before another call")
        used += metadata["cost_usd"]
    # Reserve the full configured budget for requests interrupted before saving usage.
    for previous in (bundle / "attempts").glob("*/started.json"):
        if not previous.with_name("meta.json").exists():
            raise RuntimeError("prior started request has unknown spend; no automatic retry")
    client = anthropic.Anthropic(max_retries=0, timeout=240.0)
    messages = [{"role": "user", "content": prompt}]
    count = client.messages.count_tokens(model=MODEL, messages=messages,
                                         thinking={"type": "adaptive"})
    reservation = (count.input_tokens * PRICES["input"] + MAX_TOKENS * PRICES["output"]) / 1_000_000
    if used + reservation + 0.01 > budget:
        raise RuntimeError(f"insufficient approved budget: used {used:.4f}, request reserve {reservation:.4f}")
    out = bundle / "attempts" / attempt
    out.mkdir(parents=True, exist_ok=False)
    save(out / "started.json", {"model": MODEL, "effort": "high", "max_tokens": MAX_TOKENS,
                               "prompt_sha256": digest(prompt.encode()), "approved_budget_usd": budget,
                               "input_count": count.input_tokens, "request_reserve_usd": reservation})
    started = time.monotonic()
    with client.messages.stream(model=MODEL, max_tokens=MAX_TOKENS, thinking={"type": "adaptive"},
                                output_config={"effort": "high"}, messages=messages) as stream:
        message = stream.get_final_message()
    response = "\n".join(block.text for block in message.content if block.type == "text")
    (out / "response.md").write_text(response)
    usage = message.usage.model_dump()
    cost = (usage["input_tokens"] * PRICES["input"] + usage["output_tokens"] * PRICES["output"]) / 1_000_000
    metadata = {"message_id": message.id, "served_model": message.model, "usage": usage,
                "stop_reason": message.stop_reason, "cost_usd": cost,
                "seconds": time.monotonic() - started, "response_sha256": digest(response.encode())}
    try:
        program = extract_program(response)
        (out / "policy.py").write_text(program)
        metadata["policy_sha256"] = digest(program.encode())
    except (ValueError, SyntaxError) as error:
        metadata["extraction_error"] = str(error)
    save(out / "meta.json", metadata)
    return metadata


def evaluate(bundle, attempt):
    protocol = check_bundle(bundle)
    if any(not (bundle / "attempts" / item["id"] / "meta.json").exists()
           for item in protocol["attempts"]):
        raise RuntimeError("freeze all three generations before fresh evaluation")
    directory = bundle / "attempts" / attempt
    output = directory / "evaluation.json"
    if output.exists():
        raise FileExistsError("evaluation already exists; no silent retry")
    metadata = json.loads((directory / "meta.json").read_text())
    program = (directory / "policy.py").read_text() if "policy_sha256" in metadata else None
    if program is not None and digest(program.encode()) != metadata["policy_sha256"]:
        raise ValueError("policy changed after generation")
    report = {"protocol_sha256": digest((bundle / "protocol.json").read_bytes()),
              "policy_sha256": metadata.get("policy_sha256"), "attempt": attempt, "cases": []}
    check = protocol["check"]
    for profile in check["profiles"]:
        for seed in range(check["start"], check["start"] + check["count"]):
            mission = generate(seed, profile)
            reference = exact(Problem(mission), **protocol["reference"])
            reference["replay"] = verify(mission, reference["plan"])
            execution = sandbox(bundle, program, mission, protocol["sandbox"]) if program else {
                "status": "generation_failure", "error": metadata.get("extraction_error")}
            replay = verify(mission, execution["plan"]) if execution["status"] == "ok" else {
                "valid": False, "science": 0, "errors": [execution["status"]]}
            certified = (reference["proven_optimal"] and reference["replay"]["valid"]
                         and reference["science"] == reference["replay"]["science"]
                         and reference["science"] > 0)
            score = replay["science"] / reference["science"] if certified else None
            report["cases"].append({"profile": profile, "seed": seed, "mission": mission,
                                    "reference": reference, "execution": execution, "replay": replay,
                                    "fraction_of_optimum": score})
            save(output, report)  # Persist each case, including failures, before continuing.
            print(json.dumps({"attempt": attempt, "profile": profile, "seed": seed,
                              "status": execution["status"], "fraction_of_optimum": score}), flush=True)
    report["summary"] = {}
    for profile in check["profiles"]:
        cases = [case for case in report["cases"] if case["profile"] == profile]
        scores = [case["fraction_of_optimum"] for case in cases if case["fraction_of_optimum"] is not None]
        report["summary"][profile] = {"count": len(cases), "certified_nonzero": len(scores),
                                       "mean_fraction": sum(scores) / len(scores) if scores else None,
                                       "optimal": sum(value == 1 for value in scores),
                                       "valid": sum(case["replay"]["valid"] for case in cases)}
    save(output, report)
    return report["summary"]


def preflight(bundle):
    """Free checks on used development data only; reference code never enters prompts."""
    protocol = check_bundle(bundle)
    output = bundle / "preflight.json"
    if output.exists():
        raise FileExistsError("preflight already recorded")
    reference_source = (ROOT / "stereo_survey" / "search.py").read_text().replace(
        "from .geometry import", "from stereo_survey.geometry import")
    reference_source += "\ndef solve(mission):\n    return exact(Problem(mission), max_joint=10_000_000)['plan']\n"
    programs = {"empty": 'def solve(mission):\n    return {"images": []}\n',
                "invalid": 'def solve(mission):\n    return {"images": ["unknown"]}\n',
                "reference": reference_source}
    report = {"protocol_sha256": digest((bundle / "protocol.json").read_bytes()), "cases": []}
    for profile in ("compact", "expanded"):
        mission = json.loads((bundle / f"development-{profile}.json").read_text())
        optimum = exact(Problem(mission), **protocol["reference"])
        assert optimum["proven_optimal"]
        for name, program in programs.items():
            execution = sandbox(bundle, program, mission, protocol["sandbox"])
            replay = verify(mission, execution.get("plan"))
            case = {"profile": profile, "program": name, "program_sha256": digest(program.encode()),
                    "execution": execution, "replay": replay, "optimum": optimum["science"]}
            report["cases"].append(case)
            save(output, report)
            assert execution["status"] == "ok", case
            assert replay["valid"] == (name != "invalid"), case
            assert replay["science"] == (optimum["science"] if name == "reference" else 0), case
    report["passed"] = True
    save(output, report)
    return {"passed": True, "cases": len(report["cases"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "check", "preflight", "ask", "evaluate"))
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--attempt", choices=("plain-1", "plain-2", "hinted-1"))
    parser.add_argument("--approved-budget-usd", type=float)
    args = parser.parse_args()
    if args.action == "prepare":
        result = prepare(args.bundle)
    elif args.action == "check":
        result = check_bundle(args.bundle)
    elif args.action == "preflight":
        result = preflight(args.bundle)
    elif args.action == "ask":
        if not args.attempt or not args.approved_budget_usd or not 0 < args.approved_budget_usd <= MAX_BUDGET:
            parser.error(f"ask needs an attempt and explicit approved budget of at most ${MAX_BUDGET:g}")
        result = ask(args.bundle, args.attempt, args.approved_budget_usd)
    else:
        if not args.attempt:
            parser.error("evaluate needs an attempt")
        result = evaluate(args.bundle, args.attempt)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
