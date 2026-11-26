#!/usr/bin/env python3
"""Run the agent on evals/messages.jsonl against the real model on Bedrock and score it.

    AWS_PROFILE=... AWS_DEFAULT_REGION=eu-central-1 python scripts/eval_agent.py [--show]

Checks per message: intent, language, every expected product + quantity, credit customer + amount,
and for unclear messages ("asks": true) that the reply asks a question. Costs a few cents (Haiku).
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))
from shop_agent import understand  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def same(a: str, b: str) -> bool:
    a, b = a.lower().strip(), b.lower().strip()
    return a == b or a.rstrip("s") == b.rstrip("s") or a in b or b in a


def check(case: dict, got) -> list[str]:
    errs = []
    if got.intent != case["intent"]:
        errs.append(f"intent {got.intent} != {case['intent']}")
    if got.language != case["language"]:
        errs.append(f"language {got.language} != {case['language']}")
    for product, qty in case.get("items", {}).items():
        hit = [i for i in got.items if same(i.product, product)]
        if not hit or hit[0].quantity != qty:
            errs.append(f"item {product}={qty} got {[(i.product, i.quantity) for i in got.items]}")
    if "customer" in case and not (got.customer and same(got.customer, case["customer"])):
        errs.append(f"customer {got.customer} != {case['customer']}")
    if "amount_mad" in case and got.amount_mad != case["amount_mad"]:
        errs.append(f"amount {got.amount_mad} != {case['amount_mad']}")
    if case.get("asks") and "?" not in got.reply:
        errs.append("should ask for the missing quantity")
    return errs


def main():
    cases = [json.loads(line) for line in open(os.path.join(ROOT, "evals", "messages.jsonl"), encoding="utf-8")]
    passed, t0 = 0, time.time()
    for case in cases:
        got = understand(case["text"])
        errs = check(case, got)
        passed += not errs
        mark = "PASS" if not errs else "FAIL"
        print(f"{mark}  {case['text']!r:45} -> {got.intent:8} {got.reply!r}" if "--show" in sys.argv or errs
              else f"{mark}  {case['text']!r}")
        for e in errs:
            print("        ", e)
    print(f"\n{passed}/{len(cases)} passed in {time.time() - t0:.0f} s")
    sys.exit(0 if passed == len(cases) else 1)


if __name__ == "__main__":
    main()
