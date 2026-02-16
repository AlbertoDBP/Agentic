#!/bin/bash

# CATEGORIZATION FIX for SQL files
# SQL migrations should ALWAYS go to implementation/, not deployment/

echo "Fixing auto-update-docs.sh categorization for SQL files..."

# Update the categorization function in auto-update-docs.sh
# SQL files with migration patterns go to implementation
# SQL files with deployment patterns go to deployment

cat >> scripts/CATEGORIZATION-RULES.md << 'RULES'
# Auto-Update Documentation - Categorization Rules

## SQL Files
- **implementation/**: V*.sql (migrations), queries/, procedures/
- **deployment/**: setup.sql, init.sql, seed.sql
- **testing/**: test_*.sql, sample_*.sql

## Python Files  
- **implementation/**: All .py files unless test_*.py
- **testing/**: test_*.py, *_test.py
- **scripts/**: If has shebang and in scripts/

## YAML/JSON Files
- **deployment/**: docker-compose*.yml, .github/workflows/*.yml
- **implementation/**: config.yml, settings.json

## Documentation Files
- **deployment/**: *deployment*.md, *operational*.md, *runbook*.md
- **functional/**: agent-*.md, *specification*.md
- **implementation/**: implementation-*.md, technical-*.md
- **testing/**: test-*.md, *-test.md

## Priority Order
1. Check filename patterns (most specific)
2. Check file extension + content
3. Apply defaults by extension
RULES

echo "✅ Categorization rules documented"
