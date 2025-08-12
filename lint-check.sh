#!/bin/bash
#
# Simple lint check script for Python code
#

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
FIX_MODE=0
FILES=""
for arg in "$@"; do
    if [[ "$arg" == "--fix" ]]; then
        FIX_MODE=1
    else
        FILES="$FILES $arg"
    fi
done

# Default to all Python files if none specified
if [[ -z "$FILES" ]]; then
    FILES=$(find custom_components -name "*.py" 2>/dev/null || echo "")
fi

if [[ -z "$FILES" ]]; then
    echo -e "${YELLOW}No Python files found${NC}"
    exit 0
fi

# If --fix mode, run fixes and re-check
if [[ $FIX_MODE -eq 1 ]]; then
    echo -e "${BLUE}🔧 Running automatic fixes...${NC}"
    if [[ -x "./lint-fix.sh" ]]; then
        ./lint-fix.sh $FILES
        echo ""
        echo -e "${GREEN}✅ Fixes applied! Running final check...${NC}"
        exec "$0" $FILES
    else
        echo -e "${RED}❌ lint-fix.sh not found${NC}"
        exit 1
    fi
fi

# Run checks
echo -e "${BLUE}🔍 Checking Python files...${NC}"
HAS_ERRORS=0

# 1. Python syntax check
echo -e "${BLUE}Checking syntax...${NC}"
for file in $FILES; do
    if [[ -f "$file" ]]; then
        if ! python3 -m py_compile "$file" 2>/dev/null; then
            echo -e "${RED}❌ Syntax error in $file${NC}"
            python3 -m py_compile "$file"
            HAS_ERRORS=1
        fi
    fi
done

# 2. flake8 check (if available)
if command -v flake8 >/dev/null 2>&1; then
    echo -e "${BLUE}Running flake8...${NC}"
    if flake8 --max-line-length=120 --extend-ignore=E203,W503 $FILES; then
        echo -e "${GREEN}✅ flake8: Passed${NC}"
    else
        echo -e "${RED}❌ flake8: Issues found${NC}"
        HAS_ERRORS=1
    fi
fi

# 3. Check manifest.json (if no specific files given)
if [[ "$FILES" == *"custom_components"* ]] && [[ -f "custom_components/aiseg2mqtt/manifest.json" ]]; then
    echo -e "${BLUE}Checking manifest.json...${NC}"
    if python3 -c "import json; json.load(open('custom_components/aiseg2mqtt/manifest.json'))" 2>/dev/null; then
        echo -e "${GREEN}✅ manifest.json: Valid${NC}"
    else
        echo -e "${RED}❌ manifest.json: Invalid JSON${NC}"
        HAS_ERRORS=1
    fi
fi

# Summary
echo ""
if [[ $HAS_ERRORS -eq 0 ]]; then
    echo -e "${GREEN}🎉 All checks passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Issues found${NC}"
    if [[ $FIX_MODE -eq 0 ]]; then
        echo -e "${YELLOW}💡 Run with --fix to attempt automatic fixes${NC}"
    fi
    exit 1
fi