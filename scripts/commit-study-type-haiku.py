#!/usr/bin/env python3
"""Commit Layer 2 (haiku) classifications to CSV.

Skips rows where haiku returned 'skip' — these are punted for later.
Safety: only touches rows still labeled as 'review' or blank.

Usage:
    python3 commit-study-type-haiku.py <domain> <haiku-output-path> [--apply]
"""
import csv
import json
import os
import shutil
import sys
from collections import Counter

KB = os.path.expanduser("~/Documents/GitHub/knowledge")


def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    domain = sys.argv[1]
    hpath = sys.argv[2]
    apply = "--apply" in sys.argv

    csv_path = os.path.join(KB, domain, "citations.csv")
    if not os.path.exists(csv_path):
        sys.exit(f"No CSV at {csv_path}")
    if not os.path.exists(hpath):
        sys.exit(f"No haiku output at {hpath}")

    hits = {h["key"]: h for h in json.load(open(hpath))}
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)

    changes = []
    skips = 0
    drift = 0
    for r in rows:
        h = hits.get(r["key"])
        if not h: continue
        if h["classification"] == "skip":
            skips += 1
            continue
        if r["study_type"] not in ("review", ""):
            drift += 1
            continue
        if r["study_type"] == h["classification"]:
            continue
        changes.append((r["key"], r["study_type"], h["classification"]))
        if apply:
            r["study_type"] = h["classification"]

    print(f"=== {domain} Layer 2 commit ===")
    print(f"Haiku entries:      {len(hits)}")
    print(f"  Classifications:  {len(changes)}")
    print(f"  Skipped by haiku: {skips}")
    print(f"  CSV drift skip:   {drift}")
    print(f"\nBreakdown:")
    for t, n in Counter(c[2] for c in changes).most_common():
        print(f"  → {t:22s} {n}")

    if not apply:
        print("\nDry-run. Re-run with --apply.")
        return

    shutil.copy2(csv_path, csv_path + ".bak")
    tmp = csv_path + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)
    os.replace(tmp, csv_path)
    print(f"\nApplied {len(changes)} changes.")


if __name__ == "__main__":
    main()
