# Knowledge Base Repository

This repo is a collection of knowledge base domains. Each domain is a subdirectory at the root level.

## Structure

- Each subdirectory is a standalone domain with its own `CLAUDE.md`, procedures, and content.
- `master/` is special — it maintains an index of all domains. See `master/CLAUDE.md`.
- Sibling domains can read each other's `wiki/_index.md` but never write to each other.

## Creating a New Domain

New domains are subdirectories of this repo, not separate repositories.

1. Create the directory: `knowledge/<domain-name>/`
2. Create the required structure:
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
3. Adapt `CLAUDE.md` and procedures from an existing domain (e.g. `personal-health/`). Domain-specific sections (evidence tiers, source quality labels, prescriptive language examples) should be tailored to the new domain's subject matter.
4. The core rules carry across all domains:
   - `raw/` is source material, `wiki/` is compiled output
   - One concept per article, flat wiki directory
   - Describe what is known, never prescribe what to do
   - Compilation integrity: document what sources say, not what you infer
   - Never fabricate sources, never silently overwrite conflicting info
