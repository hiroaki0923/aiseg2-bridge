# GitHub Actions Setup

## HACS Integration Release Workflow

This repository uses GitHub Actions to automate the release process for the Home Assistant Custom Component (HACS integration).

## Setup (First Time Only)

Before creating releases, you need to install git hooks:

```bash
# Install git hooks for automatic version management
./setup-hooks.sh
```

This installs a pre-push hook that automatically updates `manifest.json` when you push version tags.

## What happens when you create a release tag

When you push a version tag (e.g., `v0.3.0`):

1. **Pre-push hook** (local) - Automatically updates `manifest.json` version and commits the change
2. **HACS Validation** (GitHub) - Validates the integration against HACS standards  
3. **Create GitHub Release** (GitHub) - Creates a release with HACS installation instructions

## Creating a release

To create a new release:

```bash
# Create and push a version tag
git tag v0.3.0
git push origin v0.3.0  # Pre-push hook auto-updates manifest.json
```

The version should follow semantic versioning (e.g., `v1.2.3`).

## Workflow Details

### Jobs

1. **validate-hacs**: Runs HACS validation to ensure integration compatibility
2. **create-release**: Creates a GitHub release with installation instructions and changelog

### Local Automation

- **pre-push hook**: Automatically updates `manifest.json` version when pushing version tags

### Generated Release Content

The release will include:
- HACS installation instructions
- Manual installation steps
- Auto-generated changelog from commit messages
- Links to documentation

## No Additional Setup Required

Unlike Docker-based workflows, this HACS workflow doesn't require any repository secrets or external service configuration. It uses the built-in `GITHUB_TOKEN` for all operations.

## Release Location

Releases will be available at: `https://github.com/hiroaki0923/aiseg2-bridge/releases`

Users can install the integration through:
- HACS (recommended)
- Manual download from GitHub releases