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


SOURCE_TIER_MAP = {
    # S1: peer-reviewed (handled by citations.csv)
    'pubmed': 'S1', 'pmc': 'S1', 'doi': 'S1', 'nature': 'S1',
    'sciencedirect': 'S1', 'wiley': 'S1', 'springer': 'S1',
    'frontiers': 'S1', 'nih-other': 'S1', 'oxford': 'S1',
    'plos': 'S1', 'cell': 'S1', 'jci': 'S1', 'mdpi': 'S1',
    'aps': 'S1', 'aha': 'S1', 'acs': 'S1', 'pnas': 'S1',
    'sage': 'S1', 'taylor-francis': 'S1', 'karger': 'S1',
    'bmj': 'S1', 'nejm': 'S1', 'lancet': 'S1', 'jama': 'S1',
    'cochrane': 'S1', 'cell-physiol': 'S1',
    'academia': 'S1', 'researchgate': 'S1', 'preprint': 'S1',
    'semantic-scholar': 'S1',
    # S2: named expert / practitioner
    'practitioner': 'S2',
    # S3: patient organization
    'patient-org': 'S3',
    # S5: single anecdote (social media defaults to this; can be upgraded to S4 manually)
    'social-media': 'S5',
    'blog': 'S5',
    # S6: consumer health media
    'health-media': 'S6',
    # Other
    'science-media': 'S3',  # science journalism, better than health media
    'wikipedia': 'S3',
}


def source_tier(url_type: str) -> str:
    """Map URL type to source quality tier (S1-S6)."""
    return SOURCE_TIER_MAP.get(url_type, 'S5')  # Default to S5 for unknown


def generate_sources_section(report: Dict) -> str:
    """Generate a ## Sources section for a raw file from parsed Perplexity data."""
    lines = ["## Sources", ""]
    for src in report['sources']:
        num = src['num']
        tier = source_tier(src.get('url_type', 'other'))
        title = src.get('title', '')[:80]
        url = src.get('url', '')

        if tier == 'S1':
            # Academic — show DOI or PubMed link
            pmid = src.get('pmid', '')
            pmc_id = src.get('pmc_id', '')
            if pmid:
                lines.append(f"[{num}] {tier} pubmed:{pmid} — {title}")
            elif pmc_id:
                lines.append(f"[{num}] {tier} {pmc_id} — {title}")
            else:
                lines.append(f"[{num}] {tier} {url[:60]} — {title}")
        elif tier == 'S2':
            lines.append(f"[{num}] {tier} practitioner — {title} ({url[:60]})")
        elif tier == 'S3':
            lines.append(f"[{num}] {tier} org/media — {title} ({url[:60]})")
        elif tier in ('S4', 'S5'):
            lines.append(f"[{num}] {tier} {src.get('url_type', 'unknown')} — {title} ({url[:60]})")
        elif tier == 'S6':
            lines.append(f"[{num}] {tier} health-media — {title} ({url[:60]})")
        else:
            lines.append(f"[{num}] {tier} — {title} ({url[:60]})")

    # Summary
    tier_counts = Counter(source_tier(s.get('url_type', 'other')) for s in report['sources'])
    lines.append("")
    lines.append(f"<!-- Source quality: {', '.join(f'{t}={n}' for t, n in sorted(tier_counts.items()))} -->")
    return "\n".join(lines)


def single_file_mode(filepath: Path):
    """Parse a single Perplexity markdown and append a ## Sources section."""
    report = parse_file(filepath)

    if not report['sources']:
        print(f"No numbered sources found in {filepath.name}")
        return

    # Generate sources section
    sources_section = generate_sources_section(report)

    # Print summary
    tier_counts = Counter(source_tier(s.get('url_type', 'other')) for s in report['sources'])
    print(f"\n  {filepath.name}")
    print(f"  {report['source_count']} sources parsed")
    for tier in sorted(tier_counts):
        label = {'S1': 'peer-reviewed', 'S2': 'named-expert', 'S3': 'org/media',
                 'S4': 'anecdotal-pattern', 'S5': 'single-anecdote/social', 'S6': 'consumer-health'}
        print(f"    {tier} ({label.get(tier, 'unknown')}): {tier_counts[tier]}")

    # Check if file already has a ## Sources section
    text = filepath.read_text(encoding='utf-8', errors='replace')
    if '## Sources' in text:
        print(f"\n  ⚠ File already has a ## Sources section. Not overwriting.")
        print(f"  Generated section saved to stdout only.")
        print(f"\n{sources_section}")
    else:
        # Append to file
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(f"\n\n{sources_section}\n")
        print(f"\n  ✓ ## Sources section appended to {filepath.name}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Parse Perplexity deep research markdown exports')
    parser.add_argument('--single', type=str, help='Parse a single file and append ## Sources section')
    args = parser.parse_args()

    if args.single:
        single_file_mode(Path(args.single))
        sys.exit(0)

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
