#!/usr/bin/env python3
"""
classify-study-type-titles.py — Layer 1.5 deterministic title-keyword map.

Runs AFTER classify-study-type.py (Layer 1) has punted papers to the
"needs-haiku" queue. Tries to resolve more of them via unambiguous title
lexical signals BEFORE any LLM call.

Principle: only fire when a title signal is rigidly unambiguous
(e.g., "meta-analysis" in title → meta-analysis; no other interpretation).

Writes a new needs-haiku file with the residual, plus a title-hits file
for commit review.

Usage:
    python3 classify-study-type-titles.py <domain>
"""
import json
import os
import re
import sys
from collections import Counter

KB = os.path.expanduser("~/Documents/GitHub/knowledge")

# Ordered rules. First match wins. Patterns are case-insensitive.
# Each pattern must be RIGID — a false positive here is a silent CSV corruption.
TITLE_RULES = [
    # Explicit design names in title are near-ironclad signals.
    (r"\bmeta[-\s]?analysis\b", "meta-analysis"),
    (r"\bsystematic review\b", "systematic-review"),
    (r"\bumbrella review\b", "systematic-review"),
    (r"\bscoping review\b", "review"),
    (r"\bnarrative review\b", "review"),

    # RCT explicit
    (r"\brandomized (controlled )?(clinical )?trial\b", "rct"),
    (r"\brandomised (controlled )?(clinical )?trial\b", "rct"),
    (r"\bdouble[- ]blind\b.*\btrial\b", "rct"),
    (r"\bplacebo[- ]controlled\b.*\btrial\b", "rct"),

    # Case reports — allow "case report", "case series", "a case of"
    (r"\ba case of\b", "case-report"),
    (r"\bcase (report|series|reports)\b", "case-report"),
    (r"\btwo cases of\b", "case-report"),
    (r"\bthree cases of\b", "case-report"),
    (r"\bfour cases of\b", "case-report"),

    # Cohort
    (r"\bcohort study\b", "cohort"),
    (r"\bprospective cohort\b", "cohort"),
    (r"\bretrospective cohort\b", "cohort"),

    # Cross-sectional
    (r"\bcross[- ]sectional (study|survey|analysis)\b", "cross-sectional"),

    # Case-control
    (r"\bcase[- ]control (study|analysis)\b", "case-control"),

    # Animal (strict — title must explicitly name animal model)
    (r"\bin mice\b", "animal"),
    (r"\bin rats\b", "animal"),
    (r"\bin zebrafish\b", "animal"),
    (r"\bmouse model\b", "animal"),
    (r"\brat model\b", "animal"),
    (r"\bmurine model\b", "animal"),

    # In vitro / ex vivo explicit
    (r"\bin vitro\b", "in-vitro"),
    (r"\bex vivo\b", "ex-vivo"),
]

COMPILED = [(re.compile(p, re.IGNORECASE), t) for p, t in TITLE_RULES]


IN_VIVO_RE = re.compile(r"\bin vivo\b", re.IGNORECASE)


def classify_title(title):
    """Return (classification, matched_pattern) or (None, None).

    Conservative: skip mixed-methods titles where both 'in vitro' and 'in vivo'
    appear — punt to haiku instead.
    """
    if not title:
        return None, None
    for pat, t in COMPILED:
        if pat.search(title):
            # Guard: mixed in-vitro / in-vivo should not auto-classify as in-vitro.
            if t == "in-vitro" and IN_VIVO_RE.search(title):
                return None, None
            return t, pat.pattern
    return None, None


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    domain = sys.argv[1]
    needs_path = f"/tmp/study-type-needs-haiku-{domain}.json"
    if not os.path.exists(needs_path):
        sys.exit(f"No input at {needs_path} — run classify-study-type.py first")

    candidates = json.load(open(needs_path))
    title_hits = []
    residual = []

    for c in candidates:
        title = c.get("title", "")
        ans, pat = classify_title(title)
        if ans:
            c2 = dict(c)
            c2["new_type"] = ans
            c2["matched_pattern"] = pat
            title_hits.append(c2)
        else:
            residual.append(c)

    with open(f"/tmp/study-type-title-hits-{domain}.json", "w") as f:
        json.dump(title_hits, f, indent=2)
    with open(f"/tmp/study-type-needs-haiku-{domain}.json", "w") as f:
        json.dump(residual, f, indent=2)

    print(f"=== {domain} Layer 1.5 (title keywords) ===")
    print(f"Input:              {len(candidates)}")
    print(f"  Title-hits:       {len(title_hits)}  ({100*len(title_hits)//max(1,len(candidates))}%)")
    print(f"  Residual→haiku:   {len(residual)}")

    if title_hits:
        print(f"\nTitle-hits by type:")
        for t, n in Counter(h["new_type"] for h in title_hits).most_common():
            print(f"  {t:22s} {n}")


if __name__ == "__main__":
    main()
