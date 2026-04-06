---
description: Submodule coordination rules for the knowledge base
globs: [".gitmodules", "scripts/auto-commit-push.sh"]
---

- Submodules must be pushed before the parent repo to avoid broken pointers
- The auto-commit script handles both layers — do not manually push the parent without first pushing changed submodules
- When adding a new submodule, also remove the corresponding line from .gitignore if present
- Submodule URLs use HTTPS for consistency with existing remotes
