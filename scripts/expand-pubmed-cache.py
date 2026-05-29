#!/usr/bin/env python3
"""
expand-pubmed-cache.py — bulk-fetch PubMed metadata for every DOI in a domain's
citations.csv that isn't already in scripts/pubmed-lookup.json.

Writes ONLY to scripts/pubmed-lookup.json (cache). Never touches citations.csv.

Flow:
  1. Read all DOIs from the domain CSV.
  2. Drop DOIs already resolved (present in cache's DOI index).
  3. For each remaining DOI, call esearch with 'DOI[AID]' to get PMID.
  4. Batch PMIDs (200 at a time) into esummary. Merge into cache.

Usage:
    python3 expand-pubmed-cache.py <domain>
"""
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from collections import OrderedDict

KB = os.path.expanduser("~/Documents/GitHub/knowledge")
CACHE = os.path.join(KB, "scripts", "pubmed-lookup.json")
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
SLEEP = 0.34  # ~3 req/sec


def load_cache():
    if os.path.exists(CACHE):
        return json.load(open(CACHE))
    return {}


def save_cache(c):
    with open(CACHE, "w") as f:
        json.dump(c, f, indent=1)


def cached_dois(cache):
    out = set()
    for k, v in cache.items():
        if isinstance(v, dict):
            for a in v.get("articleids", []):
                if a.get("idtype") == "doi":
                    out.add(a["value"].lower())
    return out


def esearch_doi_to_pmid(doi):
    """Resolve a single DOI to a PMID via esearch. Returns None if not found."""
    q = urllib.parse.urlencode({
        "db": "pubmed",
        "term": f"{doi}[AID]",
        "retmode": "json",
        "retmax": 1,
    })
    try:
        with urllib.request.urlopen(f"{ESEARCH}?{q}", timeout=20) as r:
            data = json.load(r)
    except Exception as e:
        print(f"  esearch error for {doi}: {e}", file=sys.stderr)
        return None
    ids = data.get("esearchresult", {}).get("idlist", [])
    return ids[0] if ids else None


def esummary_batch(pmids):
    """Fetch esummary records for a list of PMIDs. Returns dict of pmid→record."""
    q = urllib.parse.urlencode({
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
    })
    try:
        with urllib.request.urlopen(f"{ESUMMARY}?{q}", timeout=60) as r:
            data = json.load(r)
    except Exception as e:
        print(f"  esummary error: {e}", file=sys.stderr)
        return {}
    result = data.get("result", {})
    out = {}
    for pmid in result.get("uids", []):
        out[pmid] = result[pmid]
    return out


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    domain = sys.argv[1]
    csv_path = os.path.join(KB, domain, "citations.csv")
    if not os.path.exists(csv_path):
        sys.exit(f"No CSV at {csv_path}")

    cache = load_cache()
    already = cached_dois(cache)
    print(f"Cache: {len(cache)} records, {len(already)} DOIs already resolved")

    rows = list(csv.DictReader(open(csv_path)))
    dois_all = []
    for r in rows:
        d = (r.get("doi") or "").lower().strip()
        if d and d != "not-found" and d not in already:
            dois_all.append((r["key"], d))

    # Deduplicate
    seen = set()
    dois = []
    for k, d in dois_all:
        if d not in seen:
            dois.append((k, d))
            seen.add(d)

    print(f"DOIs needing lookup: {len(dois)}")
    if not dois:
        print("Nothing to do.")
        return

    # Step 1: resolve DOIs → PMIDs (one at a time; NCBI esearch doesn't reliably
    # batch multi-DOI AID queries). Throttled.
    print("\nResolving DOIs → PMIDs...")
    doi_to_pmid = {}
    unresolved = []
    for i, (key, doi) in enumerate(dois, 1):
        pmid = esearch_doi_to_pmid(doi)
        if pmid:
            doi_to_pmid[doi] = pmid
        else:
            unresolved.append((key, doi))
        if i % 50 == 0:
            print(f"  {i}/{len(dois)} — resolved {len(doi_to_pmid)}, miss {len(unresolved)}")
        time.sleep(SLEEP)

    print(f"Total resolved: {len(doi_to_pmid)} / {len(dois)}")
    if unresolved:
        print(f"Unresolved DOIs ({len(unresolved)}): first 5 → {unresolved[:5]}")

    # Step 2: batch esummary
    pmids = list(doi_to_pmid.values())
    print(f"\nFetching esummary for {len(pmids)} PMIDs in batches of 200...")
    fetched = 0
    for i in range(0, len(pmids), 200):
        batch = pmids[i:i + 200]
        records = esummary_batch(batch)
        for pmid, rec in records.items():
            cache[pmid] = rec
        fetched += len(records)
        print(f"  batch {i//200 + 1}: got {len(records)} records (total fetched: {fetched})")
        time.sleep(SLEEP)

    save_cache(cache)
    print(f"\nDone. Cache now has {len(cache)} records.")


if __name__ == "__main__":
    main()
