#!/bin/bash
#
# Automatic code formatting and linting fix script
# This script will attempt to automatically fix common code quality issues
#

# Enable strict error handling
set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default to checking all files, or use passed arguments
if [[ $# -eq 0 ]]; then
    PYTHON_FILES=$(find custom_components -name "*.py" 2>/dev/null || echo "")
    echo -e "${BLUE}🔧 Fixing all Python files in custom_components/...${NC}"
else
    PYTHON_FILES="$@"
    echo -e "${BLUE}🔧 Fixing specified files...${NC}"
fi

if [[ -z "$PYTHON_FILES" ]]; then
    echo -e "${YELLOW}⚠️  No Python files found to fix${NC}"
    exit 0
fi

echo "Files to fix:"
for file in $PYTHON_FILES; do
    if [[ -f "$file" ]]; then
        echo "  - $file"
    else
        echo "  - $file (not found)"
    fi
done
echo ""

# Track if we have any failures
HAS_ERRORS=0
CHANGES_MADE=0

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to backup a file
backup_file() {
    local file="$1"
    cp "$file" "$file.backup-$(date +%s)"
    echo -e "${BLUE}📋 Created backup: $file.backup-$(date +%s)${NC}"
}

# Function to run a fix command and report results
run_fix() {
    local tool_name="$1"
    local command="$2"
    local description="$3"
    local file="$4"
    
    echo -e "${BLUE}Running $description on $file...${NC}"
    
    # Create backup before making changes
    if [[ -f "$file" ]]; then
        backup_file "$file"
    fi
    
    if eval "$command"; then
        echo -e "${GREEN}✅ $tool_name: Fixed successfully${NC}"
        CHANGES_MADE=1
        return 0
    else
        echo -e "${YELLOW}⚠️  $tool_name: Some issues may remain${NC}"
        return 1
    fi
}

echo -e "${BLUE}=== AUTOMATIC CODE FORMATTING ===${NC}"

# autopep8 - PEP8 formatting
if command_exists autopep8; then
    for file in $PYTHON_FILES; do
        if [[ -f "$file" ]]; then
            run_fix "autopep8" "autopep8 --in-place --aggressive --aggressive '$file'" "PEP8 formatting" "$file"
        fi
    done
elif command_exists python3; then
    if python3 -m autopep8 --version >/dev/null 2>&1; then
        for file in $PYTHON_FILES; do
            if [[ -f "$file" ]]; then
                run_fix "autopep8" "python3 -m autopep8 --in-place --aggressive --aggressive '$file'" "PEP8 formatting" "$file"
            fi
        done
    else
        echo -e "${YELLOW}💡 Install autopep8 for automatic PEP8 fixing: pip install autopep8${NC}"
    fi
fi

# black - opinionated code formatter
if command_exists black; then
    echo -e "${BLUE}Running black formatter...${NC}"
    VALID_FILES=""
    for file in $PYTHON_FILES; do
        if [[ -f "$file" ]]; then
            VALID_FILES="$VALID_FILES '$file'"
        fi
    done
    
    if [[ -n "$VALID_FILES" ]]; then
        # Create backups first
        for file in $PYTHON_FILES; do
            if [[ -f "$file" ]]; then
                backup_file "$file"
            fi
        done
        
        if eval "black --line-length 120 $VALID_FILES"; then
            echo -e "${GREEN}✅ black: Code formatted successfully${NC}"
            CHANGES_MADE=1
        else
            echo -e "${YELLOW}⚠️  black: Some files may not have been formatted${NC}"
        fi
    fi
fi

# isort - import sorting
if command_exists isort; then
    for file in $PYTHON_FILES; do
        if [[ -f "$file" ]]; then
            run_fix "isort" "isort --profile black --line-length 120 '$file'" "import sorting" "$file"
        fi
    done
elif command_exists python3; then
    if python3 -m isort --version >/dev/null 2>&1; then
        for file in $PYTHON_FILES; do
            if [[ -f "$file" ]]; then
                run_fix "isort" "python3 -m isort --profile black --line-length 120 '$file'" "import sorting" "$file"
            fi
        done
    fi
fi

echo ""
echo -e "${BLUE}=== MANUAL FIXES (Common Patterns) ===${NC}"

# Apply common manual fixes
for file in $PYTHON_FILES; do
    if [[ ! -f "$file" ]]; then
        continue
    fi
    
    echo -e "${BLUE}Applying manual fixes to $file...${NC}"
    backup_file "$file"
    
    TEMP_FILE=$(mktemp)
    MADE_CHANGES=0
    
    # Fix trailing whitespace
    if sed 's/[[:space:]]*$//' "$file" > "$TEMP_FILE" && ! cmp -s "$file" "$TEMP_FILE"; then
        mv "$TEMP_FILE" "$file"
        echo -e "${GREEN}  ✓ Removed trailing whitespace${NC}"
        MADE_CHANGES=1
    fi
    
    # Fix multiple blank lines
    if python3 -c "
import re
with open('$file', 'r') as f:
    content = f.read()
# Replace 3 or more consecutive newlines with exactly 2
new_content = re.sub(r'\n{3,}', '\n\n', content)
if content != new_content:
    with open('$file', 'w') as f:
        f.write(new_content)
    exit(0)
else:
    exit(1)
"; then
        echo -e "${GREEN}  ✓ Fixed excessive blank lines${NC}"
        MADE_CHANGES=1
    fi
    
    # Ensure file ends with newline
    if [[ -s "$file" ]] && [[ "$(tail -c1 "$file" | wc -l)" -eq 0 ]]; then
        echo "" >> "$file"
        echo -e "${GREEN}  ✓ Added missing newline at end of file${NC}"
        MADE_CHANGES=1
    fi
    
    # Fix basic spacing around operators (simple cases)
    if python3 -c "
import re
with open('$file', 'r') as f:
    content = f.read()
original = content
# Fix spacing around = in function definitions (but not in strings)
content = re.sub(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*([^=])', r'\1=\2', content)
# Fix spacing after commas
content = re.sub(r',([^\s\n])', r', \1', content)
if content != original:
    with open('$file', 'w') as f:
        f.write(content)
    exit(0)
else:
    exit(1)
"; then
        echo -e "${GREEN}  ✓ Fixed basic spacing issues${NC}"
        MADE_CHANGES=1
    fi
    
    if [[ $MADE_CHANGES -eq 1 ]]; then
        CHANGES_MADE=1
        echo -e "${GREEN}✅ Manual fixes applied to $file${NC}"
    else
        echo -e "${BLUE}ℹ️  No manual fixes needed for $file${NC}"
    fi
    
    rm -f "$TEMP_FILE"
done

echo ""
echo -e "${BLUE}=== FINAL VALIDATION ===${NC}"

# Run a quick check to see if we fixed the issues
if [[ -x "./lint-check.sh" ]]; then
    echo -e "${BLUE}Running lint check to validate fixes...${NC}"
    if ./lint-check.sh $PYTHON_FILES; then
        echo -e "${GREEN}🎉 All fixes successful! Code passes lint checks.${NC}"
    else
        echo -e "${YELLOW}⚠️  Some issues remain after automatic fixes.${NC}"
        echo -e "${YELLOW}You may need to fix these manually.${NC}"
    fi
else
    echo -e "${YELLOW}💡 Run ./lint-check.sh to validate the fixes${NC}"
fi

echo ""
echo -e "${BLUE}=== SUMMARY ===${NC}"

if [[ $CHANGES_MADE -eq 1 ]]; then
    echo -e "${GREEN}✅ Automatic fixes have been applied to your code!${NC}"
    echo ""
    echo -e "${YELLOW}📋 Backup files created (*.backup-*) - you can restore if needed${NC}"
    echo -e "${BLUE}💡 Review the changes before committing:${NC}"
    for file in $PYTHON_FILES; do
        if [[ -f "$file" ]]; then
            echo "  git diff $file"
        fi
    done
    echo ""
    echo -e "${BLUE}🗑️  Clean up backups when satisfied:${NC}"
    echo "  find . -name '*.backup-*' -delete"
else
    echo -e "${GREEN}✅ No fixes were needed - your code is already clean!${NC}"
fi

echo ""
echo -e "${YELLOW}💡 For even better formatting, consider installing:${NC}"
echo -e "  pip install autopep8 black isort"