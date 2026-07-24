# Evaluation harness

A labeled benchmark for the code reviewer: measure how well it catches real
bugs, with numbers instead of vibes.

## What's here
- **`dataset.py`** — the labeled dataset. Small code files with **known planted
  bugs** (the "answer key" / ground truth) across `security`, `correctness`,
  and `error-handling`, plus a few **clean** files (to catch false positives).
  Each bug is located by a unique substring, so line numbers can't drift.
- **`harness.py`** — the scoring engine: builds diffs, runs a reviewer, and
  grades findings against the answer key into TP / FP / FN, then computes
  precision / recall / F1. Also contains a rule-based **baseline** reviewer.
- **`run_eval.py`** — runs it and prints the report card.

## Metrics
- **Precision** = TP / (TP + FP) — of what it flagged, how much was a real bug.
- **Recall** = TP / (TP + FN) — of the real bugs, how many it caught.
- **F1** — the balance of the two.

Reported **overall and per-category** (security / correctness / error-handling),
because a single blended number hides where a reviewer is strong or weak.

Matching is line-based with a small tolerance. A stronger version would use an
**LLM-as-judge** to match findings to bugs by meaning rather than line number.

## Tracking runs
`--save` records a run to `evals/results/<reviewer>.json`. On the next run the
report prints the **delta vs the last saved run** (precision/recall/F1 ▲▼), so
you can see whether a prompt tweak, model swap, or new technique actually helped.

## Run it
```bash
# rule-based baseline (no API key needed)
python evals/run_eval.py --reviewer baseline

# the real LLM reviewer (needs OPENAI_API_KEY)
OPENAI_API_KEY=sk-... python evals/run_eval.py --reviewer llm
```

## Baseline result (yardstick)
The regex baseline scores **100% precision / 60% recall**: it catches syntactic
issues (weak hash, hardcoded secret, SQL injection, `eval`, bare `except`,
resource leak) but misses every **semantic/correctness** bug (index error,
division-by-zero, off-by-one, mutable default) — because rules can't reason
about what the code *does*. That gap is exactly what the LLM reviewer should
close; run `--reviewer llm` to measure whether it does.
