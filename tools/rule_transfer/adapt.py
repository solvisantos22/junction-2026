"""Two-response, $1-capped code adaptation diagnostic; never an agent benchmark.

Only the runner executes model code, in its isolated container. Public artifacts
exclude provider thinking blocks; exact API history stays in an explicit /tmp
directory. There are no retries and no fresh-seed evaluation in this module.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
from statistics import mean
import subprocess
import urllib.error
import urllib.request

from .runner import run_case

ROOT = Path(__file__).resolve().parents[2]
BASE_POLICY = ROOT / "docs/lightlag-runs/live-oneshot-opus-1/policy.py"
BASE_POLICY_HASH = "288279ff7a4fcc545df26526b4bb82fec33808a829494a6b356da8754831c6fe"
MODEL = "claude-opus-5-5"
MAX_OUTPUT = 16000
BUDGET_USD = 1.0
KINDS = ("none", "ground", "turning", "link", "relay")
SYSTEM = """Adapt the supplied Python autopilot to the published mission rules.
You have exactly two responses. First call evaluate_policy once with your complete
candidate; it is compiled and run on the fixed 20 practice missions. After its
feedback, call submit_policy once with your final program. No other tools exist.
For either tool provide exactly one of code (full Python source) or replacements
(ordered literal old/new edits). Each submission starts from the ORIGINAL source
in the prompt, not the practice candidate. Each old string must match exactly once
at that edit step. Keep a synchronous top-level play(tools) entry point. Python
standard library and NumPy are available in the networkless runner. A compile or
patch error is practice feedback; no person repairs your program. Your final
submission is frozen before any fresh evaluation. Do not provide your program in
plain text instead of the tool. Do not include private reasoning in tool fields.
"""
SUBMISSION_SCHEMA = {
    "type": "object", "properties": {
        "code": {"type": "string"},
        "replacements": {"type": "array", "items": {
            "type": "object", "properties": {"old": {"type": "string", "minLength": 1},
                                                "new": {"type": "string"}},
            "required": ["old", "new"], "additionalProperties": False}}},
    "oneOf": [{"required": ["code"]}, {"required": ["replacements"]}],
    "additionalProperties": False,
}
TOOLS = [{"name": name, "description": description, "input_schema": SUBMISSION_SCHEMA}
         for name, description in (
             ("evaluate_policy", "Compile and practice-test the first candidate on 20 fixed used missions."),
             ("submit_policy", "Compile and freeze the final candidate after practice feedback."))]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value, *, private=False):
    data = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if private:
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
            stream.write(data)
    else:
        Path(path).write_text(data, encoding="utf-8")


def load_key(env_file):
    values = []
    for line in Path(env_file).read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*(?:export\s+)?ANTHROPIC_API_KEY\s*=\s*(.*)$", line)
        if match:
            parts = shlex.split(match.group(1), comments=True)
            if len(parts) != 1 or not parts[0]:
                raise ValueError("ANTHROPIC_API_KEY must have one nonempty value")
            values.append(parts[0])
    if len(values) != 1:
        raise ValueError("explicit env file must define ANTHROPIC_API_KEY exactly once")
    return values[0]


def resolve_image(image):
    value = subprocess.check_output(["docker", "image", "inspect", image, "--format", "{{.Id}}"],
                                    text=True, timeout=15).strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise ValueError("Docker did not return an immutable image ID")
    return value


def prepare_material(prompt_file, image="junction-rule-adaptation-numpy", *, image_resolver=resolve_image):
    prompt_file = Path(prompt_file).resolve()
    base = BASE_POLICY.read_text(encoding="utf-8")
    prompt = prompt_file.read_text(encoding="utf-8")
    if digest(BASE_POLICY) != BASE_POLICY_HASH:
        raise ValueError("the frozen original policy changed")
    if prompt.count(base) != 1:
        raise ValueError("prompt must contain the full original policy exactly once")
    packages = ("lightlag", "lightlag_dynamic", "lightlag_controllers", "lightlag_shift", "lightlag_mcp")
    sources = [p for package in packages for p in (ROOT / package).rglob("*.py")]
    sources += [Path(__file__), Path(__file__).with_name("runner.py"), Path(__file__).with_name("worker.py")]
    dockerfile = Path(__file__).with_name("Dockerfile.adaptation")
    if dockerfile.exists():
        sources.append(dockerfile)
    protocol_file = ROOT / "docs/rule-transfer-results/adaptation-protocol.md"
    sources.extend([protocol_file, ROOT / "docs/rule-transfer.md"])
    protocol = {"schema": "rule-transfer-adaptation-v1", "model": MODEL, "effort": "medium",
                "thinking": "adaptive", "max_responses": 2, "max_output_tokens": MAX_OUTPUT,
                "budget_cap_usd": BUDGET_USD, "input_usd_per_million": 4,
                "output_usd_per_million": 20, "cache_requested": False,
                "input_reservation_multiplier": 1.1, "input_reservation_extra_tokens": 1024,
                "base_policy_sha256": digest(BASE_POLICY), "prompt_sha256": digest(prompt_file),
                "system_sha256": hashlib.sha256(SYSTEM.encode()).hexdigest(),
                "tools_sha256": hashlib.sha256(json.dumps(TOOLS, sort_keys=True).encode()).hexdigest(),
                "protocol_sha256": digest(protocol_file),
                "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "source_sha256": {str(p.relative_to(ROOT)): digest(p) for p in sorted(set(sources))},
                "docker_image_id": image_resolver(image),
                "practice_seeds": list(range(3200, 3204)), "practice_kinds": list(KINDS)}
    return {"protocol": protocol, "prompt": prompt, "base": base, "prompt_file": prompt_file}


def apply_submission(base, arguments):
    if not isinstance(arguments, dict) or set(arguments) not in ({"code"}, {"replacements"}):
        raise ValueError("provide exactly code or replacements")
    if "code" in arguments:
        code = arguments["code"]
        if not isinstance(code, str):
            raise ValueError("code must be a string")
    else:
        code = base
        if not isinstance(arguments["replacements"], list):
            raise ValueError("replacements must be an array")
        for index, edit in enumerate(arguments["replacements"]):
            if (not isinstance(edit, dict) or set(edit) != {"old", "new"}
                    or not isinstance(edit["old"], str) or not edit["old"]
                    or not isinstance(edit["new"], str)):
                raise ValueError("invalid replacement at index {}".format(index))
            count = code.count(edit["old"])
            if count != 1:
                raise ValueError("replacement {} matched {} times; exactly one required".format(index, count))
            code = code.replace(edit["old"], edit["new"], 1)
    tree = ast.parse(code, filename="candidate-policy.py")
    compile(tree, "candidate-policy.py", "exec")
    if not any(isinstance(node, ast.FunctionDef) and node.name == "play"
               and len(node.args.posonlyargs + node.args.args) >= 1 for node in tree.body):
        raise ValueError("program needs a synchronous top-level play(tools) function")
    return code


class ProviderError(Exception):
    def __init__(self, status=None, request_id=None, body=None):
        super().__init__("provider request failed")
        self.status, self.request_id, self.body = status, request_id, body


def call_provider(endpoint, payload, key):
    if endpoint not in ("/v1/messages", "/v1/messages/count_tokens"):
        raise ValueError("unsupported provider endpoint")
    request = urllib.request.Request("https://api.anthropic.com" + endpoint,
                                     data=json.dumps(payload, allow_nan=False).encode(),
                                     headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                              "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            return json.load(response), response.headers.get("request-id")
    except urllib.error.HTTPError as error:
        raise ProviderError(error.code, error.headers.get("request-id"),
                            error.read().decode(errors="replace")) from None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        raise ProviderError() from None


def usage_cost(usage):
    fields = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    for field in fields:
        value = usage.get(field, 0 if field.startswith("cache_") else None)
        if type(value) is not int or value < 0:
            raise ValueError("missing or invalid provider token usage")
    # No cache control is requested. If a provider nevertheless reports cache
    # writes, reserve their most expensive supported TTL ($8/MTok), not $4.
    return (4 * usage["input_tokens"] + 20 * usage["output_tokens"]
            + 8 * usage.get("cache_creation_input_tokens", 0)
            + .20 * usage.get("cache_read_input_tokens", 0)) / 1_000_000


def _check_pins(material):
    protocol = material["protocol"]
    if digest(BASE_POLICY) != protocol["base_policy_sha256"] or digest(material["prompt_file"]) != protocol["prompt_sha256"]:
        raise ValueError("policy or prompt changed during adaptation")
    if any(digest(ROOT / path) != expected for path, expected in protocol["source_sha256"].items()):
        raise ValueError("source changed during adaptation")


def _practice(policy, output, image, evaluator):
    rows = []
    for seed in range(3200, 3204):
        for kind in KINDS:
            directory = output / "practice" / "{}-{}".format(kind, seed)
            result = evaluator(policy, seed, kind, directory, image=image)
            evaluation = result["evaluation"]
            transcript = [json.loads(line) for line in (directory / "transcript.jsonl").read_text().splitlines()]
            rows.append({"case": len(rows) + 1, "status": result["status"],
                         "sampled_value": evaluation["sampled_value"], "raw_score": evaluation["raw_score"],
                         "normalized_score": evaluation["raw_score"] / evaluation["max_available_value"],
                         "alive": evaluation["alive"], "at_base": evaluation["at_base"],
                         "invalid_calls": [r for r in transcript if not r["ok"]],
                         "policy_errors": result.get("errors", []) if result["status"] == "policy_error" else []})
            if result["status"] not in ("returned", "invalid_calls", "policy_error"):
                raise RuntimeError("practice infrastructure or resource limit")
    return {"cases": rows, "overall": {
        "mean_normalized_score": mean(r["normalized_score"] for r in rows),
        "deaths": sum(not r["alive"] for r in rows),
        "alive_home": sum(r["alive"] and r["at_base"] for r in rows)}}


def _paths(output, private_runtime):
    output, private_runtime = Path(output).resolve(), Path(private_runtime).resolve()
    temporary = Path("/tmp").resolve()
    if (private_runtime == temporary or not private_runtime.is_relative_to(temporary)
            or private_runtime.is_relative_to(ROOT) or output.is_relative_to(private_runtime)
            or private_runtime.is_relative_to(output)):
        raise ValueError("private runtime must be a separate /tmp subdirectory outside the repository")
    for path in (output, private_runtime):
        if path.exists() and (not path.is_dir() or any(path.iterdir())):
            raise ValueError("output and private runtime must be new or empty directories")
    return output, private_runtime


def run(prompt_file, output, private_runtime, env_file, *, image="junction-rule-adaptation-numpy",
        provider=call_provider, evaluator=run_case, image_resolver=resolve_image, dry_run=False):
    output, private_runtime = _paths(output, private_runtime)
    material = prepare_material(prompt_file, image, image_resolver=image_resolver)
    key = load_key(env_file)
    report = {"protocol": material["protocol"], "status": "dry_run" if dry_run else "incomplete",
              "responses": [], "counts": [], "model_calls": 0, "total_reported_cost_usd": 0.0,
              "usage_unknown": False}
    if dry_run:
        return report
    output.mkdir(parents=True, exist_ok=True)
    private_runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    private_runtime.chmod(0o700)
    (output / "prompt.txt").write_text(material["prompt"], encoding="utf-8")
    write_json(output / "request-material.json", {"system": SYSTEM, "tools": TOOLS})
    messages = [{"role": "user", "content": material["prompt"]}]

    def checkpoint():
        write_json(output / "adaptation.json", report)

    def request(endpoint, payload, label):
        write_json(private_runtime / (label + "-request.json"), payload, private=True)
        try:
            body, request_id = provider(endpoint, payload, key)
        except ProviderError as error:
            write_json(private_runtime / (label + "-error.json"),
                       {"status": error.status, "request_id": error.request_id, "body": error.body}, private=True)
            report["provider_error"] = {"status": error.status, "request_id": error.request_id}
            raise
        write_json(private_runtime / (label + "-response.json"), body, private=True)
        return body, request_id

    checkpoint()
    stage = "prepare"
    try:
        for turn, expected in enumerate(("evaluate_policy", "submit_policy"), start=1):
            _check_pins(material)
            stage = "count_{}".format(turn)
            base_request = {"model": MODEL, "system": SYSTEM, "messages": messages,
                            "tools": TOOLS, "thinking": {"type": "adaptive"}}
            count, count_id = request("/v1/messages/count_tokens", base_request, stage)
            tokens = count.get("input_tokens")
            if type(tokens) is not int or tokens < 0:
                raise ValueError("invalid token count")
            reserved_input = math.ceil(tokens * 1.1) + 1024
            reserve = (reserved_input * 4 + MAX_OUTPUT * 20) / 1_000_000
            report["counts"].append({"turn": turn, "request_id": count_id, "input_tokens": tokens,
                                     "reserved_input_tokens": reserved_input, "reserved_cost_usd": reserve})
            if report["total_reported_cost_usd"] + reserve > BUDGET_USD:
                report["incomplete_reason"] = "budget_reservation_limit"
                break
            stage = "response_{}".format(turn)
            payload = dict(base_request, max_tokens=MAX_OUTPUT, output_config={"effort": "medium"},
                           tool_choice={"type": "auto", "disable_parallel_tool_use": True})
            report["model_calls"] += 1
            report["usage_unknown"] = True
            checkpoint()
            response, request_id = request("/v1/messages", payload, stage)
            usage = response.get("usage", {})
            public = {"turn": turn, "id": response.get("id"), "request_id": request_id,
                      "model": response.get("model"), "stop_reason": response.get("stop_reason"),
                      "usage": usage,
                      "content": [block for block in response.get("content", [])
                                  if block.get("type") in ("text", "tool_use")]}
            report["responses"].append(public)
            write_json(output / (stage + "-public.json"), public)
            checkpoint()
            cost = usage_cost(usage)
            public["reported_cost_usd"] = cost
            report["total_reported_cost_usd"] = round(report["total_reported_cost_usd"] + cost, 10)
            report["usage_unknown"] = False
            write_json(output / (stage + "-public.json"), public)
            checkpoint()
            if cost > reserve or report["total_reported_cost_usd"] > BUDGET_USD:
                raise ValueError("provider usage exceeded reservation")
            if response.get("model") != MODEL or response.get("stop_reason") != "tool_use":
                raise ValueError("unexpected model or stop reason; no retry")
            calls = [block for block in response.get("content", []) if block.get("type") == "tool_use"]
            if len(calls) != 1 or calls[0].get("name") != expected or not calls[0].get("id"):
                raise ValueError("unexpected tool sequence; no retry")
            stage = "submission_{}".format(turn)
            try:
                code = apply_submission(material["base"], calls[0].get("input"))
            except (ValueError, SyntaxError) as error:
                if turn == 2:
                    raise
                feedback = {"submission_error": str(error), "practice_executed": False}
            else:
                _check_pins(material)
                policy = output / ("candidate-policy.py" if turn == 1 else "final-policy.py")
                policy.write_text(code, encoding="utf-8")
                if turn == 1:
                    stage = "practice"
                    feedback = _practice(policy, output, material["protocol"]["docker_image_id"], evaluator)
                else:
                    _check_pins(material)
                    freeze = {"schema": "rule-transfer-adaptation-freeze-v1", "status": "complete",
                              "final_policy_sha256": digest(policy),
                              **{k: material["protocol"][k] for k in (
                                  "base_policy_sha256", "prompt_sha256", "source_sha256", "model",
                                  "effort", "thinking", "docker_image_id", "source_commit",
                                  "protocol_sha256", "system_sha256", "tools_sha256")},
                              "final_response_id": response.get("id"), "final_request_id": request_id,
                              "total_reported_cost_usd": report["total_reported_cost_usd"],
                              "fresh_check_opened": False, "final_practice_evaluated": False}
                    write_json(output / "freeze.json", freeze)
                    report.update(status="complete", final_policy_sha256=digest(policy),
                                  freeze_sha256=digest(output / "freeze.json"))
                    break
            feedback["next_step"] = "Call submit_policy with your final program; replacements start from ORIGINAL source."
            write_json(output / "practice-feedback.json", feedback)
            messages += [{"role": "assistant", "content": response["content"]},
                         {"role": "user", "content": [{"type": "tool_result", "tool_use_id": calls[0]["id"],
                                                        "content": json.dumps(feedback, allow_nan=False)}]}]
    except Exception as error:
        # Never copy exception text from a provider, key parser, or transport into
        # public logs. Full provider bodies, if available, are private only.
        report["incomplete_reason"] = stage + ":" + type(error).__name__
    checkpoint()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-runtime", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--image", default="junction-rule-adaptation-numpy")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        report = run(args.prompt_file, args.output, args.private_runtime, args.env_file,
                     image=args.image, dry_run=args.dry_run)
    except Exception as error:
        print(json.dumps({"status": "incomplete", "reason": "setup:" + type(error).__name__}))
        return 1
    print(json.dumps({"status": report["status"], "model_calls": report["model_calls"],
                      "reported_cost_usd": report["total_reported_cost_usd"],
                      "reason": report.get("incomplete_reason"), "output": str(args.output)}))
    return 0 if report["status"] in ("complete", "dry_run") else 1


if __name__ == "__main__":
    raise SystemExit(main())
