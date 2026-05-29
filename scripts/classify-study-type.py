#!/usr/bin/env python3
"""
classify-study-type.py — skim-then-punt study_type backfill.

LAYER 1 (this script, deterministic, no LLM):
  Maps PubMed pubtype field directly to controlled vocab when unambiguous.
  Writes /tmp/study-type-layer1.json with high-confidence answers.
  Everything else goes to /tmp/study-type-needs-haiku.json for LAYER 2.

Nothing is written to citations.csv. That's a separate commit step
gated on opus audit.

Usage:
    python3 classify-study-type.py <domain>
    # e.g.: python3 classify-study-type.py personal-health
"""
import csv
import json
import os
import re
import sys
from collections import Counter

KB = os.path.expanduser("~/Documents/GitHub/knowledge")
PUBMED_CACHE = os.path.join(KB, "scripts", "pubmed-lookup.json")


def load_pubmed():
    """Return DOI→record and PMID→record indexes from the cache."""
    if not os.path.exists(PUBMED_CACHE):
        return {}, {}
    cache = json.load(open(PUBMED_CACHE))
    pmid_to_rec = {}
    doi_to_rec = {}
    for k, v in cache.items():
        if not isinstance(v, dict) or "articleids" not in v:
            continue
        pmid_to_rec[k] = v
        for aid in v.get("articleids", []):
            if aid.get("idtype") == "doi":
                doi_to_rec[aid["value"].lower()] = v
    return doi_to_rec, pmid_to_rec


def classify_pubtype(pubtypes, journal):
    """
    Deterministic classification from PubMed pubtypes + journal.
    Returns (answer, confidence_reason) or (None, reason_for_punt).
    """
    if not pubtypes:
        return None, "no pubtype in PubMed cache"

    pts = {p.lower() for p in pubtypes}
    has = lambda needle: any(needle in p for p in pts)

    # Strongest signals first. Order matters: meta-analysis beats review,
    # case-reports beats everything, RCT beats review.
    if has("randomized controlled trial"):
        return "rct", "pubtype has 'Randomized Controlled Trial'"
    if has("meta-analysis"):
        return "meta-analysis", "pubtype has 'Meta-Analysis'"
    if has("systematic review"):
        return "systematic-review", "pubtype has 'Systematic Review'"
    if has("case reports"):
        return "case-report", "pubtype has 'Case Reports'"

    # Medical Hypotheses journal is hypothesis-proposal genre → map to review
    if journal and "medical hypotheses" in journal.lower():
        return "review", "journal is Medical Hypotheses"

    # "Review" on its own (no conflicting design tag) → review.
    # "Noise" pubtypes are administrative/meta tags that don't indicate design.
    # Use prefix matching because PubMed emits variants like
    # "Research Support, Non-U.S. Gov't", "Research Support, N.I.H., Extramural", etc.
    NOISE_PREFIXES = (
        "research support", "comparative study", "journal article",
        "english abstract", "review", "historical article",
        "letter", "editorial", "comment", "validation study",
        "multicenter study",
    )
    if has("review"):
        real_design = {p for p in pts if not any(p.startswith(n) for n in NOISE_PREFIXES)}
        if not real_design:
            return "review", "pubtype is 'Review' with no conflicting design tag"
        return None, f"'Review' mixed with {sorted(real_design)} — needs haiku"

    # Everything else is ambiguous at this layer.
    return None, f"pubtype {sorted(pts)} — no deterministic map"


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    domain = sys.argv[1]
    csv_path = os.path.join(KB, domain, "citations.csv")
    if not os.path.exists(csv_path):
        sys.exit(f"No CSV at {csv_path}")

    doi_to_rec, pmid_to_rec = load_pubmed()
    print(f"PubMed cache: {len(pmid_to_rec)} records, {len(doi_to_rec)} DOI-indexed", file=sys.stderr)

    rows = list(csv.DictReader(open(csv_path)))

    layer1_hits = []         # deterministic answers
    needs_haiku = []         # needs LLM pass
    no_pubmed_data = []      # no DOI or not in cache — deeper lookup needed

    # Target: rows currently classified as 'review' placeholder.
    # Also include rows with no study_type.
    targets = [r for r in rows if r["study_type"] in ("review", "")]

    for r in targets:
        doi = (r.get("doi") or "").lower().strip()
        rec = doi_to_rec.get(doi) if doi and doi != "not-found" else None

        if rec is None:
            no_pubmed_data.append({
                "key": r["key"],
                "doi": doi or "(missing)",
                "current_type": r["study_type"],
                "journal": r.get("journal", ""),
                "reason": "no DOI match in PubMed cache",
            })
            continue

        ans, reason = classify_pubtype(rec.get("pubtype", []), r.get("journal", ""))
        payload = {
            "key": r["key"],
            "doi": doi,
            "pmid": rec.get("uid"),
            "current_type": r["study_type"],
            "title": rec.get("title", ""),
            "pubtype": rec.get("pubtype", []),
            "journal": r.get("journal", ""),
            "reason": reason,
        }
        if ans:
            payload["new_type"] = ans
            layer1_hits.append(payload)
        else:
            needs_haiku.append(payload)

    # Write outputs — NOT the CSV.
    out_dir = "/tmp"
    with open(f"{out_dir}/study-type-layer1-{domain}.json", "w") as f:
        json.dump(layer1_hits, f, indent=2)
    with open(f"{out_dir}/study-type-needs-haiku-{domain}.json", "w") as f:
        json.dump(needs_haiku, f, indent=2)
    with open(f"{out_dir}/study-type-no-pubmed-{domain}.json", "w") as f:
        json.dump(no_pubmed_data, f, indent=2)

    # Report
    print(f"\n=== {domain} ===")
    print(f"Rows targeted (study_type in review/blank): {len(targets)}")
    print(f"  Layer 1 deterministic hits:  {len(layer1_hits):4d}  ({100*len(layer1_hits)//max(1,len(targets))}%)")
    print(f"  Need Layer 2 (haiku):        {len(needs_haiku):4d}  ({100*len(needs_haiku)//max(1,len(targets))}%)")
    print(f"  No PubMed data (deeper):     {len(no_pubmed_data):4d}  ({100*len(no_pubmed_data)//max(1,len(targets))}%)")

    if layer1_hits:
        print(f"\nLayer 1 breakdown by assigned type:")
        for t, n in Counter(h["new_type"] for h in layer1_hits).most_common():
            print(f"  {t:22s} {n}")


if __name__ == "__main__":
    main()
