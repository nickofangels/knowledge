#!/usr/bin/env python3
"""Parse Perplexity deep research markdown exports to extract numbered source references.

Extracts:
  - Source number (maps to [N] in the original raw file)
  - Title
  - URL
  - Domain (pubmed, pmc, doi.org, wikipedia, etc.)

Output: JSON file with all sources grouped by report title.
"""

import json
import re
import sys
from pathlib import Path
from collections import Counter
from typing import List, Dict, Optional

# Pattern: "N. [Title](URL) - Description..."
SOURCE_RE = re.compile(
    r'^(\d+)\.\s+\[([^\]]+)\]\((https?://[^\)]+)\)\s*-?\s*(.*)',
    re.MULTILINE
)

def classify_url(url: str) -> str:
    """Classify a URL by source type."""
    u = url.lower()
    if 'pubmed.ncbi.nlm.nih.gov' in u:
        return 'pubmed'
    if 'pmc.ncbi.nlm.nih.gov' in u:
        return 'pmc'
    if 'doi.org' in u:
        return 'doi'
    if 'nature.com' in u:
        return 'nature'
    if 'sciencedirect.com' in u:
        return 'sciencedirect'
    if 'wiley.com' in u or 'onlinelibrary' in u:
        return 'wiley'
    if 'springer.com' in u or 'link.springer' in u:
        return 'springer'
    if 'frontiersin.org' in u:
        return 'frontiers'
    if 'nih.gov' in u:
        return 'nih-other'
    if 'academic.oup.com' in u:
        return 'oxford'
    if 'journals.plos.org' in u:
        return 'plos'
    if 'cell.com' in u:
        return 'cell'
    if 'jci.org' in u:
        return 'jci'
    if 'mdpi.com' in u:
        return 'mdpi'
    # Additional academic publishers missed by initial patterns
    if 'journals.physiology.org' in u or 'physiology.org' in u:
        return 'aps'  # American Physiological Society
    if 'ahajournals.org' in u:
        return 'aha'  # American Heart Association
    if 'pubs.acs.org' in u:
        return 'acs'  # American Chemical Society
    if 'pnas.org' in u:
        return 'pnas'
    if 'journals.sagepub.com' in u or 'sagepub.com' in u:
        return 'sage'
    if 'tandfonline.com' in u:
        return 'taylor-francis'
    if 'karger.com' in u:
        return 'karger'
    if 'bmj.com' in u or 'gut.bmj.com' in u:
        return 'bmj'
    if 'nejm.org' in u:
        return 'nejm'
    if 'thelancet.com' in u:
        return 'lancet'
    if 'jama' in u and 'network' in u:
        return 'jama'
    if 'academia.edu' in u:
        return 'academia'  # preprints/papers
    if 'researchgate.net' in u:
        return 'researchgate'
    if 'biorxiv.org' in u or 'medrxiv.org' in u:
        return 'preprint'
    if 'cochrane' in u:
        return 'cochrane'
    if 'semanticscholar.com' in u:
        return 'semantic-scholar'
    if 'cellphysiolbiochem.com' in u:
        return 'cell-physiol'
    # Non-academic categories
    if 'wikipedia' in u:
        return 'wikipedia'
    if any(x in u for x in ['youtube.com', 'facebook.com', 'reddit.com', 'instagram.com', 'tiktok.com']):
        return 'social-media'
    if any(x in u for x in ['healthline.com', 'webmd.com', 'verywellhealth.com', 'medicalnewstoday.com',
                            'sleepfoundation.org', 'mayoclinic.org']):
        return 'health-media'
    if any(x in u for x in ['mastcell360.com', 'drhagmeyer.com', 'drbeckycampbell.com', 'droracle.ai',
                            'jeanniedibon.com', 'thefibroguy.com', 'painri.com']):
        return 'practitioner'
    if any(x in u for x in ['eds.clinic', 'rthm.com', 'ehlers-danlos.com', 'mastcellaction.org',
                            'ehlersdanlosnews.com', 'deficitdao.org']):
        return 'patient-org'
    if any(x in u for x in ['additudemag.com', 'neurodivergentinsights.com', 'adxs.org',
                            'geneticlifehacks.com', 'sciencedaily.com']):
        return 'science-media'
    if any(x in u for x in ['.blog', 'blog.', 'wordpress', 'medium.com', 'substack.com']):
        return 'blog'
    return 'other'


def is_academic(url_type: str) -> bool:
    """Is this an academic/peer-reviewed source?"""
    return url_type in {
        'pubmed', 'pmc', 'doi', 'nature', 'sciencedirect', 'wiley',
        'springer', 'frontiers', 'nih-other', 'oxford', 'plos', 'cell',
        'jci', 'mdpi', 'aps', 'aha', 'acs', 'pnas', 'sage',
        'taylor-francis', 'karger', 'bmj', 'nejm', 'lancet', 'jama',
        'academia', 'researchgate', 'preprint', 'cochrane',
        'semantic-scholar', 'cell-physiol'
    }


def extract_pubmed_id(url: str) -> Optional[str]:
    """Extract PubMed ID from a PubMed URL."""
    m = re.search(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', url)
    return m.group(1) if m else None


def extract_pmc_id(url: str) -> Optional[str]:
    """Extract PMC ID from a PMC URL."""
    m = re.search(r'PMC(\d+)', url)
    return f'PMC{m.group(1)}' if m else None


def parse_file(filepath: Path) -> Dict:
    """Parse a Perplexity markdown export and extract sources."""
    text = filepath.read_text(encoding='utf-8', errors='replace')

    # Extract title from first markdown heading
    title_match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else filepath.stem

    # Extract all numbered sources
    sources = []
    for match in SOURCE_RE.finditer(text):
        num = int(match.group(1))
        src_title = match.group(2).strip()
        url = match.group(3).strip()
        description = match.group(4).strip()[:200]  # Truncate description
        url_type = classify_url(url)

        source = {
            'num': num,
            'title': src_title,
            'url': url,
            'url_type': url_type,
            'academic': is_academic(url_type),
            'description': description,
        }

        # Extract IDs where possible
        pmid = extract_pubmed_id(url)
        if pmid:
            source['pmid'] = pmid
        pmc_id = extract_pmc_id(url)
        if pmc_id:
            source['pmc_id'] = pmc_id

        sources.append(source)

    return {
        'file': filepath.name,
        'title': title,
        'source_count': len(sources),
        'sources': sources,
    }


def print_summary(reports: List[Dict]):
    """Print summary statistics across all reports."""
    total_sources = sum(r['source_count'] for r in reports)
    all_sources = [s for r in reports for s in r['sources']]

    # URL type distribution
    url_types = Counter(s['url_type'] for s in all_sources)
    academic_count = sum(1 for s in all_sources if s['academic'])

    # Unique URLs
    unique_urls = set(s['url'] for s in all_sources)

    # Unique PubMed IDs
    pmids = set(s.get('pmid') for s in all_sources if s.get('pmid'))
    pmc_ids = set(s.get('pmc_id') for s in all_sources if s.get('pmc_id'))

    print(f"\n{'='*60}")
    print(f"  PERPLEXITY SOURCE ANALYSIS")
    print(f"  {len(reports)} reports, {total_sources} total source references")
    print(f"{'='*60}")

    print(f"\n  UNIQUE SOURCES: {len(unique_urls)}")
    print(f"  ACADEMIC: {academic_count} ({academic_count/total_sources*100:.0f}%)")
    print(f"  NON-ACADEMIC: {total_sources - academic_count} ({(total_sources-academic_count)/total_sources*100:.0f}%)")

    print(f"\n  IDENTIFIABLE IDs:")
    print(f"    PubMed IDs: {len(pmids)}")
    print(f"    PMC IDs: {len(pmc_ids)}")
    print(f"    Total resolvable: {len(pmids | pmc_ids)}")

    print(f"\n  SOURCE TYPE DISTRIBUTION:")
    for stype, count in url_types.most_common():
        pct = count / total_sources * 100
        bar = "█" * int(pct / 2)
        print(f"    {stype:<20s} {count:>4d}  ({pct:5.1f}%)  {bar}")

    print(f"\n  PER-REPORT BREAKDOWN:")
    for r in sorted(reports, key=lambda x: -x['source_count']):
        academic = sum(1 for s in r['sources'] if s['academic'])
        print(f"    {r['source_count']:>3d} sources ({academic:>3d} academic)  {r['title'][:60]}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    downloads = Path.home() / "Downloads"

    # Find Perplexity deep research exports (recent .md files with source patterns)
    perplexity_files = []
    for f in sorted(downloads.glob("*.md")):
        text = f.read_text(encoding='utf-8', errors='replace')
        # Check if it has the numbered source pattern
        if SOURCE_RE.search(text):
            perplexity_files.append(f)

    if not perplexity_files:
        print("No Perplexity markdown exports found in ~/Downloads/")
        sys.exit(1)

    reports = [parse_file(f) for f in perplexity_files]
    print_summary(reports)

    # Save full parsed data as JSON
    output_path = Path("/Users/nickdeangelo/Documents/GitHub/knowledge/scripts/perplexity-sources.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(reports, f, indent=2, ensure_ascii=False)
    print(f"Full source data saved to: {output_path}")
