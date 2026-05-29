#!/usr/bin/env python3
"""
commit-study-type-layer1.py — apply Layer 1 deterministic study_type answers
to a domain's citations.csv.

Safety:
  - Only touches rows where current study_type matches the recorded
    current_type at the time classification ran.
  - Writes to a .bak sibling first, then atomic rename.
  - Produces a diff summary BEFORE writing — pass --apply to actually commit.

Usage:
    python3 commit-study-type-layer1.py <domain>             # dry-run
    python3 commit-study-type-layer1.py <domain> --apply     # write CSV
    python3 commit-study-type-layer1.py <domain> --source title-hits [--apply]
"""
import csv
import json
import os
import shutil
import sys

KB = os.path.expanduser("~/Documents/GitHub/knowledge")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    domain = sys.argv[1]
    apply = "--apply" in sys.argv
    source = "layer1"
    if "--source" in sys.argv:
        source = sys.argv[sys.argv.index("--source") + 1]

    csv_path = os.path.join(KB, domain, "citations.csv")
    layer1_path = f"/tmp/study-type-{source}-{domain}.json"
    if not os.path.exists(csv_path):
        sys.exit(f"No CSV at {csv_path}")
    if not os.path.exists(layer1_path):
        sys.exit(f"No output at {layer1_path} — run classify-study-type.py first")

    hits = {h["key"]: h for h in json.load(open(layer1_path))}
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)

    changes = []
    skipped = []
    for r in rows:
        h = hits.get(r["key"])
        if not h:
            continue
        # Safety: only touch if the CSV still matches the type at classification time
        if r["study_type"] != h["current_type"]:
            skipped.append((r["key"], r["study_type"], h["new_type"], "CSV changed since classification"))
            continue
        if r["study_type"] == h["new_type"]:
            # already correct, no-op
            continue
        changes.append((r["key"], r["study_type"], h["new_type"]))
        if apply:
            r["study_type"] = h["new_type"]

    print(f"=== {domain} Layer 1 commit ===")
    print(f"Planned changes:  {len(changes)}")
    print(f"Skipped (drift):  {len(skipped)}")

    # Breakdown by new type
    from collections import Counter
    print(f"\nBreakdown:")
    for t, n in Counter(c[2] for c in changes).most_common():
        print(f"  → {t:22s} {n}")

    if not apply:
        print("\nDry-run only. Re-run with --apply to write CSV.")
        return

    backup = csv_path + ".bak"
    shutil.copy2(csv_path, backup)
    print(f"\nBackup written: {backup}")

    tmp = csv_path + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, csv_path)
    print(f"CSV updated: {csv_path}")
    print(f"Applied {len(changes)} changes.")


if __name__ == "__main__":
    main()
