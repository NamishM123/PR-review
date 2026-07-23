"""The scoring engine: run a reviewer over the dataset, grade against the
answer key, and compute precision / recall.

Terms:
  - True Positive  (TP): reviewer flagged a line that IS a planted bug
  - False Positive (FP): reviewer flagged a line that is NOT a planted bug
  - False Negative (FN): a planted bug the reviewer MISSED

  precision = TP / (TP + FP)   "of what it flagged, how much was real"
  recall    = TP / (TP + FN)   "of the real bugs, how many it caught"

Matching is line-based with a small tolerance (a finding counts if it lands
within `tolerance` lines of a planted bug). This is the simple, automatic
approach; a fancier version would use an LLM-as-judge to match by meaning.
"""

import re


def make_diff(filename: str, code: str) -> str:
    """Render a code string as a unified diff that adds a new file."""
    lines = code.splitlines()
    n = len(lines)
    header = (
        f"diff --git a/{filename} b/{filename}\n"
        "new file mode 100644\n"
        "index 0000000..1111111\n"
        "--- /dev/null\n"
        f"+++ b/{filename}\n"
        f"@@ -0,0 +1,{n} @@\n"
    )
    body = "\n".join("+" + ln for ln in lines)
    return header + body + "\n"


def bug_lines(case: dict) -> list[int]:
    """Turn a case's answer key into 1-indexed line numbers (the ground truth).

    Each planted bug is located by the unique substring on its line, so line
    numbers are derived from the code and never drift.
    """
    lines = case["code"].splitlines()
    result = []
    for bug in case["bugs"]:
        for i, text in enumerate(lines, start=1):
            if bug["match"] in text:
                result.append(i)
                break
        else:
            raise ValueError(f"{case['id']}: bug marker {bug['match']!r} not found")
    return result


def added_lines(diff: str) -> list[tuple[int, str]]:
    """Parse a unified diff into (new_file_line_number, text) for each added line."""
    out: list[tuple[int, str]] = []
    new_ln = 0
    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            new_ln = int(m.group(1)) if m else 1
            continue
        if line.startswith("+"):
            out.append((new_ln, line[1:]))
            new_ln += 1
        elif line.startswith("-"):
            pass  # removed line: doesn't advance the new-file counter
        else:
            new_ln += 1  # context line
    return out


# --- Baseline reviewer: simple regex rules, NO ML. A yardstick for the LLM. ---
_RULES = [
    (re.compile(r"\bmd5\b|\bsha1\b", re.I), "weak hash"),
    (re.compile(r"\beval\(|\bexec\(", re.I), "dangerous eval/exec"),
    (re.compile(r"(api_key|secret|password|token)\s*=\s*['\"]", re.I), "hardcoded secret"),
    (re.compile(r"execute\(\s*f['\"]", re.I), "SQL injection (f-string)"),
    (re.compile(r"except\s*:", re.I), "bare except"),
]


def baseline_review(diff: str) -> list[int]:
    """Flag lines matching any hard-coded rule. Returns the flagged line numbers."""
    flagged = []
    for lineno, text in added_lines(diff):
        # open() without a context manager -> possible resource leak
        if "open(" in text and "with " not in text:
            flagged.append(lineno)
            continue
        for rule, _label in _RULES:
            if rule.search(text):
                flagged.append(lineno)
                break
    return flagged


def score_case(planted: list[int], found: list[int], tolerance: int = 1) -> tuple[int, int, int]:
    """Compare one case's findings to its answer key. Returns (TP, FP, FN)."""
    found = list(found)
    used = [False] * len(found)
    tp = 0
    for b in planted:
        for i, f in enumerate(found):
            if not used[i] and abs(f - b) <= tolerance:
                used[i] = True
                tp += 1
                break
    fn = len(planted) - tp
    fp = sum(1 for u in used if not u)
    return tp, fp, fn


def metrics(tp: int, fp: int, fn: int) -> dict:
    """Compute precision, recall, F1 from the tallies."""
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}
