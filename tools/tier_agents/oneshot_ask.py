#!/usr/bin/env python3
"""One request, one program, for GPT and Gemini: Kristján's `lightlag_live.oneshot ask`, other labs.

    python3 -m lightlag_traverse.oneshot request /tmp/request.md
    python3 tools/tier_agents/oneshot_ask.py /tmp/request.md <new-folder> --model gpt-6.1-sol
    python3 -m lightlag_traverse.oneshot play <new-folder> traverse-oneshot-gpt-6.1-sol-1 --label "GPT-6.1 Sol · one shot"

Same as Kristján's Claude version in every way that the APIs allow: the request text from
`lightlag_traverse.oneshot request` sent once as one user message, no retries, no fallback
model, and each tier asked the way Kristján asked his model of that tier
(docs/lightlag-runs/traverse-oneshot-*/meta.json): top as Opus 5.5 (effort medium, at most
100000 output tokens), middle as Sonnet 5.5 (medium, 64000), bottom as Haiku 5.5 (low, 64000).
Effort is OpenAI's `reasoning.effort` and Gemini's `thinkingLevel`. The folder gets the same four files (request.md, response.md, policy.py,
meta.json); the largest fenced python block is the program. `play` is Kristján's, unchanged.
Keys from the environment: OPENAI_API_KEY, GOOGLE_API_KEY. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# tier: (effort, max output tokens), copied from Kristján's Opus, Sonnet and Haiku one-request runs
TIER_SETTINGS = {"top": ("medium", 100000), "middle": ("medium", 64000), "bottom": ("low", 64000)}
TIERS = {"gpt-6.1-sol": "top", "gemini-4-carbon": "top", "gpt-6.1-terra": "middle", "gemini-4-argon": "middle",
         "gpt-6-luna": "bottom", "gemini-4-hydrogen": "bottom"}
# USD per 1M tokens (input, output); reasoning is billed as output. Read 15 November 2026 from
# https://developers.openai.com/api/docs/pricing and https://aistudio.google.com/docs/pricing.
PRICES = {
    "gpt-6-luna": (0.10, 0.50), "gpt-6.1-terra": (1.00, 5.00), "gpt-6.1-sol": (2.00, 10.00),
    "gemini-4-hydrogen": (1.50, 7.50), "gemini-4-argon": (2.00, 10.00), "gemini-4-carbon": (2.00, 10.00),
}


def post(url: str, headers: dict, body: dict) -> dict:
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"content-type": "application/json", **headers})
    with urllib.request.urlopen(request, timeout=3600) as response:
        return json.loads(response.read())


def ask_openai(model: str, prompt: str, effort: str, max_tokens: int) -> tuple[str, dict]:
    reply = post("https://api.openai.com/v1/responses", {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]},
                 {"model": model, "input": prompt, "reasoning": {"effort": effort}, "max_output_tokens": max_tokens})
    text = "".join(part.get("text", "") for item in reply.get("output", []) if item.get("type") == "message"
                   for part in item.get("content", []) if part.get("type") == "output_text")
    usage = reply.get("usage") or {}
    return text, {"served_model": reply.get("model"), "stop_reason": reply.get("status"),
                  "incomplete_details": reply.get("incomplete_details"), "message_id": reply.get("id"),
                  "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
                  "reasoning_tokens": (usage.get("output_tokens_details") or {}).get("reasoning_tokens")}


def ask_gemini(model: str, prompt: str, effort: str, max_tokens: int) -> tuple[str, dict]:
    reply = post("https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent".format(model),
                 {"x-goog-api-key": os.environ["GOOGLE_API_KEY"]},
                 {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                  "generationConfig": {"maxOutputTokens": max_tokens, "thinkingConfig": {"thinkingLevel": effort}}})
    candidate = (reply.get("candidates") or [{}])[0]
    text = "".join(part.get("text", "") for part in (candidate.get("content") or {}).get("parts", [])
                   if not part.get("thought"))
    usage = reply.get("usageMetadata") or {}
    thoughts = usage.get("thoughtsTokenCount") or 0
    return text, {"served_model": reply.get("modelVersion"), "stop_reason": candidate.get("finishReason"),
                  "message_id": reply.get("responseId"), "input_tokens": usage.get("promptTokenCount"),
                  "output_tokens": (usage.get("candidatesTokenCount") or 0) + thoughts, "reasoning_tokens": thoughts}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("request", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--model", required=True, choices=sorted(PRICES))
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=False)
    prompt = args.request.read_text(encoding="utf-8")
    (args.out / "request.md").write_text(prompt, encoding="utf-8")
    tier = TIERS[args.model]
    effort, max_tokens = TIER_SETTINGS[tier]
    meta = {"model": args.model, "tier": tier, "effort": effort, "max_tokens": max_tokens, "retries": 0, "fallback_model": None,
            "api": "OpenAI Responses API" if args.model.startswith("gpt") else "Gemini API generateContent"}
    started = time.time()
    try:
        text, info = (ask_openai if args.model.startswith("gpt") else ask_gemini)(args.model, prompt, effort, max_tokens)
    except urllib.error.HTTPError as error:
        meta["error"] = "api status {}: {}".format(error.code, error.read().decode(errors="replace")[:500])
    except (urllib.error.URLError, TimeoutError) as error:
        meta["error"] = "connection: {}".format(error)
    meta["seconds"] = round(time.time() - started, 1)
    if "error" in meta:
        (args.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
        print("{} failed: {}".format(args.out.name, meta["error"]))
        return 1
    (args.out / "response.md").write_text(text, encoding="utf-8")  # keep the paid reply before anything can fail
    blocks = re.findall(r"```python\n(.*?)```", text, flags=re.S)
    code = max(blocks, key=len) if blocks else ""
    (args.out / "policy.py").write_text(code, encoding="utf-8")
    price_in, price_out = PRICES[args.model]
    meta.update(info)
    meta.update({"cost_usd": round(((info["input_tokens"] or 0) * price_in + (info["output_tokens"] or 0) * price_out) / 1e6, 5),
                 "code_lines": code.count("\n"), "has_play": "def play(" in code})
    (args.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    print("{}: stop={} out={} tokens cost=${:.4f} {}s code_lines={} has_play={}".format(
        args.out.name, meta["stop_reason"], meta["output_tokens"], meta["cost_usd"], meta["seconds"],
        meta["code_lines"], meta["has_play"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
