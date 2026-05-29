#!/usr/bin/env python3
"""Sources dashboard — black & white breakdown of citations.csv across domains.

Run: python3 sources-server.py
Open: http://localhost:8001
"""
import csv
import http.server
import json
import os
import re
from collections import Counter, defaultdict

PORT = 8001
KB_ROOT = os.path.expanduser("~/Documents/GitHub/knowledge")

# Source quality tier labels (S1-S6) from citation-registry procedure.
TIER_LABELS = {
    "S1": "peer-reviewed",
    "S2": "named-expert",
    "S3": "patient-org",
    "S4": "anecdotal-pattern",
    "S5": "single-anecdote",
    "S6": "consumer-health",
}

SOURCES_HEADER_RE = re.compile(r"^##\s+Sources\s*$", re.MULTILINE)
TIER_LINE_RE = re.compile(r"^\s*\[\d+\]\s+(S[1-6])\b", re.MULTILINE)


def list_domains():
    out = []
    for name in sorted(os.listdir(KB_ROOT)):
        path = os.path.join(KB_ROOT, name)
        if not os.path.isdir(path) or name.startswith("."):
            continue
        csv_path = os.path.join(path, "citations.csv")
        raw_dir = os.path.join(path, "raw")
        if os.path.exists(csv_path) or os.path.isdir(raw_dir):
            out.append((name, csv_path if os.path.exists(csv_path) else None, raw_dir if os.path.isdir(raw_dir) else None))
    return out


def read_csv(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def scan_raw_tiers(raw_dir):
    """Count S1-S6 tier mentions across raw files' ## Sources sections."""
    tier_counts = Counter()
    files_with_sources = 0
    if not raw_dir or not os.path.isdir(raw_dir):
        return tier_counts, files_with_sources, []
    per_file = []
    for name in sorted(os.listdir(raw_dir)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(raw_dir, name)
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        m = SOURCES_HEADER_RE.search(text)
        if not m:
            continue
        files_with_sources += 1
        section = text[m.end():]
        local = Counter(TIER_LINE_RE.findall(section))
        if local:
            tier_counts.update(local)
            per_file.append({"file": name, "tiers": dict(local)})
    return tier_counts, files_with_sources, per_file


def top_counter(values, n=10):
    c = Counter(v.strip() for v in values if v and v.strip())
    return c.most_common(n)


def domain_summary(name, csv_path, raw_dir):
    rows = read_csv(csv_path)
    total = len(rows)

    study_types = top_counter((r.get("study_type", "") for r in rows), 20)
    funding_indep = top_counter((r.get("funding_independence", "") for r in rows), 10)
    confidence = top_counter((r.get("confidence", "") for r in rows), 10)
    coi = top_counter((r.get("coi", "") for r in rows), 10)
    journals = top_counter((r.get("journal", "") for r in rows), 15)
    years = top_counter((r.get("year", "") for r in rows), 50)

    flagged = [r for r in rows if (r.get("credibility_flags") or "").strip()]
    flag_tokens = Counter()
    for r in flagged:
        for tok in re.split(r"[;,]", r.get("credibility_flags", "")):
            tok = tok.strip()
            if tok:
                flag_tokens[tok] += 1

    # Completeness / placeholder detection.
    def _blank(v):
        return (v or "").strip().lower() in ("", "not found", "not-found", "not found (paywalled)", "unknown", "tbd")

    missing_doi = sum(1 for r in rows if (r.get("doi") or "").strip() in ("", "not-found"))
    missing_funding = sum(1 for r in rows if _blank(r.get("funding")))
    missing_journal = sum(1 for r in rows if _blank(r.get("journal")))
    missing_coi = sum(1 for r in rows if _blank(r.get("coi")))
    missing_sample = sum(1 for r in rows if _blank(r.get("sample")))
    funding_unknown = sum(1 for r in rows if (r.get("funding_independence") or "").strip().lower() == "unknown")
    review_count = sum(1 for r in rows if (r.get("study_type") or "").strip().lower() == "review")
    confidence_high = sum(1 for r in rows if (r.get("confidence") or "").strip().lower() == "high")

    completeness = {
        "total": total,
        "missing_doi": missing_doi,
        "missing_journal": missing_journal,
        "missing_funding": missing_funding,
        "missing_coi": missing_coi,
        "missing_sample": missing_sample,
        "funding_independence_unknown": funding_unknown,
        "study_type_review": review_count,
        "confidence_high": confidence_high,
    }

    tier_counts, files_with_sources, per_file = scan_raw_tiers(raw_dir)

    raw_files = []
    if raw_dir and os.path.isdir(raw_dir):
        raw_files = [n for n in os.listdir(raw_dir) if n.endswith(".md")]

    return {
        "name": name,
        "total_papers": total,
        "study_types": study_types,
        "funding_independence": funding_indep,
        "confidence": confidence,
        "coi": coi,
        "journals": journals,
        "years": years,
        "flagged_count": len(flagged),
        "flag_tokens": flag_tokens.most_common(15),
        "missing_doi": missing_doi,
        "missing_funding": missing_funding,
        "tiers": {k: tier_counts.get(k, 0) for k in ["S1", "S2", "S3", "S4", "S5", "S6"]},
        "raw_files_total": len(raw_files),
        "raw_files_with_sources": files_with_sources,
        "per_file_tiers": per_file,
        "completeness": completeness,
    }


def build_summary():
    domains = []
    for name, csv_path, raw_dir in list_domains():
        domains.append(domain_summary(name, csv_path, raw_dir))
    return {"domains": domains, "tier_labels": TIER_LABELS}


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sources — Knowledge Base</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { background: #fff; color: #000; }
  body { font-family: 'SF Mono', 'Menlo', 'Consolas', monospace; padding: 32px 40px; max-width: 1100px; margin: 0 auto; font-size: 13px; line-height: 1.5; }
  h1 { font-size: 18px; font-weight: 700; letter-spacing: -0.2px; margin-bottom: 2px; }
  .sub { color: #000; font-size: 11px; opacity: 0.55; margin-bottom: 28px; }
  .domain { border: 1px solid #000; margin-bottom: 24px; }
  .domain-head { padding: 10px 14px; border-bottom: 1px solid #000; display: flex; justify-content: space-between; align-items: baseline; }
  .domain-name { font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
  .domain-total { font-size: 11px; opacity: 0.7; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0; }
  .card { padding: 12px 14px; border-top: 1px solid #000; }
  .card:nth-child(odd) { border-right: 1px solid #000; }
  .card-title { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; opacity: 0.8; }
  .row { display: flex; justify-content: space-between; padding: 2px 0; font-size: 12px; }
  .row .label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-right: 8px; }
  .row .count { font-variant-numeric: tabular-nums; font-weight: 600; flex-shrink: 0; }
  .bar-wrap { margin-top: 2px; margin-bottom: 6px; }
  .bar-row { display: grid; grid-template-columns: 120px 1fr 40px; gap: 8px; align-items: center; font-size: 12px; padding: 1px 0; }
  .bar-row .bar-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .bar { height: 10px; background: repeating-linear-gradient(90deg, #000 0, #000 2px, #fff 2px, #fff 4px); }
  .bar.solid { background: #000; }
  .bar-row .bar-count { text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }
  .tier { display: grid; grid-template-columns: 30px 130px 1fr 40px; gap: 8px; align-items: center; font-size: 12px; padding: 2px 0; }
  .tier .code { font-weight: 700; }
  .tier .desc { opacity: 0.7; font-size: 11px; }
  .meta { display: flex; gap: 16px; flex-wrap: wrap; font-size: 11px; padding: 8px 14px; border-top: 1px solid #000; background: #000; color: #fff; }
  .meta span b { font-weight: 700; }
  .flag-tag { display: inline-block; border: 1px solid #000; padding: 1px 6px; margin: 2px 4px 2px 0; font-size: 11px; }
  .empty { opacity: 0.4; font-size: 11px; font-style: italic; padding: 4px 0; }
  button { font-family: inherit; font-size: 11px; background: #fff; color: #000; border: 1px solid #000; padding: 6px 12px; cursor: pointer; letter-spacing: 0.5px; text-transform: uppercase; }
  button:hover { background: #000; color: #fff; }
  .topbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 28px; }
  .totals { display: flex; gap: 24px; padding: 12px 16px; border: 1px solid #000; margin-bottom: 24px; flex-wrap: wrap; }
  .totals .stat { display: flex; flex-direction: column; }
  .totals .stat .n { font-size: 20px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .totals .stat .l { font-size: 10px; text-transform: uppercase; letter-spacing: 1px; opacity: 0.7; }
  .tabs { display: flex; border-bottom: 1px solid #000; margin-bottom: 24px; gap: 0; }
  .tab { font-family: inherit; font-size: 11px; background: #fff; color: #000; border: 1px solid #000; border-bottom: none; padding: 10px 20px; cursor: pointer; letter-spacing: 1px; text-transform: uppercase; font-weight: 600; margin-right: -1px; margin-bottom: -1px; }
  .tab.active { background: #000; color: #fff; }
  .tab:hover:not(.active) { background: #000; color: #fff; }
  .pane { display: none; }
  .pane.active { display: block; }
  .overview-section { border: 1px solid #000; margin-bottom: 24px; }
  .overview-section > .card-title { padding: 10px 14px; margin: 0; border-bottom: 1px solid #000; opacity: 1; background: #000; color: #fff; }
  .overview-section > .body { padding: 12px 14px; }
  .domain-mini { display: grid; grid-template-columns: 200px 1fr 60px 60px; gap: 10px; padding: 4px 0; align-items: center; font-size: 12px; border-top: 1px dotted #000; }
  .domain-mini:first-child { border-top: none; }
  .domain-mini .dm-name { font-weight: 600; }
  .domain-mini .dm-count { text-align: right; font-variant-numeric: tabular-nums; }
  .domain-mini .dm-label { font-size: 10px; opacity: 0.6; text-transform: uppercase; }
  .warning { border: 2px solid #000; padding: 12px 14px; margin-bottom: 24px; }
  .warning .title { font-weight: 700; text-transform: uppercase; letter-spacing: 1px; font-size: 11px; margin-bottom: 6px; }
  .warning p { font-size: 12px; line-height: 1.6; }
  .comp-row { display: grid; grid-template-columns: 180px 1fr 90px 60px; gap: 8px; align-items: center; font-size: 12px; padding: 3px 0; }
  .comp-row .comp-label { font-size: 11px; }
  .comp-row .comp-pct { text-align: right; font-variant-numeric: tabular-nums; font-size: 11px; opacity: 0.7; }
  .comp-row .comp-count { text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }
  .comp-row .bar-track { height: 12px; background: #fff; border: 1px solid #000; position: relative; }
  .comp-row .bar-fill { height: 100%; background: #000; }
  .comp-row.bad .bar-fill { background: repeating-linear-gradient(45deg, #000 0, #000 3px, #fff 3px, #fff 6px); }
  .row.placeholder .label::after { content: ' (placeholder)'; opacity: 0.5; font-size: 10px; font-style: italic; }
  .bar-row.placeholder .bar-label::after { content: ' ⚠'; opacity: 0.6; }
  .bar-row.placeholder .bar { background: repeating-linear-gradient(45deg, #000 0, #000 3px, #fff 3px, #fff 6px) !important; }
</style>
</head>
<body>
<div class="topbar">
  <div>
    <h1>SOURCES DASHBOARD</h1>
    <div class="sub">citations.csv + raw/ ## Sources breakdown</div>
  </div>
  <button onclick="load()">Refresh</button>
</div>
<div class="tabs">
  <button class="tab active" data-pane="overview" onclick="showTab('overview')">Overview</button>
  <button class="tab" data-pane="bydomain" onclick="showTab('bydomain')">By Domain</button>
</div>
<div id="overview" class="pane active">Loading…</div>
<div id="bydomain" class="pane"></div>
<script>
function showTab(id) {
  document.querySelectorAll('.tab').forEach(function(t){ t.classList.toggle('active', t.dataset.pane === id); });
  document.querySelectorAll('.pane').forEach(function(p){ p.classList.toggle('active', p.id === id); });
}

function bar(label, count, max, solid) {
  var pct = max > 0 ? Math.round(100 * count / max) : 0;
  var cls = solid ? 'bar solid' : 'bar';
  return '<div class="bar-row"><div class="bar-label">' + esc(label) + '</div>'
    + '<div style="width:100%"><div class="' + cls + '" style="width:' + pct + '%"></div></div>'
    + '<div class="bar-count">' + count + '</div></div>';
}
function esc(s) { return String(s).replace(/[&<>]/g, function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];}); }

function section(title, pairs, opts) {
  opts = opts || {};
  var max = 0;
  for (var i = 0; i < pairs.length; i++) if (pairs[i][1] > max) max = pairs[i][1];
  var html = '<div class="card-title">' + title + '</div>';
  if (pairs.length === 0) return html + '<div class="empty">(none)</div>';
  html += '<div class="bar-wrap">';
  for (var i = 0; i < pairs.length; i++) {
    html += bar(pairs[i][0] || '(blank)', pairs[i][1], max, opts.solid);
  }
  html += '</div>';
  return html;
}

function renderDomain(d, tierLabels) {
  var h = '<div class="domain">';
  h += '<div class="domain-head"><div class="domain-name">' + esc(d.name) + '</div>'
    + '<div class="domain-total">' + d.total_papers + ' papers · ' + d.raw_files_total + ' raw files</div></div>';

  // tiers (S1-S6)
  var tierBars = '';
  var tierMax = 0;
  ['S1','S2','S3','S4','S5','S6'].forEach(function(k){ if (d.tiers[k] > tierMax) tierMax = d.tiers[k]; });
  ['S1','S2','S3','S4','S5','S6'].forEach(function(k){
    var n = d.tiers[k] || 0;
    var pct = tierMax > 0 ? Math.round(100 * n / tierMax) : 0;
    tierBars += '<div class="tier"><div class="code">' + k + '</div>'
      + '<div class="desc">' + tierLabels[k] + '</div>'
      + '<div style="width:100%"><div class="bar solid" style="width:' + pct + '%"></div></div>'
      + '<div class="bar-count">' + n + '</div></div>';
  });

  h += '<div class="card" style="border-top:1px solid #000">'
    + '<div class="card-title">Source Quality Tiers (raw/ ## Sources)</div>'
    + tierBars
    + '<div class="empty" style="margin-top:6px">' + d.raw_files_with_sources + ' of ' + d.raw_files_total + ' raw files have a ## Sources section</div>'
    + '</div>';

  // grid cards (use sectionMarked so placeholder values get hatched)
  h += '<div class="grid">';
  h += '<div class="card">' + sectionMarked('Study Type (papers)', d.study_types, {solid:true}) + '</div>';
  h += '<div class="card">' + sectionMarked('Funding Independence', d.funding_independence, {solid:true}) + '</div>';
  h += '<div class="card">' + sectionMarked('Identification Confidence', d.confidence, {solid:true}) + '</div>';
  h += '<div class="card">' + sectionMarked('COI Disclosure', d.coi, {solid:true}) + '</div>';
  h += '<div class="card">' + sectionMarked('Top Journals', d.journals.slice(0, 10), {solid:true}) + '</div>';
  h += '<div class="card">' + sectionMarked('Publication Years (top 15)', d.years.slice(0, 15), {solid:true}) + '</div>';
  h += '</div>';

  // flags + gaps
  h += '<div class="grid">';
  h += '<div class="card"><div class="card-title">Credibility Flags (' + d.flagged_count + ' papers flagged)</div>';
  if (d.flag_tokens.length === 0) h += '<div class="empty">(none)</div>';
  else {
    for (var i = 0; i < d.flag_tokens.length; i++) {
      h += '<span class="flag-tag">' + esc(d.flag_tokens[i][0]) + ' · ' + d.flag_tokens[i][1] + '</span>';
    }
  }
  h += '</div>';
  h += '<div class="card"><div class="card-title">Metadata Gaps</div>'
    + '<div class="row"><span class="label">Missing DOI</span><span class="count">' + d.missing_doi + '</span></div>'
    + '<div class="row"><span class="label">Missing Funding</span><span class="count">' + d.missing_funding + '</span></div>'
    + '</div>';
  h += '</div>';

  // footer summary
  var s1 = d.tiers.S1 || 0;
  var sketchy = (d.tiers.S5 || 0) + (d.tiers.S6 || 0);
  h += '<div class="meta">'
    + '<span><b>' + d.total_papers + '</b> papers in registry</span>'
    + '<span><b>' + s1 + '</b> S1 tagged in raw</span>'
    + '<span><b>' + sketchy + '</b> S5+S6 (sketchy)</span>'
    + '<span><b>' + d.flagged_count + '</b> flagged</span>'
    + '</div>';
  h += '</div>';
  return h;
}

function mergePairs(list) {
  // list of [[label,count],...] arrays from multiple domains. Merge by label.
  var map = {};
  list.forEach(function(pairs){
    pairs.forEach(function(p){
      var k = p[0] || '(blank)';
      map[k] = (map[k] || 0) + p[1];
    });
  });
  var out = Object.keys(map).map(function(k){ return [k, map[k]]; });
  out.sort(function(a,b){ return b[1] - a[1]; });
  return out;
}

// Values likely to be placeholders / missing-data defaults.
var PLACEHOLDERS = {
  'unknown': true, 'not found': true, 'not-found': true, 'not found (paywalled)': true,
  'tbd': true, '': true, '(blank)': true
};

function sectionMarked(title, pairs, opts) {
  opts = opts || {};
  var max = 0;
  for (var i = 0; i < pairs.length; i++) if (pairs[i][1] > max) max = pairs[i][1];
  var html = '<div class="card-title">' + title + '</div>';
  if (pairs.length === 0) return html + '<div class="empty">(none)</div>';
  html += '<div class="bar-wrap">';
  for (var i = 0; i < pairs.length; i++) {
    var label = pairs[i][0] || '(blank)';
    var count = pairs[i][1];
    var pct = max > 0 ? Math.round(100 * count / max) : 0;
    var isPh = PLACEHOLDERS[String(label).toLowerCase()];
    var cls = opts.solid ? 'bar solid' : 'bar';
    html += '<div class="bar-row' + (isPh ? ' placeholder' : '') + '">'
      + '<div class="bar-label">' + esc(label) + '</div>'
      + '<div style="width:100%"><div class="' + cls + '" style="width:' + pct + '%"></div></div>'
      + '<div class="bar-count">' + count + '</div></div>';
  }
  html += '</div>';
  return html;
}

function completenessRow(label, count, total, bad) {
  var pct = total > 0 ? Math.round(100 * count / total) : 0;
  var goodPct = 100 - pct;
  return '<div class="comp-row' + (bad ? ' bad' : '') + '">'
    + '<div class="comp-label">' + esc(label) + '</div>'
    + '<div class="bar-track"><div class="bar-fill" style="width:' + goodPct + '%"></div></div>'
    + '<div class="comp-pct">' + goodPct + '% filled</div>'
    + '<div class="comp-count">' + (total - count) + '/' + total + '</div></div>';
}

function renderOverview(data) {
  var active = data.domains.filter(function(d){ return d.total_papers > 0 || d.raw_files_total > 0; });

  // roll-up totals
  var totalPapers = 0, totalRaw = 0, totalWithSources = 0, totalFlagged = 0;
  var tierTotals = {S1:0,S2:0,S3:0,S4:0,S5:0,S6:0};
  var missingDoi = 0, missingFunding = 0;
  active.forEach(function(d){
    totalPapers += d.total_papers;
    totalRaw += d.raw_files_total;
    totalWithSources += d.raw_files_with_sources;
    totalFlagged += d.flagged_count;
    missingDoi += d.missing_doi;
    missingFunding += d.missing_funding;
    Object.keys(tierTotals).forEach(function(k){ tierTotals[k] += (d.tiers[k]||0); });
  });

  // Aggregated completeness
  var comp = {missing_doi:0, missing_journal:0, missing_funding:0, missing_coi:0, missing_sample:0, funding_independence_unknown:0, study_type_review:0, confidence_high:0, total:0};
  active.forEach(function(d){
    Object.keys(comp).forEach(function(k){ comp[k] += (d.completeness[k] || 0); });
  });

  var html = '';
  html += '<div class="totals">';
  html += '<div class="stat"><div class="n">' + totalPapers + '</div><div class="l">Papers total</div></div>';
  html += '<div class="stat"><div class="n">' + active.length + '</div><div class="l">Active domains</div></div>';
  html += '<div class="stat"><div class="n">' + data.domains.length + '</div><div class="l">All domains</div></div>';
  html += '<div class="stat"><div class="n">' + totalRaw + '</div><div class="l">Raw files</div></div>';
  html += '<div class="stat"><div class="n">' + totalWithSources + '</div><div class="l">With ## Sources</div></div>';
  html += '<div class="stat"><div class="n">' + totalFlagged + '</div><div class="l">Flagged</div></div>';
  html += '<div class="stat"><div class="n">' + (tierTotals.S5 + tierTotals.S6) + '</div><div class="l">S5+S6 sketchy</div></div>';
  html += '<div class="stat"><div class="n">' + missingDoi + '</div><div class="l">Missing DOI</div></div>';
  html += '</div>';

  // Warning / reading-notes panel
  html += '<div class="warning">'
    + '<div class="title">Reading the data — known caveats</div>'
    + '<p><b>S1–S6 tiers are empty</b> because only ' + totalWithSources + ' of ' + totalRaw + ' raw files have a <code>## Sources</code> section using the <code>[N] S#</code> format. The tier vocabulary was added after the registry backfill.</p>'
    + '<p><b>"review" dominates study_type</b> (' + comp.study_type_review + '/' + comp.total + ' = ' + Math.round(100*comp.study_type_review/comp.total) + '%). Some are genuine reviews, but many are placeholder defaults from backfill runs that could not resolve study design.</p>'
    + '<p><b>funding_independence "unknown" = ' + comp.funding_independence_unknown + '/' + comp.total + '</b> tracks rows where the <code>funding</code> field itself was blank — the tag is a consequence of missing upstream data, not an assessment.</p>'
    + '<p><b>confidence = "high" on 100%</b> is an artifact: only high-confidence matches were auto-imported. It does not indicate quality across the registry.</p>'
    + '</div>';

  // Data Completeness panel — the actual scoreboard
  html += '<div class="overview-section">'
    + '<div class="card-title">Data Completeness (filled vs placeholder)</div>'
    + '<div class="body">'
    + completenessRow('DOI', comp.missing_doi, comp.total, comp.missing_doi/comp.total > 0.2)
    + completenessRow('Journal', comp.missing_journal, comp.total, comp.missing_journal/comp.total > 0.2)
    + completenessRow('Funding source', comp.missing_funding, comp.total, comp.missing_funding/comp.total > 0.3)
    + completenessRow('COI disclosure', comp.missing_coi, comp.total, comp.missing_coi/comp.total > 0.3)
    + completenessRow('Sample description', comp.missing_sample, comp.total, comp.missing_sample/comp.total > 0.3)
    + completenessRow('Funding independence graded', comp.funding_independence_unknown, comp.total, comp.funding_independence_unknown/comp.total > 0.3)
    + completenessRow('Study type non-placeholder', comp.study_type_review, comp.total, comp.study_type_review/comp.total > 0.4)
    + '<div class="empty" style="margin-top:8px">Black fill = data present. Diagonal hatch = >20–40% placeholder/missing. Right number = missing/total.</div>'
    + '</div></div>';

  // papers per domain bar
  html += '<div class="overview-section">'
    + '<div class="card-title">Papers per Domain</div>'
    + '<div class="body">';
  var perDomainMax = 0;
  active.forEach(function(d){ if (d.total_papers > perDomainMax) perDomainMax = d.total_papers; });
  active.slice().sort(function(a,b){ return b.total_papers - a.total_papers; }).forEach(function(d){
    html += bar(d.name, d.total_papers, perDomainMax, true);
  });
  html += '</div></div>';

  // tier roll-up
  var tierMax = 0;
  Object.keys(tierTotals).forEach(function(k){ if (tierTotals[k] > tierMax) tierMax = tierTotals[k]; });
  var tierBars = '';
  ['S1','S2','S3','S4','S5','S6'].forEach(function(k){
    var n = tierTotals[k];
    var pct = tierMax > 0 ? Math.round(100 * n / tierMax) : 0;
    tierBars += '<div class="tier"><div class="code">' + k + '</div>'
      + '<div class="desc">' + data.tier_labels[k] + '</div>'
      + '<div style="width:100%"><div class="bar solid" style="width:' + pct + '%"></div></div>'
      + '<div class="bar-count">' + n + '</div></div>';
  });
  html += '<div class="overview-section">'
    + '<div class="card-title">Source Quality Tiers — all domains combined</div>'
    + '<div class="body">' + tierBars
    + '<div class="empty" style="margin-top:8px">' + totalWithSources + ' of ' + totalRaw + ' raw files have a ## Sources section</div>'
    + '</div></div>';

  // aggregated study types / funding / confidence / coi / journals / years
  var mergedStudy = mergePairs(active.map(function(d){ return d.study_types; }));
  var mergedFunding = mergePairs(active.map(function(d){ return d.funding_independence; }));
  var mergedConfidence = mergePairs(active.map(function(d){ return d.confidence; }));
  var mergedCoi = mergePairs(active.map(function(d){ return d.coi; }));
  var mergedJournals = mergePairs(active.map(function(d){ return d.journals; }));
  var mergedYears = mergePairs(active.map(function(d){ return d.years; }));
  var mergedFlags = mergePairs(active.map(function(d){ return d.flag_tokens; }));

  html += '<div class="overview-section"><div class="card-title">Aggregated Breakdowns — hatched = placeholder value</div>';
  html += '<div class="grid">';
  html += '<div class="card">' + sectionMarked('Study Type', mergedStudy.slice(0, 15), {solid:true}) + '</div>';
  html += '<div class="card">' + sectionMarked('Funding Independence', mergedFunding, {solid:true}) + '</div>';
  html += '<div class="card">' + sectionMarked('Identification Confidence', mergedConfidence, {solid:true}) + '</div>';
  html += '<div class="card">' + sectionMarked('COI Disclosure', mergedCoi.slice(0, 10), {solid:true}) + '</div>';
  html += '<div class="card">' + sectionMarked('Top Journals', mergedJournals.slice(0, 12), {solid:true}) + '</div>';
  html += '<div class="card">' + sectionMarked('Publication Years (top 15)', mergedYears.slice(0, 15), {solid:true}) + '</div>';
  html += '</div>';

  html += '<div class="grid">';
  html += '<div class="card"><div class="card-title">All Credibility Flags (' + totalFlagged + ' papers)</div>';
  if (mergedFlags.length === 0) html += '<div class="empty">(none)</div>';
  else {
    mergedFlags.slice(0, 25).forEach(function(f){
      html += '<span class="flag-tag">' + esc(f[0]) + ' · ' + f[1] + '</span>';
    });
  }
  html += '</div>';
  html += '<div class="card"><div class="card-title">Metadata Gaps (all domains)</div>'
    + '<div class="row"><span class="label">Missing DOI</span><span class="count">' + missingDoi + '</span></div>'
    + '<div class="row"><span class="label">Missing Funding</span><span class="count">' + missingFunding + '</span></div>'
    + '</div>';
  html += '</div>';
  html += '</div>';

  return html;
}

function renderByDomain(data) {
  var html = '';
  data.domains.forEach(function(d){
    if (d.total_papers === 0 && d.raw_files_total === 0) return;
    html += renderDomain(d, data.tier_labels);
  });
  return html;
}

function render(data) {
  document.getElementById('overview').innerHTML = renderOverview(data);
  document.getElementById('bydomain').innerHTML = renderByDomain(data);
}

function load() {
  document.getElementById('overview').textContent = 'Loading…';
  fetch('/api/summary').then(function(r){ return r.json(); }).then(render).catch(function(e){
    document.getElementById('overview').innerHTML = '<div class="empty">Error: ' + e + '</div>';
  });
}
load();
</script>
</body>
</html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/summary":
            data = build_summary()
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    print(f"Sources dashboard: http://localhost:{PORT}")
    http.server.HTTPServer(("", PORT), Handler).serve_forever()
