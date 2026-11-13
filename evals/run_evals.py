"""Avaliação do agente contra um conjunto de casos de referência (golden set).

Uso:
    python -m evals.run_evals                 # modo offline (determinístico, roda no CI)
    python -m evals.run_evals --llm           # usa o Claude (requer ANTHROPIC_API_KEY)
    python -m evals.run_evals --min-score 0.9 # falha (exit 1) abaixo da meta
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.agent import build_agent
from app.schemas import AgentReply

GOLDEN_FILE = Path(__file__).parent / "golden.jsonl"


def check(case: dict, reply: AgentReply) -> list[str]:
    failures = []
    if reply.intent != case["intent"]:
        failures.append(f"intent={reply.intent} (esperado {case['intent']})")
    if "source" in case and not any(case["source"] in s for s in reply.sources):
        failures.append(f"fonte {case['source']!r} ausente em {reply.sources}")
    if case.get("handoff") and not reply.handed_off:
        failures.append("deveria transferir para humano")
    for term in case.get("must_contain", []):
        if term.lower() not in reply.answer.lower():
            failures.append(f"resposta sem {term!r}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true", help="avaliar no modo LLM")
    parser.add_argument("--min-score", type=float, default=0.9)
    args = parser.parse_args()

    agent = build_agent(use_llm=args.llm)
    cases = [json.loads(line) for line in GOLDEN_FILE.read_text("utf-8").splitlines() if line]

    passed = 0
    for case in cases:
        reply = agent.reply(case["input"])
        failures = check(case, reply)
        passed += not failures
        print(f"[{'PASS' if not failures else 'FAIL'}] {case['input']}")
        if failures:
            print(f"       -> {'; '.join(failures)}")

    score = passed / len(cases)
    print(f"\n{passed}/{len(cases)} casos aprovados ({score:.0%}) | meta: {args.min_score:.0%}")
    return 0 if score >= args.min_score else 1


if __name__ == "__main__":
    sys.exit(main())
