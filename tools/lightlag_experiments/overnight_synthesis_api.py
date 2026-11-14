"""Root-only single paid response. Importing this file never loads credentials.

Offline tests inject a fake provider. The CLI alone constructs the real client,
after authorization, immutable-input checks, complete A/B accounting and an
exclusive attempt claim. No automatic retry or alternate response is supported.
"""

import argparse
import ast
from datetime import datetime, timezone
from decimal import Decimal
import importlib.metadata
import os
from pathlib import Path
import signal

try:
    from . import overnight_synthesis as common
except ImportError:  # direct CLI dispatch from the adjacent script
    import overnight_synthesis as common


def price_preflight(estimated_tokens, cumulative):
    if type(estimated_tokens) is not int or estimated_tokens < 0:
        raise common.GuardError("token count is missing or invalid")
    spent = Decimal(str(cumulative))
    if not spent.is_finite() or spent < 0 or spent >= 12 or spent + 1 > Decimal("15.70"):
        raise common.GuardError("existing launch guard or full dollar reservation would be exceeded")
    allowance = (5 * estimated_tokens + 3) // 4 + 1000
    cost = (Decimal(allowance) * 4 + Decimal(24000) * 20) / 1000000
    if cost > Decimal("0.90"):
        raise common.GuardError("conservative input plus full output allowance exceeds $0.90")
    return {"estimated_input_tokens": estimated_tokens, "allowed_input_tokens": allowance,
            "max_output_tokens": 24000, "maximum_calculated_usd": float(cost),
            "reservation_usd": 1.0, "cumulative_reported_usd_before_request": float(spent),
            "reservation_total_usd": float(spent + 1),
            "count_is_estimate": True, "prices_usd_per_million": {"input": 4, "output": 20}}


def reconciled_budget(base, repo):
    names = ("docs/lightlag-runs/overnight-a-summary.json", "docs/lightlag-runs/overnight-b-summary.json")
    a, b = (base.read_json(Path(repo) / name) for name in names)
    if a["n_completed"] != 9 or a["n_planned"] != 9 or len(a["runs"]) != 9:
        raise base.GuardError("Block A accounting is incomplete")
    if b["n_attempted"] != 12 or b["n_planned"] != 12 or b["n_pending"] != 0 or len(b["runs"]) != 12:
        raise base.GuardError("Block B must finish before synthesis")
    if b.get("stop_launches") or b.get("validation_issues") or b.get("stop_reasons"):
        raise base.GuardError("Block B declares unresolved issues or a launch stop")
    totals = []
    for block in (a, b):
        costs = []
        for row in block["runs"]:
            value = row.get("reported_cost_usd")
            if value is None or row.get("provider_error") or row.get("exception"):
                raise base.GuardError("prior provider error or unknown usage stops paid work")
            value = Decimal(str(value))
            if not value.is_finite() or value < 0:
                raise base.GuardError("invalid prior reported cost")
            costs.append(value)
        total = sum(costs, Decimal(0))
        if block.get("reported_cost_usd") is None or abs(total - Decimal(str(block["reported_cost_usd"]))) > Decimal("0.0000001"):
            raise base.GuardError("prior cost rows do not reconcile")
        totals.append(total)
    cumulative = sum(totals, Decimal(0))
    if b.get("cumulative_reported_cost_usd") is None or abs(cumulative - Decimal(str(b["cumulative_reported_cost_usd"]))) > Decimal("0.0000001"):
        raise base.GuardError("cumulative A/B accounting does not reconcile")
    price_preflight(0, cumulative)  # full reservation and stop guard before any endpoint
    return {"block_a_reported_usd": float(totals[0]), "block_b_reported_usd": float(totals[1]),
            "cumulative_reported_usd": float(cumulative), "account_balance_independently_verified": False,
            "source_sha256": {name: base.sha256((Path(repo) / name).read_bytes()) for name in names}}


def unrun_cells():
    return [{"profile": p, "seed": seed, "status": "unrun_synthesis_failed",
             "generated_reward": None, "kf_mpc_reward": None}
            for p in ("rush", "rush_noisy") for seed in range(60000, 60020)]


def safe_provider_error(error):
    # SDK exception text may contain request headers or local paths. Keep only
    # typed metadata; exact provider text/content is retained separately.
    return {"type": type(error).__name__, "status_code": getattr(error, "status_code", None),
            "request_id": getattr(error, "request_id", None),
            "message": "provider call failed; exception text intentionally omitted"}


def module_status(text, stop_reason):
    if stop_reason != "end_turn":
        return "response_incomplete", {"stop_reason": stop_reason}
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, MemoryError) as error:
        return "invalid_module", {"type": type(error).__name__, "line": getattr(error, "lineno", None)}
    plays = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "play"]
    if not plays:
        return "incompatible_module", {"message": "no top-level synchronous play function"}
    arguments = plays[-1].args
    positional = arguments.posonlyargs + arguments.args
    required = len(positional) - len(arguments.defaults)
    if not positional or required > 1 or any(value is None for value in arguments.kw_defaults):
        return "incompatible_module", {"message": "play cannot be called with one positional tools argument"}
    return "response_frozen", None


def usage_cost(message):
    usage = message.get("usage") or {}
    counts = [usage.get(name) for name in ("input_tokens", "output_tokens")]
    if any(type(value) is not int or value < 0 for value in counts):
        raise common.GuardError("actual input/output usage is missing")
    if any(usage.get(name) not in (0, None) for name in ("cache_creation_input_tokens", "cache_read_input_tokens")):
        raise common.GuardError("unexpected cache charges require separate price verification")
    if usage.get("service_tier") not in (None, "standard") or usage.get("speed") not in (None, "standard"):
        raise common.GuardError("unexpected provider pricing tier")
    if counts[1] > 24000:
        raise common.GuardError("provider output exceeded the declared allowance")
    return float((Decimal(counts[0]) * 4 + Decimal(counts[1]) * 20) / 1000000)


def perform_request(base, request, output, budget, client):
    """Exactly one count and at most one stream; fake-client tested offline."""
    output = Path(output)
    base.write_json(output / "request.json", request)
    base.write_json(output / "budget-before.json", budget)
    result = {"schema_version": 1, "status": "not_started", "evaluation_eligible": False,
              "request_sha256": base.sha256(base.canonical(request)),
              "provider_count_attempts": 0, "provider_message_attempts": 0,
              "calculated_provider_usage_cost_usd": None, "usage_unknown": False,
              "stream_terminal_received": False,
              "account_balance_independently_verified": False, "error": None,
              "max_retries": 0, "unrun_cells": unrun_cells()}
    phase = "count"
    try:
        count_request = {key: value for key, value in request.items()
                         if key in ("model", "system", "messages", "thinking", "output_config", "speed")}
        base.write_json(output / "count-request.json", count_request)
        result["provider_count_attempts"] = 1
        count = client.messages.count_tokens(**count_request)
        base.write_json(output / "token-count.json", {"body": count.model_dump(mode="json"),
                                                       "request_id": getattr(count, "_request_id", None)})
        phase = "budget"
        priced = price_preflight(count.input_tokens, budget["cumulative_reported_usd"])
        base.write_json(output / "cost-preflight.json", priced)
        phase = "generation"
        result["provider_message_attempts"] = 1
        # Persist the paid-start marker before the first streamed request; a killed
        # process must never be mistaken for zero usage or an unattempted response.
        base.write_json(output / "paid-request-started.json", {"started_at": datetime.now(timezone.utc).isoformat(),
                                                                "request_sha256": result["request_sha256"], "max_retries": 0})
        with (output / "stream-events.jsonl").open("xb") as events:
            with client.messages.stream(**request) as stream:
                result["provider_request_id"] = stream.request_id
                for event in stream:
                    payload = event.model_dump(mode="json")
                    events.write(base.canonical(payload))
                    events.flush()
                    if payload.get("type") == "message_stop":
                        result["stream_terminal_received"] = True
                if not result["stream_terminal_received"]:
                    try:
                        snapshot = stream.current_message_snapshot.model_dump(mode="json")
                    except (AttributeError, RuntimeError):
                        snapshot = None
                    if snapshot is not None:
                        base.write_json(output / "partial-response.json", snapshot)
                    raise base.GuardError("provider stream ended without its terminal event; final usage unknown")
                message = stream.get_final_message().model_dump(mode="json")
        base.write_json(output / "response.json", message)
        result["response_id"], result["response_model"] = message.get("id"), message.get("model")
        result["usage"] = message.get("usage")
        text = "".join(block["text"] for block in message.get("content", []) if block.get("type") == "text")
        with (output / "response-text.txt").open("x") as target:
            target.write(text)
        module = base.extract_module(text)
        with (output / "policy.py").open("x") as target:
            target.write(module)
        (output / "policy.py").chmod(0o444)
        result.update(response_text_sha256=base.sha256(text.encode()), policy_sha256=base.sha256(module.encode()),
                      extraction="single outer Markdown fence and terminal whitespace only")
        phase = "usage"
        if message.get("model") != request["model"]:
            raise base.GuardError("unexpected response model; no further paid work")
        result["calculated_provider_usage_cost_usd"] = usage_cost(message)
        phase = "module"
        if Decimal(str(result["calculated_provider_usage_cost_usd"])) > 1:
            result["status"], result["error"] = "actual_cost_overrun", {"message": "known provider usage exceeds the reserved dollar; stop paid work"}
        else:
            result["status"], result["error"] = module_status(module, message.get("stop_reason"))
        result["evaluation_eligible"] = result["status"] == "response_frozen"
        if result["evaluation_eligible"]:
            result["unrun_cells"] = []
    except BaseException as error:
        result["status"] = {"budget": "budget_preflight_failed", "usage": "usage_or_price_unverified",
                            "module": "module_validation_error"}.get(phase, "provider_error")
        result["error"] = safe_provider_error(error)
        result["usage_unknown"] = phase in ("generation", "usage")
        if phase == "usage":
            result["calculated_provider_usage_cost_usd"] = None
    result["artifact_sha256"] = {str(path.relative_to(output)): base.sha256(path.read_bytes())
                                 for path in sorted(output.rglob("*")) if path.is_file()}
    base.write_json(output / "synthesis.json", result)
    return result


def implementation_manifest(base):
    files = {"overnight_synthesis.py": Path(base.__file__), "overnight_synthesis_api.py": Path(__file__)}
    return {"implementation_sha256": {name: base.sha256(path.read_bytes()) for name, path in files.items()},
            "current_broker_is_used": True,
            "saved_preparer_is_provenance_only": True,
            "request_worker_and_simulator_remain_preparation_v1_bytes": True}


def make_client(api_key):
    """Construction alone makes no requests; tests supply an explicit fake key."""
    if "ANTHROPIC_CUSTOM_HEADERS" in os.environ:
        raise common.GuardError("custom provider header environment is forbidden; its value was not read")
    import anthropic
    import httpx2
    transport = httpx2.HTTPTransport(retries=0, trust_env=False)
    http = httpx2.Client(transport=transport, trust_env=False, timeout=600)
    return anthropic.Anthropic(api_key=api_key, webhook_key="", base_url="https://api.anthropic.com",
                               max_retries=0, http_client=http, timeout=600, open_telemetry=False)


def main(argv=None, *, base=common):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approved-request-sha256", required=True)
    parser.add_argument("--root-authorized-paid-call", action="store_true")
    args = parser.parse_args(argv)
    if not args.root_authorized_paid_call:
        parser.error("root authorization is required; no endpoint was called")
    if "ANTHROPIC_CUSTOM_HEADERS" in os.environ:
        raise base.GuardError("custom provider header environment is forbidden; its value was not read")
    manifest = base.read_json(args.preparation / "preparation.json")
    base.verify_preparation(args.preparation, manifest)
    base.verify_source(args.source_root, manifest["source_sha256"])
    base.verify_historical_inputs(args.repo, manifest)
    if not manifest["historical_gate_passed"] or not manifest["isolation_passed"]:
        raise base.GuardError("preparation gates did not pass")
    if manifest["source_commit"] != base.SOURCE_COMMIT or manifest["protocol_commit"] != base.PROTOCOL_COMMIT:
        raise base.GuardError("unexpected frozen protocol or simulator revision")
    request = base.read_json(args.preparation / "request.json")
    if args.approved_request_sha256 != manifest["request_sha256"] or base.sha256(base.canonical(request)) != args.approved_request_sha256:
        raise base.GuardError("request differs from the independently approved hash")
    if importlib.metadata.version("anthropic") != manifest["host_runtime"]["anthropic_sdk"]:
        raise base.GuardError("provider SDK changed after preparation")
    budget = reconciled_budget(base, args.repo)
    output = base.claim_output(args.output)
    # One permanent claim shared by all output destinations for this preparation.
    base.write_json(args.preparation.parent / "single-request-claim.json",
                    {"request_sha256": manifest["request_sha256"], "claimed_at": datetime.now(timezone.utc).isoformat(),
                     "one_attempt_only": True, "reservation_usd": 1.0})
    base.write_json(output / "implementation.json", implementation_manifest(base))
    base.write_json(output / "preparation-link.json", {"preparation_sha256": base.sha256((args.preparation / "preparation.json").read_bytes()),
                                                       "request_sha256": manifest["request_sha256"]})
    try:
        # This branch is root-only. Credentials are never put in arguments, files,
        # logs or containers. Disable environment proxy and alternate endpoints.
        key = os.environ["ANTHROPIC_API_KEY"]
        client = make_client(key)
        def stop(signum, frame):
            raise KeyboardInterrupt("root interrupted the one-shot request")
        signal.signal(signal.SIGTERM, stop)
        try:
            result = perform_request(base, request, output, budget, client)
        finally:
            client.close()
    except BaseException as error:
        if not (output / "synthesis.json").exists():
            base.write_json(output / "synthesis.json", {"status": "root_runtime_error", "evaluation_eligible": False,
                                                        "error": safe_provider_error(error), "unrun_cells": unrun_cells(),
                                                        "usage_unknown": (output / "paid-request-started.json").exists(),
                                                        "calculated_provider_usage_cost_usd": None})
        raise
    print(base.canonical({key: result.get(key) for key in ("status", "evaluation_eligible", "provider_request_id", "response_id",
                                                          "calculated_provider_usage_cost_usd", "usage_unknown")}).decode().strip())
    return 0 if result["evaluation_eligible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
