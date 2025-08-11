# GitHub Actions Setup

## Required Secrets

Before using the Docker publish workflow, you need to set up the following secrets in your GitHub repository:

1. `DOCKERHUB_USERNAME` - Your Docker Hub username
2. `DOCKERHUB_TOKEN` - Your Docker Hub access token (not password)

### How to create Docker Hub access token:

1. Log in to [Docker Hub](https://hub.docker.com)
2. Go to Account Settings → Security
3. Click "New Access Token"
4. Give it a descriptive name (e.g., "GitHub Actions for aiseg2mqtt")
5. Copy the token (you won't be able to see it again)

### How to add secrets to GitHub:

1. Go to your repository on GitHub
2. Click on Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Add both `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`

## Triggering the workflow

The workflow will automatically run when you create a new tag:

```bash
git tag v1.0.0
git push origin v1.0.0
```

This will:
1. Build and push Docker images for both x86_64 (amd64) and ARM64 (aarch64) architectures
2. Create a GitHub Release with:
   - Auto-generated changelog from commit messages
   - Docker pull instructions
   - Link to README for installation guide

The release will be available at: `https://github.com/hiroaki0923/aiseg2mqtt/releases`