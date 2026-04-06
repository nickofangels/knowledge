# Knowledge Base Repository

This repo is a collection of knowledge base domains. Each domain is a subdirectory at the root level.

## Structure

- Each subdirectory is a git submodule pointing to its own private repo.
- `master-index.md` — index of all domains (article counts, key topics).
- `scripts/` — shared utilities.
- `server.py` — local server.
- Sibling domains can read each other's `wiki/_index.md` but never write to each other.

## Creating a New Domain

New domains are private repos added as submodules.

1. Create a private repo on GitHub: `knowledge-<domain-name>`
2. Add as submodule: `git submodule add <repo-url> <domain-name>`
3. Create the required structure:
   ```
   <domain-name>/
   ├── CLAUDE.md                      # Domain instructions
   ├── evidence.md                    # Dated observations log
   ├── raw/                           # Source material
   ├── wiki/
   │   ├── _index.md                  # Table of contents
   │   ├── _processed.md              # Raw files already compiled
   │   └── _audit.md                  # Knowledge check output
   ├── outputs/                       # Deliverables (on request)
   └── .claude/
       └── procedures/
           ├── compile.md             # How to compile raw → wiki
           ├── deep-research.md       # How to run deep research
           └── knowledge-check.md     # How to audit the wiki
   ```
4. Adapt `CLAUDE.md` and procedures from an existing domain (e.g. `personal-health/`). Domain-specific sections (evidence tiers, source quality labels, prescriptive language examples) should be tailored to the new domain's subject matter.
5. The core rules carry across all domains:
   - `raw/` is source material, `wiki/` is compiled output
   - One concept per article, flat wiki directory
   - Describe what is known, never prescribe what to do
   - Compilation integrity: document what sources say, not what you infer
   - Never fabricate sources, never silently overwrite conflicting info

## Update Index

1. Read `*/wiki/_index.md` for all domain folders.
2. Write `master-index.md`: one section per domain with article count, link to its `_index.md`, and key topics listed.
3. Note emerging clusters: if a domain has several articles sharing a prefix or theme that isn't a subtopic of the domain's core subject, mention it as a candidate for its own domain. Don't prescribe — just surface the pattern.
4. Only write to `master-index.md`. Never write anywhere else.
5. Skip domains with no `wiki/_index.md`.

## Future Research

`future-research.md` — cross-domain questions and hypotheses to investigate. When the user identifies a new research question spanning domains, append it here as a bullet. Keep entries terse: bold label, one-line hypothesis, key unknowns.

## Submodule Workflow

Domains are git submodules pointing to private repos. This allows selective open-sourcing while keeping everything accessible from one clone.

- Clone: `git clone --recurse-submodules <url>`
- Pull: `git pull && git submodule update --remote --merge`
- New domain: create private repo, then `git submodule add <url> <domain-name>`
- Auto-commit script handles both layers (domain commits + parent pointer updates)
- Pointer conflicts (single-user repo): `git checkout --theirs <domain> && git add <domain>`

## Boundaries

**Always do (autonomous):** read any domain's `wiki/_index.md`, run compile/health-check within a domain, update `master-index.md`

**Ask first:** git push, creating a new domain/submodule, deleting wiki articles, modifying shared scripts

**Never do:** write to a sibling domain's files, delete a submodule, force-push any repo, commit secrets

## Misplaced Content

This top-level repo has no `raw/` or `wiki/`. If the user pastes research or article content here, do not process it. Ask which domain it belongs to, then direct them to open that domain's workspace so the content can be saved to `raw/` and compiled there.
