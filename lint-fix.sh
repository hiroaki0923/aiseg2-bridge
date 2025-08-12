#!/bin/bash
#
# Automatic code formatting script using standard tools
#

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get files to fix
if [[ $# -eq 0 ]]; then
    PYTHON_FILES=$(find custom_components -name "*.py" 2>/dev/null || echo "")
    echo -e "${BLUE}🔧 Fixing all Python files in custom_components/...${NC}"
else
    PYTHON_FILES="$@"
    echo -e "${BLUE}🔧 Fixing specified files...${NC}"
fi

if [[ -z "$PYTHON_FILES" ]]; then
    echo -e "${YELLOW}No Python files found${NC}"
    exit 0
fi

echo "Files to fix:"
for file in $PYTHON_FILES; do
    echo "  - $file"
done
echo ""

# Track if we made changes
CHANGES_MADE=0

# 1. Run black FIRST (most comprehensive formatter)
if command -v black >/dev/null 2>&1; then
    echo -e "${BLUE}Running black formatter...${NC}"
    if black --line-length 120 $PYTHON_FILES; then
        CHANGES_MADE=1
    fi
else
    echo -e "${RED}black not found - install with: pip install black${NC}"
    echo -e "${YELLOW}Black is required for proper Python formatting${NC}"
    exit 1
fi

# 2. Run isort (import sorting - after black to maintain compatibility)
if command -v isort >/dev/null 2>&1; then
    echo -e "${BLUE}Running isort...${NC}"
    for file in $PYTHON_FILES; do
        if [[ -f "$file" ]]; then
            if isort --profile black --line-length 120 "$file"; then
                echo -e "${GREEN}  ✓ $file${NC}"
                CHANGES_MADE=1
            fi
        fi
    done
else
    echo -e "${YELLOW}isort not found - install with: pip install isort${NC}"
fi

# Summary
echo ""
if [[ $CHANGES_MADE -eq 1 ]]; then
    echo -e "${GREEN}✅ Formatting complete!${NC}"
    echo -e "${BLUE}Review changes with: git diff${NC}"
else
    echo -e "${GREEN}✅ No changes needed - code is already formatted!${NC}"
fi