#!/usr/bin/env python3
"""Citation audit — detects @key and legacy [N] citations, cross-references registry.

Reports:
  - Linked (@key) vs legacy ([N]) citation counts per file
  - Broken links (@keys not in registry)
  - Medium-confidence markers
  - Orphaned registry entries (not referenced by any @key)
  - Metadata gaps
  - File coverage summary
"""

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional, List, Dict, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent

ATKEY_RE = re.compile(r"@([a-z][a-z0-9]*\d{4}[a-z]?)")
LEGACY_RE = re.compile(r"\[(\d+)\]")
MEDIUM_RE = re.compile(r"<!--\s*citation-confidence:\s*medium\s*-->")


def load_registry(domain_path: Path) -> List[Dict]:
    csv_path = domain_path / "citations.csv"
    if not csv_path.exists():
        return []
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def scan_file(filepath: Path) -> Dict:
    """Scan a markdown file for @key and [N] citations."""
    text = filepath.read_text(encoding="utf-8", errors="replace")

    atkeys = set(ATKEY_RE.findall(text))
    legacy_nums = set(LEGACY_RE.findall(text))
    medium_count = len(MEDIUM_RE.findall(text))

    return {
        "path": filepath,
        "atkeys": atkeys,
        "legacy_count": len(legacy_nums),
        "medium_count": medium_count,
    }


def audit_domain(domain_path: Path):
    domain = domain_path.name
    raw_dir = domain_path / "raw"
    wiki_dir = domain_path / "wiki"

    registry = load_registry(domain_path)
    reg_keys = {r.get("key", "").strip() for r in registry if r.get("key", "").strip()}

    # Scan all markdown files
    file_results = []
    all_atkeys_found = set()

    for d in [raw_dir, wiki_dir]:
        if not d.exists():
            continue
        for f in sorted(d.glob("*.md")):
            if f.name.startswith("_"):
                continue
            result = scan_file(f)
            file_results.append(result)
            all_atkeys_found.update(result["atkeys"])

    # Cross-reference
    broken_links = all_atkeys_found - reg_keys
    orphaned = [r for r in registry if r.get("key", "").strip() not in all_atkeys_found]

    # Confidence distribution
    confidence_counts = Counter(r.get("confidence", "unknown").strip() for r in registry)

    # Metadata gaps
    gap_fields = ["doi", "funding", "coi"]
    missing_values = {"not found", "not found (paywalled)", "unknown", ""}
    gaps = defaultdict(list)
    for row in registry:
        for field in gap_fields:
            val = row.get(field, "").strip().lower()
            if val in missing_values:
                gaps[field].append(row.get("key", row.get("id", "?")))

    # Totals
    total_linked = sum(len(r["atkeys"]) for r in file_results)
    total_legacy = sum(r["legacy_count"] for r in file_results)
    total_medium = sum(r["medium_count"] for r in file_results)

    # Print report
    print(f"\n{'='*60}")
    print(f"  CITATION AUDIT: {domain}")
    print(f"{'='*60}")

    print(f"\n  REGISTRY: {len(registry)} entries")
    print(f"  CONFIDENCE: ", end="")
    parts = []
    for level in ["high", "medium", "low"]:
        if confidence_counts[level]:
            parts.append(f"{confidence_counts[level]} {level}")
    print(", ".join(parts) if parts else "empty")

    print(f"\n  CITATIONS ACROSS ALL FILES:")
    print(f"    @key (linked):    {total_linked}")
    print(f"    [N] (legacy):     {total_legacy}")
    if total_medium:
        print(f"    Medium-conf:      {total_medium}")

    if broken_links:
        print(f"\n  BROKEN LINKS (@keys not in registry):")
        for key in sorted(broken_links):
            # Find which files reference this key
            files = [r["path"].name for r in file_results if key in r["atkeys"]]
            print(f"    @{key}  in {', '.join(files)}")

    if orphaned:
        print(f"\n  ORPHANED ({len(orphaned)} registry entries not @cited in any file):")
        for row in orphaned:
            print(f"    @{row.get('key', '?')} — {row.get('author', '?').split(',')[0]} {row.get('year', '?')}")

    if any(gaps.values()):
        print(f"\n  METADATA GAPS:")
        for field in gap_fields:
            if gaps[field]:
                print(f"    {field}: missing in {', '.join(gaps[field])}")

    # Per-file coverage
    raw_files = [r for r in file_results if "raw" in str(r["path"])]
    if raw_files:
        print(f"\n  RAW FILE COVERAGE:")
        for r in sorted(raw_files, key=lambda x: x["path"].name):
            name = r["path"].name
            linked = len(r["atkeys"])
            legacy = r["legacy_count"]
            if linked == 0 and legacy == 0:
                status = "no citations"
            elif linked == 0:
                status = f"legacy only ({legacy} [N])"
            elif legacy == 0:
                status = f"fully linked ({linked} @key)"
            else:
                status = f"{linked} @key, {legacy} [N] remaining"
            med = f"  [{r['medium_count']} medium]" if r["medium_count"] else ""
            print(f"    {name:<50s}  {status}{med}")

    wiki_files = [r for r in file_results if "wiki" in str(r["path"])]
    if wiki_files:
        wiki_linked = sum(len(r["atkeys"]) for r in wiki_files)
        wiki_legacy = sum(r["legacy_count"] for r in wiki_files)
        print(f"\n  WIKI FILES: {len(wiki_files)} files, {wiki_linked} @key, {wiki_legacy} [N]")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        domains = [ROOT / sys.argv[1]]
    else:
        domains = sorted(p.parent for p in ROOT.glob("*/raw"))
    for d in domains:
        if d.exists():
            audit_domain(d)
