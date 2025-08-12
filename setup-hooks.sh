#!/bin/bash
#
# Setup script to install git hooks
#

set -e

HOOKS_DIR=".githooks"
GIT_HOOKS_DIR=".git/hooks"

echo "🔧 Setting up git hooks..."

# Check if we're in a git repository
if [[ ! -d ".git" ]]; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

# Check if hooks directory exists
if [[ ! -d "$HOOKS_DIR" ]]; then
    echo "❌ Error: $HOOKS_DIR directory not found"
    exit 1
fi

# Create git hooks directory if it doesn't exist
mkdir -p "$GIT_HOOKS_DIR"

# Install pre-commit hook
if [[ -f "$HOOKS_DIR/pre-commit" ]]; then
    cp "$HOOKS_DIR/pre-commit" "$GIT_HOOKS_DIR/pre-commit"
    chmod +x "$GIT_HOOKS_DIR/pre-commit"
    echo "✅ Installed pre-commit hook"
else
    echo "❌ Warning: $HOOKS_DIR/pre-commit not found"
fi

# Install pre-push hook
if [[ -f "$HOOKS_DIR/pre-push" ]]; then
    cp "$HOOKS_DIR/pre-push" "$GIT_HOOKS_DIR/pre-push"
    chmod +x "$GIT_HOOKS_DIR/pre-push"
    echo "✅ Installed pre-push hook"
else
    echo "❌ Warning: $HOOKS_DIR/pre-push not found"
fi

echo "🎉 Git hooks setup completed!"
echo ""
echo "Installed hooks:"
echo ""
echo "📋 Pre-commit hook will automatically:"
echo "  - Check Python syntax errors"
echo "  - Run basic linting (flake8 if available)"
echo "  - Validate Home Assistant patterns"
echo "  - Check manifest.json validity"
echo ""
echo "🏷️  Pre-push hook will automatically:"
echo "  - Update manifest.json version when you push version tags"
echo "  - Commit the version update before pushing the tag"
echo ""
echo "💡 Optional tools for better checking:"
echo "  - Install flake8: pip install flake8"
echo "  - Install jq: brew install jq (macOS) or apt-get install jq (Linux)"
echo ""
echo "Usage:"
echo "  git add ."
echo "  git commit -m 'message'  # Pre-commit checks run here"
echo "  git tag v1.0.0"
echo "  git push origin v1.0.0   # Pre-push version update runs here"