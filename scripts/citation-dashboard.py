#!/usr/bin/env python3
"""Citation quality dashboard — reads citations.csv from one or all domains."""

import csv
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Optional, List, Dict

ROOT = Path(__file__).resolve().parent.parent


def load_registry(domain: Optional[str] = None) -> List[Dict]:
    """Load citations from one domain or all domains with a citations.csv."""
    rows = []
    if domain:
        paths = [ROOT / domain / "citations.csv"]
    else:
        paths = sorted(ROOT.glob("*/citations.csv"))
    for p in paths:
        if not p.exists():
            continue
        d = p.parent.name
        with open(p, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                row["domain"] = d
                rows.append(row)
    return rows


def funding_bucket(funding: str) -> str:
    """Classify funding into broad categories."""
    f = funding.lower().strip()
    if not f or f in ("not found", "unknown", "none listed"):
        return "not reported"
    if "paywalled" in f:
        return "paywalled"
    if any(k in f for k in ("nih", "nsf", "public health", "medical research council",
                            "mrc", "government", "danish", "nordic")):
        return "government/public"
    if any(k in f for k in ("foundation", "trust", "charity", "association")):
        return "nonprofit/foundation"
    if any(k in f for k in ("pharma", "pfizer", "novartis", "industry", "inc.", "ltd.")):
        return "industry"
    return "other/mixed"


def print_section(title: str, counts: Counter, total: int):
    print(f"\n  {title}")
    for item, n in counts.most_common():
        pct = n / total * 100
        bar = "█" * int(pct / 2.5)
        print(f"    {item:<30s} {n:>4d}  ({pct:5.1f}%)  {bar}")


def extract_surnames(author_field: str) -> List[str]:
    """Extract author surnames from a CSV author field."""
    surnames = []
    for part in author_field.split(","):
        part = part.strip()
        if not part:
            continue
        words = part.split()
        if words:
            name = words[0].rstrip(".")
            if len(name) > 2 and not name.isupper():
                surnames.append(name)
    return surnames


def extract_funders(funding_field: str) -> List[str]:
    """Extract individual funder names from a funding field."""
    f = funding_field.strip()
    if not f or f.lower() in ("not found", "not found (paywalled)", "unknown", "none listed"):
        return []
    # Split on semicolons (our convention) and clean up
    funders = []
    for part in f.split(";"):
        part = part.strip()
        # Remove grant numbers in parens
        cleaned = re.sub(r"\s*\([^)]*\)", "", part).strip()
        # Remove trailing grant IDs
        cleaned = re.sub(r"\s+[A-Z0-9]{5,}$", "", cleaned).strip()
        if cleaned and len(cleaned) > 3:
            funders.append(cleaned)
    return funders


def dashboard(rows: List[Dict]):
    if not rows:
        print("No citations found.")
        return

    total = len(rows)
    domains = set(r["domain"] for r in rows)
    print(f"\n{'='*60}")
    print(f"  CITATION QUALITY DASHBOARD")
    print(f"  {total} citations across {len(domains)} domain(s): {', '.join(sorted(domains))}")
    print(f"{'='*60}")

    # Study type breakdown
    study_types = Counter(r.get("study_type", "unknown").strip() or "unknown" for r in rows)
    print_section("STUDY TYPE", study_types, total)

    # Funding independence
    independence = Counter(r.get("funding_independence", "unknown").strip() or "unknown" for r in rows)
    print_section("FUNDING INDEPENDENCE", independence, total)

    # Funding source breakdown
    funding = Counter(funding_bucket(r.get("funding", "")) for r in rows)
    print_section("FUNDING SOURCE (auto-bucketed)", funding, total)

    # COI disclosure
    coi = Counter()
    for r in rows:
        c = r.get("coi", "").strip().lower()
        if not c or c in ("not found", "unknown"):
            coi["not found"] += 1
        elif "paywalled" in c:
            coi["paywalled"] += 1
        elif "predates" in c:
            coi["predates disclosure"] += 1
        elif "none" in c or "no " in c:
            coi["none declared"] += 1
        else:
            coi["disclosed"] += 1
    print_section("CONFLICT OF INTEREST", coi, total)

    # Credibility flags
    flagged = [r for r in rows if r.get("credibility_flags", "").strip()]
    if flagged:
        print(f"\n  CREDIBILITY FLAGS ({len(flagged)} paper(s)):")
        for r in flagged:
            print(f"    @{r['key']}: {r['credibility_flags']}")
    else:
        print(f"\n  CREDIBILITY FLAGS: none")

    # Journal distribution
    journals = Counter(r.get("journal", "unknown").strip() or "unknown" for r in rows)
    print_section("JOURNAL", journals, total)

    # Decade distribution
    decades = Counter()
    for r in rows:
        y = r.get("year", "").strip()
        if y.isdigit():
            decades[f"{int(y)//10*10}s"] += 1
        else:
            decades["unknown"] += 1
    print_section("PUBLICATION DECADE", decades, total)

    # Confidence distribution
    confidence = Counter(r.get("confidence", "unknown").strip() or "unknown" for r in rows)
    print_section("CONFIDENCE", confidence, total)

    # --- CONCENTRATION ANALYSIS ---
    print(f"\n  {'─'*56}")
    print(f"  CONCENTRATION ANALYSIS")
    print(f"  {'─'*56}")

    # Author frequency
    author_counts = Counter()
    for r in rows:
        for surname in extract_surnames(r.get("author", "")):
            author_counts[surname] += 1
    repeat_authors = [(name, n) for name, n in author_counts.most_common() if n >= 2]
    if repeat_authors:
        print(f"\n  AUTHORS APPEARING IN 2+ PAPERS:")
        for name, n in repeat_authors:
            pct = n / total * 100
            papers = [r["key"] for r in rows if name in extract_surnames(r.get("author", ""))]
            print(f"    {name:<25s} {n:>2d} papers ({pct:4.1f}%)  {', '.join(papers)}")
    else:
        print(f"\n  AUTHORS: no repeats detected")

    # Funder frequency
    funder_counts = Counter()
    for r in rows:
        for funder in extract_funders(r.get("funding", "")):
            funder_counts[funder] += 1
    repeat_funders = [(name, n) for name, n in funder_counts.most_common() if n >= 2]
    if repeat_funders:
        print(f"\n  FUNDERS APPEARING IN 2+ PAPERS:")
        for name, n in repeat_funders:
            print(f"    {name:<45s} {n:>2d} papers")
    else:
        print(f"\n  FUNDERS: no repeats detected")

    # DOI coverage
    has_doi = sum(1 for r in rows if r.get("doi", "").strip()
                  and not r["doi"].strip().lower().startswith("no-doi"))
    print(f"\n  DOI COVERAGE")
    print(f"    With DOI: {has_doi}/{total}  ({has_doi/total*100:.1f}%)")
    print(f"    Without:  {total - has_doi}/{total}")

    # Completeness: fields that are missing/unknown
    # credibility_flags excluded — empty means "clean", not "missing"
    fields = ["doi", "journal", "funding", "funding_independence", "coi", "sample"]
    print(f"\n  METADATA COMPLETENESS")
    missing_values = {"not found", "unknown", "none listed", ""}
    for field in fields:
        filled = 0
        paywalled = 0
        missing = 0
        for r in rows:
            val = r.get(field, "").strip().lower()
            if not val or val in missing_values:
                missing += 1
            elif "paywalled" in val:
                paywalled += 1
            else:
                filled += 1
        parts = [f"{filled}/{total} filled"]
        if paywalled:
            parts.append(f"{paywalled} paywalled")
        if missing:
            parts.append(f"{missing} missing")
        print(f"    {field:<25s}  {'  '.join(parts)}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    domain = sys.argv[1] if len(sys.argv) > 1 else None
    rows = load_registry(domain)
    dashboard(rows)
