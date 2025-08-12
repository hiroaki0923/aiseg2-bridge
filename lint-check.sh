#!/bin/bash
#
# Manual lint and quality check script
# Run this before committing to catch issues early
#

# Enable strict error handling
set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check for --fix flag
FIX_MODE=0
ARGS=()
for arg in "$@"; do
    if [[ "$arg" == "--fix" ]]; then
        FIX_MODE=1
    else
        ARGS+=("$arg")
    fi
done

# Default to checking all files, or use passed arguments
if [[ ${#ARGS[@]} -eq 0 ]]; then
    PYTHON_FILES=$(find custom_components -name "*.py" 2>/dev/null || echo "")
    CHECK_MANIFEST=1
    if [[ $FIX_MODE -eq 1 ]]; then
        echo -e "${BLUE}🔧 Running checks and fixes on all Python files in custom_components/...${NC}"
    else
        echo -e "${BLUE}🔍 Running checks on all Python files in custom_components/...${NC}"
    fi
else
    PYTHON_FILES="${ARGS[*]}"
    CHECK_MANIFEST=0
    if [[ $FIX_MODE -eq 1 ]]; then
        echo -e "${BLUE}🔧 Running checks and fixes on specified files...${NC}"
    else
        echo -e "${BLUE}🔍 Running checks on specified files...${NC}"
    fi
fi

if [[ -z "$PYTHON_FILES" ]]; then
    echo -e "${YELLOW}⚠️  No Python files found to check${NC}"
    exit 0
fi

echo "Files to check:"
for file in $PYTHON_FILES; do
    echo "  - $file"
done
echo ""

# Track if we have any failures
HAS_ERRORS=0
HAS_WARNINGS=0

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to run a check and report results
run_check() {
    local tool_name="$1"
    local command="$2"
    local description="$3"
    local is_warning="${4:-0}"
    
    echo -e "${BLUE}Running $description...${NC}"
    
    if eval "$command"; then
        echo -e "${GREEN}✅ $tool_name: Passed${NC}"
        return 0
    else
        if [[ $is_warning -eq 1 ]]; then
            echo -e "${YELLOW}⚠️  $tool_name: Issues found (warnings)${NC}"
            HAS_WARNINGS=1
        else
            echo -e "${RED}❌ $tool_name: Failed${NC}"
            HAS_ERRORS=1
        fi
        return 1
    fi
}

echo -e "${BLUE}=== SYNTAX AND BASIC CHECKS ===${NC}"

# Check for basic Python syntax errors
echo -e "${BLUE}Checking Python syntax...${NC}"
SYNTAX_OK=1
for file in $PYTHON_FILES; do
    if [[ -f "$file" ]]; then
        if ! python3 -m py_compile "$file" 2>/dev/null; then
            echo -e "${RED}❌ Syntax error in $file${NC}"
            python3 -m py_compile "$file" || true
            HAS_ERRORS=1
            SYNTAX_OK=0
        fi
    else
        echo -e "${YELLOW}⚠️  File not found: $file${NC}"
        HAS_WARNINGS=1
    fi
done

if [[ $SYNTAX_OK -eq 1 ]]; then
    echo -e "${GREEN}✅ Python syntax: All files passed${NC}"
fi

echo ""
echo -e "${BLUE}=== LINTING TOOLS ===${NC}"

# flake8 - comprehensive linting
if command_exists flake8; then
    # Create a temporary file list to avoid shell expansion issues
    TEMP_FILE_LIST=$(mktemp)
    for file in $PYTHON_FILES; do
        if [[ -f "$file" ]]; then
            echo "$file" >> "$TEMP_FILE_LIST"
        fi
    done
    
    if [[ -s "$TEMP_FILE_LIST" ]]; then
        run_check "flake8 (full)" "flake8 --max-line-length=120 --extend-ignore=E203,W503 $(cat $TEMP_FILE_LIST | tr '\n' ' ')" "comprehensive linting with flake8" 0
    fi
    rm -f "$TEMP_FILE_LIST"
elif python3 -m flake8 --version >/dev/null 2>&1; then
    # Try using flake8 via python module
    VALID_FILES=""
    for file in $PYTHON_FILES; do
        if [[ -f "$file" ]]; then
            VALID_FILES="$VALID_FILES $file"
        fi
    done
    if [[ -n "$VALID_FILES" ]]; then
        run_check "flake8 (critical)" "python3 -m flake8 --select=E9,F63,F7,F82 $VALID_FILES" "critical error checking" 1
    fi
fi

# pylint - if available
if command_exists pylint; then
    VALID_FILES=""
    for file in $PYTHON_FILES; do
        if [[ -f "$file" ]]; then
            VALID_FILES="$VALID_FILES $file"
        fi
    done
    if [[ -n "$VALID_FILES" ]]; then
        run_check "pylint" "pylint --errors-only $VALID_FILES" "error checking with pylint" 1
    fi
fi

# mypy - if available
if command_exists mypy; then
    VALID_FILES=""
    for file in $PYTHON_FILES; do
        if [[ -f "$file" ]]; then
            VALID_FILES="$VALID_FILES $file"
        fi
    done
    if [[ -n "$VALID_FILES" ]]; then
        run_check "mypy" "mypy --ignore-missing-imports --no-strict-optional $VALID_FILES" "type checking with mypy" 1
    fi
fi

echo ""
echo -e "${BLUE}=== HOME ASSISTANT SPECIFIC CHECKS ===${NC}"

# Check for Home Assistant specific patterns
HA_ISSUES=0
for file in $PYTHON_FILES; do
    if [[ ! -f "$file" ]]; then
        continue
    fi
    
    echo -e "${BLUE}Checking HA patterns in $file...${NC}"
    
    # Check for proper async/await usage
    if grep -n "def.*async" "$file" 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Line $(grep -n "def.*async" "$file" | cut -d: -f1): Should be 'async def' not 'def.*async'${NC}"
        HA_ISSUES=1
    fi
    
    # Check for proper logging import
    if grep -q "_LOGGER\." "$file" && ! grep -q "import logging" "$file" && ! grep -q "_LOGGER = logging.getLogger" "$file"; then
        echo -e "${YELLOW}⚠️  Using _LOGGER without proper logging setup${NC}"
        HA_ISSUES=1
    fi
    
    # Check for proper exception handling in async functions
    if grep -q "async def.*update\|async def.*fetch" "$file" && ! grep -q "except.*Exception" "$file"; then
        echo -e "${YELLOW}⚠️  Async data methods should have exception handling${NC}"
        HA_ISSUES=1
    fi
    
    # Check for missing docstrings in public functions
    if grep -n "^def \|^async def " "$file" | grep -v "__" | head -5; then
        echo -e "${BLUE}ℹ️  Public functions found (consider adding docstrings)${NC}"
    fi
done

if [[ $HA_ISSUES -eq 0 ]]; then
    echo -e "${GREEN}✅ Home Assistant patterns: All checks passed${NC}"
else
    HAS_WARNINGS=1
fi

# Check manifest.json if requested
if [[ $CHECK_MANIFEST -eq 1 ]]; then
    echo ""
    echo -e "${BLUE}=== MANIFEST.JSON VALIDATION ===${NC}"
    
    MANIFEST_FILE="custom_components/aiseg2mqtt/manifest.json"
    if [[ -f "$MANIFEST_FILE" ]]; then
        if command_exists jq; then
            if jq . "$MANIFEST_FILE" > /dev/null; then
                echo -e "${GREEN}✅ manifest.json: Valid JSON${NC}"
                
                # Check required fields
                REQUIRED_FIELDS="domain name version documentation issue_tracker requirements codeowners"
                MANIFEST_OK=1
                for field in $REQUIRED_FIELDS; do
                    if ! jq -e ".$field" "$MANIFEST_FILE" > /dev/null; then
                        echo -e "${RED}❌ manifest.json: Missing required field '$field'${NC}"
                        HAS_ERRORS=1
                        MANIFEST_OK=0
                    fi
                done
                
                if [[ $MANIFEST_OK -eq 1 ]]; then
                    echo -e "${GREEN}✅ manifest.json: All required fields present${NC}"
                fi
            else
                echo -e "${RED}❌ manifest.json: Invalid JSON${NC}"
                HAS_ERRORS=1
            fi
        elif command_exists python3; then
            if python3 -c "
import json
try:
    with open('$MANIFEST_FILE', 'r') as f:
        data = json.load(f)
    print('Valid JSON')
    print(f'Version: {data.get(\"version\", \"unknown\")}')
    print(f'Domain: {data.get(\"domain\", \"unknown\")}')
except json.JSONDecodeError as e:
    print(f'Invalid JSON: {e}')
    exit(1)
"; then
                echo -e "${GREEN}✅ manifest.json: Valid JSON${NC}"
            else
                echo -e "${RED}❌ manifest.json: Invalid JSON${NC}"
                HAS_ERRORS=1
            fi
        fi
    else
        echo -e "${YELLOW}⚠️  manifest.json not found${NC}"
        HAS_WARNINGS=1
    fi
fi

echo ""
echo -e "${BLUE}=== SUMMARY ===${NC}"

if [[ $FIX_MODE -eq 1 && ($HAS_ERRORS -gt 0 || $HAS_WARNINGS -gt 0) ]]; then
    echo -e "${BLUE}🔧 Attempting automatic fixes...${NC}"
    if [[ -x "./lint-fix.sh" ]]; then
        ./lint-fix.sh $PYTHON_FILES
        echo ""
        echo -e "${BLUE}Running checks again after fixes...${NC}"
        # Re-run checks to see if fixes worked
        exec "$0" "${ARGS[@]}"
    else
        echo -e "${RED}❌ lint-fix.sh not found or not executable${NC}"
        exit 1
    fi
fi

if [[ $HAS_ERRORS -eq 0 && $HAS_WARNINGS -eq 0 ]]; then
    echo -e "${GREEN}🎉 All checks passed! Code is ready to commit.${NC}"
    exit 0
elif [[ $HAS_ERRORS -eq 0 ]]; then
    echo -e "${YELLOW}⚠️  Some warnings found, but no critical errors.${NC}"
    echo -e "${YELLOW}Consider fixing warnings before committing.${NC}"
    if [[ $FIX_MODE -eq 0 ]]; then
        echo -e "${BLUE}💡 Run with --fix to attempt automatic fixes: ./lint-check.sh --fix${NC}"
    fi
    exit 0
else
    echo -e "${RED}💥 Critical errors found! Please fix before committing.${NC}"
    echo ""
    echo -e "${YELLOW}💡 Tips:${NC}"
    echo -e "  - Run with --fix to attempt automatic fixes: ./lint-check.sh --fix"
    echo -e "  - Install additional tools: pip install autopep8 black isort flake8 pylint mypy"
    echo -e "  - Install jq: brew install jq (macOS) or apt-get install jq (Linux)"
    echo -e "  - Check specific files: ./lint-check.sh path/to/file.py"
    exit 1
fi