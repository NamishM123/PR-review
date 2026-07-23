"""Run the evaluation and print a precision/recall report card.

Usage (from the repo root):
    python evals/run_eval.py                 # auto: LLM if OPENAI_API_KEY is set, else baseline
    python evals/run_eval.py --reviewer baseline
    python evals/run_eval.py --reviewer llm --tolerance 2

The "baseline" reviewer is a set of hard-coded regex rules (no ML) — it's a
yardstick. The "llm" reviewer is the real app reviewer (app/reviewer.py).
Comparing the two is the point: does the LLM beat dumb rules, and where?
"""

import argparse
import asyncio
import os
import sys

# Make both the repo root (for `app`) and this folder (for dataset/harness) importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dataset  # noqa: E402
import harness  # noqa: E402


async def findings_for(reviewer: str, diff: str) -> list[int]:
    """Return the line numbers a given reviewer flags for one diff."""
    if reviewer == "llm":
        from app.reviewer import review_pull_request

        review = await review_pull_request(diff, [])
        return [c.line for c in review.comments]
    return harness.baseline_review(diff)


async def run(reviewer: str, tolerance: int) -> None:
    print(f"\nEvaluating reviewer = '{reviewer}'  (line-match tolerance = {tolerance})\n")
    header = f"{'case':<18}{'category':<15}{'bugs':>5}{'flagged':>9}{'TP':>4}{'FP':>4}{'FN':>4}"
    print(header)
    print("-" * len(header))

    tot_tp = tot_fp = tot_fn = 0
    for case in dataset.CASES:
        diff = harness.make_diff(case["filename"], case["code"])
        planted = harness.bug_lines(case)
        found = await findings_for(reviewer, diff)
        tp, fp, fn = harness.score_case(planted, found, tolerance)
        tot_tp += tp
        tot_fp += fp
        tot_fn += fn
        print(
            f"{case['id']:<18}{case['category']:<15}{len(planted):>5}"
            f"{len(found):>9}{tp:>4}{fp:>4}{fn:>4}"
        )

    m = harness.metrics(tot_tp, tot_fp, tot_fn)
    print("-" * len(header))
    print(f"\nTotals:  TP={tot_tp}  FP={tot_fp}  FN={tot_fn}")
    print(f"Precision: {m['precision']:.0%}   (of what it flagged, how much was a real bug)")
    print(f"Recall:    {m['recall']:.0%}   (of the real bugs, how many it caught)")
    print(f"F1:        {m['f1']:.0%}   (balance of the two)\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the code reviewer.")
    parser.add_argument("--reviewer", choices=["auto", "baseline", "llm"], default="auto")
    parser.add_argument("--tolerance", type=int, default=1)
    args = parser.parse_args()

    reviewer = args.reviewer
    if reviewer == "auto":
        reviewer = "llm" if os.environ.get("OPENAI_API_KEY") else "baseline"
        if reviewer == "baseline":
            print("\n(No OPENAI_API_KEY found — running the rule-based baseline reviewer.")
            print(" Set OPENAI_API_KEY and pass --reviewer llm to evaluate the real model.)")

    asyncio.run(run(reviewer, args.tolerance))


if __name__ == "__main__":
    main()
