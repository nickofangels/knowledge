#!/usr/bin/env python3
"""Citation registry validator — checks CSV integrity.

Validates:
  - CSV is parseable
  - No duplicate keys
  - No duplicate DOIs (except placeholders)
  - study_type uses controlled vocabulary
  - confidence is high/medium/low
  - Required fields present
  - Keys are lowercase alphanumeric
"""

import csv
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Optional, List

ROOT = Path(__file__).resolve().parent.parent

VALID_STUDY_TYPES = {
    "rct", "meta-analysis", "systematic-review", "cohort", "case-control",
    "cross-sectional", "observational", "in-vitro", "ex-vivo", "animal",
    "case-report", "computational", "review",
}
VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_INDEPENDENCE = {"independent", "aligned", "indirect", "unknown"}
KEY_RE = re.compile(r"^[a-z][a-z0-9-]*\d{4}[a-z]?$")
REQUIRED_FIELDS = ["key", "confidence", "id", "doi", "author", "year", "journal", "study_type"]
DOI_PLACEHOLDERS = {"not found", "not-found", "unknown", ""}


def validate_domain(domain_path: Path) -> List[str]:
    """Validate a domain's citations.csv. Returns list of errors."""
    csv_path = domain_path / "citations.csv"
    errors = []

    if not csv_path.exists():
        return [f"{domain_path.name}: no citations.csv found"]

    # Parse CSV
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except csv.Error as e:
        return [f"{domain_path.name}: CSV parse error: {e}"]

    if not rows:
        return []  # Empty registry is valid

    domain = domain_path.name

    # Check required fields exist in header
    if rows:
        header = set(rows[0].keys())
        for field in REQUIRED_FIELDS:
            if field not in header:
                errors.append(f"{domain}: missing column '{field}' in CSV header")

    keys_seen = Counter()
    dois_seen = Counter()

    for i, row in enumerate(rows, start=2):  # Row 2 = first data row
        key = row.get("key", "").strip()
        doi = row.get("doi", "").strip()
        study_type = row.get("study_type", "").strip()
        confidence = row.get("confidence", "").strip()
        row_id = row.get("id", f"row {i}")

        # Key format
        if not key:
            errors.append(f"{domain} {row_id}: empty key")
        elif not KEY_RE.match(key):
            errors.append(f"{domain} {row_id}: invalid key format '{key}' (must be lowercase authorYEAR)")

        # Duplicates
        keys_seen[key] += 1
        if doi.lower() not in DOI_PLACEHOLDERS:
            dois_seen[doi] += 1

        # Study type
        if study_type and study_type not in VALID_STUDY_TYPES:
            errors.append(f"{domain} @{key}: invalid study_type '{study_type}' — use one of: {', '.join(sorted(VALID_STUDY_TYPES))}")

        # Confidence
        if confidence and confidence not in VALID_CONFIDENCE:
            errors.append(f"{domain} @{key}: invalid confidence '{confidence}' — use high/medium/low")

        # Funding independence
        independence = row.get("funding_independence", "").strip()
        if independence and independence not in VALID_INDEPENDENCE:
            errors.append(f"{domain} @{key}: invalid funding_independence '{independence}' — use {', '.join(sorted(VALID_INDEPENDENCE))}")

        # Required fields
        for field in REQUIRED_FIELDS:
            if not row.get(field, "").strip():
                errors.append(f"{domain} @{key}: empty required field '{field}'")

    # Duplicate checks
    for key, count in keys_seen.items():
        if count > 1 and key:
            errors.append(f"{domain}: duplicate key '@{key}' appears {count} times")
    for doi, count in dois_seen.items():
        if count > 1:
            errors.append(f"{domain}: duplicate DOI '{doi}' appears {count} times")

    return errors


if __name__ == "__main__":
    if len(sys.argv) > 1:
        domains = [ROOT / sys.argv[1]]
    else:
        domains = sorted(p.parent for p in ROOT.glob("*/citations.csv"))

    all_errors = []
    for d in domains:
        errors = validate_domain(d)
        all_errors.extend(errors)

    if all_errors:
        print(f"\n  VALIDATION FAILED — {len(all_errors)} error(s):\n")
        for e in all_errors:
            print(f"    {e}")
        print()
        sys.exit(1)
    else:
        checked = len(domains)
        print(f"\n  VALIDATION PASSED — {checked} domain(s) checked, no errors.\n")
