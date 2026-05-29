#!/usr/bin/env python3
"""
verify-haiku-classifications.py — deterministic post-check on haiku output.

For each non-skip haiku classification, require explicit lexical evidence
in the abstract. If the evidence is absent, REJECT (convert to skip).

This catches haiku drift: cases where haiku matched a weak signal or
misattributed (e.g., 'double-blind' in a reference to a prior study).

Usage:
    python3 verify-haiku-classifications.py <haiku-output-path> <source-batch-path>
    # writes <haiku-output-path>.verified.json
"""
import json
import re
import sys

# For each classification, regex signals that MUST appear in the abstract
# (and optionally anti-signals that DISQUALIFY even if signals match).
RULES = {
    "rct": {
        "require": [r"\brandomi[sz]ed\b", r"\brandomly (assigned|allocated)\b",
                    r"\brandom allocation\b", r"\bdouble[- ]blind\b"],
        "exclude": [r"\bopen[- ]label\b", r"\bretrospective\b"],
    },
    "meta-analysis": {
        "require": [r"\bmeta[- ]analysis\b", r"\bpooled (analysis|estimate)\b"],
    },
    "systematic-review": {
        "require": [r"\bsystematic review\b", r"\bPRISMA\b",
                    r"\bsearched (databases|PubMed|MEDLINE|Cochrane)\b"],
    },
    "review": {
        "require": [r"\bthis review\b", r"\bwe review\b", r"\bin this review\b",
                    r"\bwe (summariz|discuss)\b", r"\bhere,? we (discuss|describe|summariz)\b",
                    r"\ba review of\b", r"\bevaluation and management\b",
                    r"\bcomprehensive (overview|review)\b", r"\bcurrent understanding\b"],
        # Reviews often don't have "we measured" sort of phrasing, but if
        # primary-data indicators are there, reject.
        "exclude": [r"\bwe enrolled\b", r"\bwe recruited\b",
                    r"\bparticipants were (randomized|randomised)\b"],
    },
    "cohort": {
        "require": [r"\bcohort\b", r"\bfollowed (for|up) (\d+|one|two|three)\b",
                    r"\bprospective (study|follow)\b", r"\bincidence (rate|over)\b",
                    r"\bobservational study\b"],
    },
    "case-control": {
        "require": [r"\bcase[- ]control\b"],
    },
    "cross-sectional": {
        "require": [r"\bcross[- ]sectional\b", r"\bpopulation[- ]based survey\b"],
    },
    "observational": {
        "require": [r"\bobservational\b", r"\bregistry\b", r"\bmedical records\b",
                    r"\bchart review\b"],
    },
    "case-report": {
        "require": [r"\bwe report (a case|the case)\b", r"\bcase series\b",
                    r"\bwe describe a patient\b", r"\bwe present (a case|\d+ cases)\b",
                    r"\ba case of\b", r"\bhere we present \d+ cases?\b"],
    },
    "animal": {
        "require": [r"\bmice\b", r"\brats?\b(?! of )", r"\bmurine\b", r"\brodent\b",
                    r"\bzebrafish\b", r"\bdrosophila\b", r"\brabbits?\b", r"\bpigs?\b",
                    r"\bC57BL/6\b", r"\bBALB/c\b", r"\bmouse model\b", r"\brat model\b",
                    r"\banimals were\b", r"\bwild[- ]type mice\b"],
        # If the abstract describes a cell-line study using cells DERIVED
        # from mice (e.g. mast cells "isolated from mice"), it may be
        # better classified in-vitro. For our purposes, animal is still
        # acceptable if species language is primary.
    },
    "in-vitro": {
        "require": [r"\bin vitro\b", r"\bcell culture\b", r"\bcultured cells\b",
                    r"\bcell line\b", r"\bHEK[- ]?293\b", r"\bRBL[- ]?2H3\b",
                    r"\bprimary (human|rat|mouse) \w+ cells\b",
                    r"\bisolated from (humans?|donors?|foreskin)\b",
                    r"\bfibroblasts?\b", r"\benzyme kinetics\b"],
        # In-vitro should NOT coexist with in vivo whole-organism signals.
        "exclude": [r"\bin vivo\b", r"\banimals were (given|injected|treated)\b",
                    r"\bwe administered\b"],
    },
    "ex-vivo": {
        "require": [r"\bex vivo\b", r"\bexplanted\b", r"\btissue (biopsy|biopsies|samples)\b",
                    r"\bisolated (tissue|tendons?|arteries|vessels)\b"],
    },
    "computational": {
        "require": [r"\bsimulation\b", r"\bbioinformatic\b", r"\bin silico\b",
                    r"\bmolecular dynamics\b", r"\bcomputational model\b",
                    r"\bmachine learning\b", r"\bneural network\b",
                    r"\b(we|our) model(ed|led)\b"],
    },
}

COMPILED = {}
for cls, rs in RULES.items():
    COMPILED[cls] = {
        "require": [re.compile(p, re.IGNORECASE) for p in rs.get("require", [])],
        "exclude": [re.compile(p, re.IGNORECASE) for p in rs.get("exclude", [])],
    }


def verify(cls, abstract, title):
    """Return (kept, reason). kept=False means downgrade to 'skip'."""
    if not abstract:
        return False, "no abstract to verify against"
    if cls not in COMPILED:
        return False, f"no rules for class {cls}"
    rules = COMPILED[cls]
    text = abstract + " " + (title or "")
    # Must match at least one require
    if not any(p.search(text) for p in rules["require"]):
        return False, "no required signal in abstract"
    # Must not match any exclude
    for p in rules["exclude"]:
        m = p.search(text)
        if m:
            return False, f"anti-signal matched: {m.group(0)}"
    return True, "signal present, no anti-signal"


def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    haiku_path = sys.argv[1]
    src_path = sys.argv[2]

    haiku_out = json.load(open(haiku_path))
    src = {c["key"]: c for c in json.load(open(src_path))}

    kept = 0
    rejected = 0
    skipped_by_haiku = 0
    rejections_by_class = {}
    verified = []

    for r in haiku_out:
        if r["classification"] == "skip":
            verified.append(r)
            skipped_by_haiku += 1
            continue
        abstract = src.get(r["key"], {}).get("abstract", "")
        title = src.get(r["key"], {}).get("title", "")
        ok, reason = verify(r["classification"], abstract, title)
        if ok:
            kept += 1
            verified.append(r)
        else:
            rejected += 1
            rejections_by_class[r["classification"]] = rejections_by_class.get(r["classification"], 0) + 1
            # Downgrade to skip with reason
            verified.append({
                "key": r["key"],
                "classification": "skip",
                "reasoning": f"REJECTED haiku's '{r['classification']}': {reason}",
                "original_haiku": r["classification"],
            })

    out_path = haiku_path.replace(".json", ".verified.json")
    with open(out_path, "w") as f:
        json.dump(verified, f, indent=2)

    print(f"Verified {haiku_path}")
    print(f"  Haiku's original skips: {skipped_by_haiku}")
    print(f"  Haiku classifications:  {kept + rejected}")
    print(f"    KEPT after verify:    {kept}")
    print(f"    REJECTED (→ skip):    {rejected}")
    if rejections_by_class:
        print(f"  Rejections by class:")
        for c, n in sorted(rejections_by_class.items(), key=lambda x: -x[1]):
            print(f"    {c:22s} {n}")
    print(f"  Output: {out_path}")


if __name__ == "__main__":
    main()
