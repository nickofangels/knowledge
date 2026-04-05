#!/bin/bash
# Auto-commit and push all knowledge sub-repos
# Runs daily via launchd

KNOWLEDGE_DIR="$HOME/Documents/GitHub/knowledge"
LOG="$KNOWLEDGE_DIR/scripts/auto-commit-push.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')

echo "=== Run: $TIMESTAMP ===" >> "$LOG"

for repo in "$KNOWLEDGE_DIR"/*/; do
    [ -d "$repo/.git" ] || continue

    name=$(basename "$repo")
    cd "$repo"

    # Skip if nothing changed
    if git diff --quiet HEAD 2>/dev/null && [ -z "$(git ls-files --others --exclude-standard)" ]; then
        echo "  $name: clean, skipped" >> "$LOG"
        continue
    fi

    git add -A
    git commit -m "auto: knowledge sync $TIMESTAMP" 2>> "$LOG"
    git push origin HEAD 2>> "$LOG"

    if [ $? -eq 0 ]; then
        echo "  $name: committed and pushed" >> "$LOG"
    else
        echo "  $name: push failed" >> "$LOG"
    fi
done

echo "" >> "$LOG"
