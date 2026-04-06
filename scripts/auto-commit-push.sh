#!/bin/bash
# Auto-commit and push all knowledge sub-repos (submodules)
# Runs daily via launchd
# Handles two layers: commits inside each domain, then updates parent submodule pointers

KNOWLEDGE_DIR="$HOME/Documents/GitHub/knowledge"
LOG="$KNOWLEDGE_DIR/scripts/auto-commit-push.log"
ERROR_LOG="$KNOWLEDGE_DIR/scripts/auto-commit-push-error.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
PARENT_CHANGED=false

echo "=== Run: $TIMESTAMP ===" >> "$LOG"

# Ensure submodules are initialised and up to date
cd "$KNOWLEDGE_DIR"
git submodule update --init --recursive 2>> "$ERROR_LOG"

# Phase 1: Commit and push inside each domain submodule
for repo in "$KNOWLEDGE_DIR"/*/; do
    [ -e "$repo/.git" ] || continue

    name=$(basename "$repo")
    cd "$repo"

    # Skip if nothing changed
    if git diff --quiet HEAD 2>/dev/null && [ -z "$(git ls-files --others --exclude-standard)" ]; then
        echo "  $name: clean, skipped" >> "$LOG"
        continue
    fi

    git add -A
    git commit -m "auto: knowledge sync $TIMESTAMP" 2>> "$ERROR_LOG"
    git push origin HEAD 2>> "$ERROR_LOG"

    if [ $? -eq 0 ]; then
        echo "  $name: committed and pushed" >> "$LOG"
        PARENT_CHANGED=true
    else
        echo "  $name: push failed" >> "$ERROR_LOG"
    fi
done

# Phase 2: Update parent repo's submodule pointers
cd "$KNOWLEDGE_DIR"
if [ "$PARENT_CHANGED" = true ] || ! git diff --quiet 2>/dev/null; then
    git add -A
    git commit -m "auto: update submodule pointers $TIMESTAMP" 2>> "$ERROR_LOG"
    git push origin HEAD 2>> "$ERROR_LOG"

    if [ $? -eq 0 ]; then
        echo "  parent: submodule pointers updated and pushed" >> "$LOG"
    else
        echo "  parent: push failed" >> "$ERROR_LOG"
    fi
else
    echo "  parent: no pointer changes, skipped" >> "$LOG"
fi

echo "" >> "$LOG"
