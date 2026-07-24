"""Run the evaluation and print a precision/recall report card.

Usage (from the repo root):
    python evals/run_eval.py                 # auto: LLM if OPENAI_API_KEY is set, else baseline
    python evals/run_eval.py --reviewer baseline
    python evals/run_eval.py --reviewer llm --tolerance 2
    python evals/run_eval.py --reviewer baseline --save   # record this run + show delta vs last

The "baseline" reviewer is a set of hard-coded regex rules (no ML) — it's a
yardstick. The "llm" reviewer is the real app reviewer (app/reviewer.py).
Comparing the two is the point: does the LLM beat dumb rules, and where?

Per-category metrics show WHERE a reviewer is strong or weak (e.g. great at
security, blind to correctness) — far more useful than one blended number.
--save records the run so you can track improvement across runs.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Make both the repo root (for `app`) and this folder (for dataset/harness) importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dataset  # noqa: E402
import harness  # noqa: E402

RESULTS_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "results"


async def findings_for(reviewer: str, diff: str) -> list[int]:
    """Return the line numbers a given reviewer flags for one diff."""
    if reviewer == "llm":
        from app.reviewer import review_pull_request

        review = await review_pull_request(diff, [])
        return [c.line for c in review.comments]
    return harness.baseline_review(diff)


def _fmt_row(label: str, tp: int, fp: int, fn: int) -> str:
    m = harness.metrics(tp, fp, fn)
    # recall is meaningless when there were no bugs to catch (clean cases)
    recall = "  n/a" if (tp + fn) == 0 else f"{m['recall']:>4.0%}"
    return f"{label:<16}{tp:>4}{fp:>4}{fn:>4}   {m['precision']:>4.0%}   {recall}"


async def run(reviewer: str, tolerance: int) -> dict:
    print(f"\nEvaluating reviewer = '{reviewer}'  (line-match tolerance = {tolerance})\n")
    header = f"{'case':<18}{'category':<15}{'bugs':>5}{'flagged':>9}{'TP':>4}{'FP':>4}{'FN':>4}"
    print(header)
    print("-" * len(header))

    tot = [0, 0, 0]  # tp, fp, fn
    by_cat: dict[str, list[int]] = {}
    for case in dataset.CASES:
        diff = harness.make_diff(case["filename"], case["code"])
        planted = harness.bug_lines(case)
        found = await findings_for(reviewer, diff)
        tp, fp, fn = harness.score_case(planted, found, tolerance)
        tot[0] += tp
        tot[1] += fp
        tot[2] += fn
        cat = by_cat.setdefault(case["category"], [0, 0, 0])
        cat[0] += tp
        cat[1] += fp
        cat[2] += fn
        print(
            f"{case['id']:<18}{case['category']:<15}{len(planted):>5}"
            f"{len(found):>9}{tp:>4}{fp:>4}{fn:>4}"
        )
    print("-" * len(header))

    # Per-category breakdown — where is the reviewer strong / weak?
    print("\nBy category:")
    print(f"{'category':<16}{'TP':>4}{'FP':>4}{'FN':>4}   {'prec':>5}  {'recall':>6}")
    print("-" * 44)
    for cat in sorted(by_cat):
        print(_fmt_row(cat, *by_cat[cat]))
    print("-" * 44)
    print(_fmt_row("OVERALL", *tot))

    m = harness.metrics(*tot)
    print(f"\nPrecision: {m['precision']:.0%}   (of what it flagged, how much was a real bug)")
    print(f"Recall:    {m['recall']:.0%}   (of the real bugs, how many it caught)")
    print(f"F1:        {m['f1']:.0%}   (balance of the two)\n")

    return {
        "reviewer": reviewer,
        "tolerance": tolerance,
        "overall": {"tp": tot[0], "fp": tot[1], "fn": tot[2], **m},
        "by_category": {
            c: {"tp": v[0], "fp": v[1], "fn": v[2], **harness.metrics(*v)}
            for c, v in by_cat.items()
        },
    }


def _compare_to_last(reviewer: str, current: dict) -> None:
    """If a previous run for this reviewer was saved, print the delta."""
    path = RESULTS_DIR / f"{reviewer}.json"
    if not path.exists():
        return
    prev = json.loads(path.read_text())["overall"]
    cur = current["overall"]
    print("Change vs last saved run:")
    for key in ("precision", "recall", "f1"):
        delta = cur[key] - prev[key]
        arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "=")
        print(f"  {key:<10} {prev[key]:.0%} -> {cur[key]:.0%}  {arrow} {delta:+.0%}")
    print()


def _save(reviewer: str, results: dict) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{reviewer}.json"
    path.write_text(json.dumps(results, indent=2))
    print(f"Saved results to {path.relative_to(Path.cwd())}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the code reviewer.")
    parser.add_argument("--reviewer", choices=["auto", "baseline", "llm"], default="auto")
    parser.add_argument("--tolerance", type=int, default=1)
    parser.add_argument("--save", action="store_true", help="record this run for cross-run comparison")
    args = parser.parse_args()

    reviewer = args.reviewer
    if reviewer == "auto":
        reviewer = "llm" if os.environ.get("OPENAI_API_KEY") else "baseline"
        if reviewer == "baseline":
            print("\n(No OPENAI_API_KEY found — running the rule-based baseline reviewer.")
            print(" Set OPENAI_API_KEY and pass --reviewer llm to evaluate the real model.)")

    results = asyncio.run(run(reviewer, args.tolerance))
    _compare_to_last(reviewer, results)  # show delta before overwriting
    if args.save:
        _save(reviewer, results)


if __name__ == "__main__":
    main()
