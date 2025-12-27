#!/bin/bash

# Configuration
API_URL="http://localhost:8000/api/scan"
GOLDEN_REPOS_FILE="backend/rules/golden_repos.json"

# Check if file exists
if [ ! -f "$GOLDEN_REPOS_FILE" ]; then
    echo "Error: $GOLDEN_REPOS_FILE not found"
    exit 1
fi

# Extract URLs from JSON (requires no external dependencies, simple grep/sed/tr)
# We want to extract lines that look like "https://github.com/..."
REPOS=$(grep "https://" "$GOLDEN_REPOS_FILE" | sed 's/.*"\(https:[^"]*\)".*/\1/')

echo "Triggering scans for golden repositories..."

for REPO in $REPOS; do
    echo "Processing: $REPO"
    curl -s -X POST "$API_URL" \
         -H "Content-Type: application/json" \
         -d "{\"repo_url\": \"$REPO\", \"branch\": \"main\", \"scan_type\": \"static\"}" | grep -q "id"
    
    if [ $? -eq 0 ]; then
        echo "  Successfully triggered scan for $REPO"
    else
        echo "  Failed to trigger scan for $REPO"
    fi
    sleep 1 # Small delay to be gentle
done

echo "All scans triggered!"
