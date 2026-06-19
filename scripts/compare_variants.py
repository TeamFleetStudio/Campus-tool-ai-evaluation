#!/usr/bin/env python3
"""Run multiple user_prompt variants against the same problem and compare scores."""

import json
import sys
import urllib.request
from pathlib import Path

API = "http://localhost:8000/v1/evaluate/direct"
DATA = Path(__file__).resolve().parent.parent / "data" / "variant_comparison.json"


def evaluate(problem: str, user_prompt: str) -> dict:
    payload = json.dumps({
        "problem_statement": problem,
        "user_prompt": user_prompt,
        "rubric_version": "v1",
    }).encode()
    req = urllib.request.Request(
        API,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def main() -> None:
    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)

    problem = data["problem_statement"]
    results = []

    print(f"Problem: {problem[:80]}...")
    print(f"Testing {len(data['variants'])} variants\n")
    print(f"{'Label':<12} {'Score':>8}  {'Tokens':>8}  Description")
    print("-" * 70)

    for v in data["variants"]:
        try:
            out = evaluate(problem, v["user_prompt"])
            score = out["total_score"]
            tokens = out["usage"]["total_tokens"]
            results.append((v["label"], score, tokens, v["description"]))
            print(f"{v['label']:<12} {score:>8.1f}  {tokens:>8}  {v['description']}")
        except Exception as e:
            print(f"{v['label']:<12} {'ERROR':>8}  {'—':>8}  {e}")

    if results:
        print("-" * 70)
        best = max(results, key=lambda x: x[1])
        worst = min(results, key=lambda x: x[1])
        print(f"\nBest:  {best[0]} ({best[1]}/100)")
        print(f"Worst: {worst[0]} ({worst[1]}/100)")
        print(f"Spread: {best[1] - worst[1]:.1f} points")


if __name__ == "__main__":
    main()
