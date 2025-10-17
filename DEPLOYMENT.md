# SimulAiz Deployment Guide

This document describes the production-grade CI/CD pipeline for deploying SimulAiz to the shared Docker Swarm infrastructure.

## Architecture Overview

SimulAiz uses a multi-stage deployment pipeline:

```
GitHub → Build & Push → Registry → Deploy to Test → Deploy to Production
```

### Infrastructure Components

- **Docker Swarm**: Production cluster at `192.168.50.x`
- **Registry**: Private registry at `registry.shared.neutralaiz.com:5000` (192.168.50.11:5000)
- **Storage**: CephFS mounted at `/mnt/cephfs/simulaiz/`
- **Traefik**: Reverse proxy for routing and load balancing
- **GPU Node**: swarm-manager-02 (host02) with NVIDIA GPU

## Deployment Environments

### Test Environment
- **URL**: https://simulaiz.test.neutralaiz.com
- **Purpose**: Integration testing and validation
- **Auto-deploy**: Every push to `main` branch
- **Health checks**: Required before production promotion

### Production Environment
- **URL**: https://simulaiz.neutralaiz.com
- **Purpose**: Live production system
- **Deployment**: Manual trigger via GitHub Actions
- **Features**: Zero-downtime updates, automatic rollback on failure

## CI/CD Pipeline

### Pull Request Workflow (Recommended)

SimulAiz uses a **PR-gated deployment process** to ensure code quality and review before any deployment:

```
Feature Branch → Pull Request → Code Review → Merge to Main → Test Deployment → Production
```

**PR Validation (on PR creation/update):**
- Build validation only
- Verifies Docker image builds successfully
- No image push or deployment
- Provides feedback on build status

**Test Deployment (on PR merge to main):**
- Automatic deployment after PR approval and merge
- Full build, push to registry, and deploy to test environment
- Health checks verify deployment success

**Production Deployment (manual trigger):**
- Requires successful test deployment
- Manual workflow dispatch for production
- Additional health checks with automatic rollback

### Automated Workflow (GitHub Actions)

The pipeline is defined in `.github/workflows/deploy.yml` and consists of three jobs:

#### 1. Build Job
```yaml
Triggers: Pull Request (validation) OR Push to main (deployment) OR Manual workflow dispatch
Actions:
  - Checkout code
  - Build Docker image
  - Tag with commit SHA and timestamp
  - Push to shared registry (192.168.50.11:5000) - ONLY if not a PR
Outputs: Image tag, digest, and deployment flag
Behavior:
  - On PR: Build validation only, no registry push
  - On main push: Full build and push to registry
```

#### 2. Deploy to Test
```yaml
Triggers: After successful build on main branch (PR merge) OR Manual dispatch
Actions:
  - Copy stack.yml to swarm manager
  - Update image tag in configuration
  - Deploy stack with docker stack deploy
  - Wait for service stabilization (30s)
  - Run health checks (up to 2 minutes)
Validation: HTTP health check at /health endpoint
Notes: Does NOT run on PR validation - only after PR is merged to main
```

#### 3. Deploy to Production (Manual)
```yaml
Triggers: Manual workflow dispatch with environment=production
Requirements: Successful test deployment
Actions:
  - Create backup of current deployment
  - Copy production stack configuration
  - Update domains and image tags
  - Deploy with zero-downtime update strategy
  - Monitor rollout (60s stabilization)
  - Run health checks (up to 5 minutes)
Safeguards: Automatic rollback on health check failure
```

### Manual Deployment Scripts

For deployments outside of GitHub Actions (e.g., from local development machine):

#### Build and Push
```bash
cd ~/infrastructure/stacks/simulaiz
./build-and-push.sh [tag]
```

This script:
- Builds the Docker image from `/home/neutralaiz/SimulAiz`
- Tags it for the shared registry
- Pushes to registry (directly or via swarm manager)

#### Full Deployment
```bash
cd ~/infrastructure/bin
./deploy-simulaiz.sh [tag]
```

This comprehensive script:
1. Checks registry availability
2. Validates environment configuration (.env)
3. Sets up shared storage on CephFS
4. Builds and pushes the image
5. Deploys the stack to swarm
6. Verifies deployment status
7. Shows access information

## Configuration

### Environment Variables

Required secrets in GitHub (Settings → Secrets and variables → Actions):

**Test Environment:**
- `LIVEKIT_URL`: LiveKit server URL (wss://livekit.test.neutralaiz.com)
- `LIVEKIT_API_KEY`: LiveKit API key for test
- `LIVEKIT_API_SECRET`: LiveKit API secret for test

**Production Environment:**
- `PROD_LIVEKIT_URL`: LiveKit server URL for production
- `PROD_LIVEKIT_API_KEY`: LiveKit API key for production
- `PROD_LIVEKIT_API_SECRET`: LiveKit API secret for production

### Stack Configuration

The deployment stack (`deploy/stack.yml`) includes:

- **Service**: Single SimulAiz instance
- **Network**: Connected to `traefik-public` and `webhost-network`
- **Storage**: CephFS volumes for models and assets
- **Placement**: GPU-enabled node (swarm-manager-02)
- **Resources**:
  - Limit: 16GB RAM
  - Reservation: 8GB RAM, 1 GPU
- **Health Checks**: Traefik monitors `/health` endpoint
- **Update Strategy**: Rolling update with rollback on failure

### Traefik Integration

SimulAiz is automatically exposed through Traefik with:

- **Routing**: Based on Host header
- **Load Balancing**: Round-robin (when multiple replicas)
- **Health Checks**:
  - Path: `/health`
  - Interval: 10s
  - Timeout: 5s
- **Headers**: HSTS enabled (31536000 seconds)

## Release Management

### Creating Releases

SimulAiz uses semantic versioning (SemVer) for releases: `vMAJOR.MINOR.PATCH`

- **MAJOR**: Incompatible API changes or major feature overhauls
- **MINOR**: New features, backwards-compatible
- **PATCH**: Bug fixes, minor improvements

#### Release Workflow

1. **Prepare Release Branch** (optional for major releases)
   ```bash
   git checkout -b release/v1.0.0
   # Final fixes and updates
   git commit -m "chore: prepare v1.0.0 release"
   git push origin release/v1.0.0
   ```

2. **Create and Push Release Tag**

   **Option A: Using the helper script (recommended)**
   ```bash
   cd /home/neutralaiz/SimulAiz/scripts
   ./create-release.sh
   # Follow the interactive prompts
   ```

   **Option B: Manual tag creation**
   ```bash
   # From main branch (or release branch)
   git tag -a v1.0.0 -m "Release v1.0.0: Initial production release"
   git push origin v1.0.0
   ```

3. **Automatic Build and Release Creation**
   - GitHub Actions automatically:
     - Builds Docker image tagged with version
     - Pushes to registry as `v1.0.0` and `latest`
     - Generates changelog from git commits
     - Creates GitHub Release with deployment instructions

4. **Deploy Release to Production**
   - Go to repository → Actions
   - Select "Build and Deploy to Shared Swarm"
   - Click "Run workflow"
   - Select environment: `production`
   - Enter release tag: `v1.0.0`
   - Click "Run workflow"

### Viewing Releases

**List all releases:**
```bash
gh release list
```

**View specific release:**
```bash
gh release view v1.0.0
```

**List available images in registry:**
```bash
ssh ubuntu@192.168.50.11 'curl http://localhost:5000/v2/simulaiz/tags/list'
```

### Release Best Practices

1. **Version Bumping**
   - Patch (v1.0.x): Bug fixes, security patches
   - Minor (v1.x.0): New features, enhancements
   - Major (vx.0.0): Breaking changes, architecture changes

2. **Pre-Release Testing**
   - Always test in test environment first
   - Verify all features work as expected
   - Check performance and resource usage
   - Review logs for any issues

3. **Release Notes**
   - Automatically generated from commit messages
   - Use conventional commits for better changelogs
   - Include deployment instructions
   - Note any breaking changes or special requirements

4. **Production Deployment**
   - Deploy during low-traffic periods
   - Monitor health checks carefully
   - Have rollback plan ready
   - Verify deployment success before announcing

### Rolling Back a Release

If a release has issues in production:

1. **Quick Rollback via Docker Swarm**
   ```bash
   ssh ubuntu@192.168.50.11 'docker service rollback simulaiz-prod_app'
   ```

2. **Deploy Previous Release Version**
   - Go to repository → Releases
   - Find the last stable release (e.g., v1.0.0)
   - Use workflow dispatch to deploy that version
   - Select environment: `production`
   - Enter release tag: `v1.0.0`

3. **Create Hotfix Release**
   ```bash
   git checkout v1.0.0
   git checkout -b hotfix/v1.0.1
   # Apply fixes
   git commit -m "fix: critical bug in production"
   git tag -a v1.0.1 -m "Hotfix v1.0.1: Fix critical production bug"
   git push origin v1.0.1
   ```

## Shared Storage

### CephFS Structure

```
/mnt/cephfs/simulaiz/
├── models/
│   ├── wav2lip/
│   │   └── wav2lip_gan.pth    # Wav2Lip GAN weights (required for GPU)
│   └── xtts/                  # XTTS voice models
└── assets/
    └── avatar.png             # Default avatar image
```

### Storage Setup

Storage is automatically configured during deployment:

1. Directories are created on CephFS
2. Models are copied from local project (if available)
3. Assets are synced to shared storage
4. Permissions are set for container access

## Deployment Process

### Automated (Recommended) - PR-Gated Workflow

This is the recommended production-safe deployment process:

#### 1. Create Feature Branch and Make Changes
```bash
git checkout -b feature/your-feature-name
# Make your changes
git add .
git commit -m "Description of changes"
git push origin feature/your-feature-name
```

#### 2. Create Pull Request
- Go to repository on GitHub
- Click "New Pull Request"
- Select your feature branch
- Fill in PR description with:
  - What changed
  - Why it changed
  - Testing performed
  - Any special deployment considerations

#### 3. PR Build Validation
- GitHub Actions automatically runs build validation
- Verifies Docker image builds successfully
- NO deployment occurs at this stage
- Review build results in PR checks

#### 4. Code Review and Approval
- Request review from team members
- Address any feedback or requested changes
- Obtain required approvals
- **This is your deployment gate** ✓

#### 5. Merge to Main
- Once approved, merge the PR to main branch
- Delete feature branch (optional)
- **This triggers automatic test deployment**

#### 6. Automatic Test Deployment
- GitHub Actions automatically:
  - Builds and tags Docker image
  - Pushes to shared registry
  - Deploys to test environment
  - Runs health checks
- Monitor at: https://simulaiz.test.neutralaiz.com
- Check GitHub Actions for deployment status

#### 7. Verify Test Environment
```bash
# Check health endpoint
curl https://simulaiz.test.neutralaiz.com/health

# View service logs if needed
ssh ubuntu@192.168.50.11 'docker service logs -f simulaiz_app'
```

#### 8. Create Release (Recommended for Production)
For production deployments, create a release:
```bash
# Tag the release
git tag -a v1.0.0 -m "Release v1.0.0: Description of release"
git push origin v1.0.0

# GitHub Actions will automatically build and create the release
```

#### 9. Deploy Release to Production
Once release is created:
- Go to repository → Actions
- Select "Build and Deploy to Shared Swarm" workflow
- Click "Run workflow"
- Select environment: `production`
- Enter release tag: `v1.0.0`
- Click "Run workflow" button
- Monitor deployment and health checks
- Automatic rollback on failure

**Alternative**: Deploy latest from main (not recommended for production)
- Same as above but leave release tag empty
- Only use for urgent hotfixes or testing

### Quick Deployment (Main Branch)

For urgent hotfixes or when PR process is not needed:

1. **Commit and Push to Main**
   ```bash
   git add .
   git commit -m "Your changes"
   git push origin main
   ```

2. **Monitor GitHub Actions**
   - Go to repository → Actions tab
   - Watch build and test deployment progress
   - Verify test environment health checks pass

3. **Deploy to Production** (when ready)
   - Follow step 8 above

### Manual Deployment

1. **Build the Image**
   ```bash
   cd ~/SimulAiz
   docker compose build app
   ```

2. **Push to Registry**
   ```bash
   cd ~/infrastructure/stacks/simulaiz
   ./build-and-push.sh latest
   ```

3. **Deploy to Swarm**
   ```bash
   cd ~/infrastructure/bin
   ./deploy-simulaiz.sh latest
   ```

## Monitoring and Verification

### Check Service Status
```bash
ssh ubuntu@192.168.50.11 'docker service ls --filter label=com.docker.stack.namespace=simulaiz'
```

### View Service Logs
```bash
ssh ubuntu@192.168.50.11 'docker service logs -f simulaiz_app'
```

### Check Running Containers
```bash
ssh ubuntu@192.168.50.11 'docker ps --filter label=com.docker.stack.namespace=simulaiz'
```

### Verify Health Endpoint
```bash
curl https://simulaiz.test.neutralaiz.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "...",
  "timestamp": "..."
}
```

## Troubleshooting

### Build Failures

**Problem**: Docker build fails
```bash
# Check Docker status
docker info

# View build logs
docker compose build app --progress=plain
```

**Problem**: Registry push fails
```bash
# Verify registry connectivity
ssh ubuntu@192.168.50.11 'curl http://localhost:5000/v2/'

# Check registry logs
ssh ubuntu@192.168.50.11 'docker service logs registry'
```

### Deployment Failures

**Problem**: Service won't start
```bash
# Check service status
ssh ubuntu@192.168.50.11 'docker service ps simulaiz_app --no-trunc'

# View error logs
ssh ubuntu@192.168.50.11 'docker service logs simulaiz_app --tail 100'
```

**Problem**: Health checks failing
```bash
# Check service endpoint
curl -v https://simulaiz.test.neutralaiz.com/health

# Check Traefik logs
ssh ubuntu@192.168.50.11 'docker service logs traefik'
```

### Storage Issues

**Problem**: CephFS not mounted
```bash
# Check CephFS mount on swarm nodes
ssh ubuntu@192.168.50.11 'df -h | grep cephfs'
ssh ubuntu@192.168.50.12 'df -h | grep cephfs'

# Remount if needed
ssh ubuntu@192.168.50.11 'sudo mount -a'
```

**Problem**: Permission denied errors
```bash
# Check directory permissions
ssh ubuntu@192.168.50.11 'ls -la /mnt/cephfs/simulaiz/'

# Fix permissions if needed
ssh ubuntu@192.168.50.11 'sudo chmod -R 755 /mnt/cephfs/simulaiz/'
```

## Rollback Procedure

### Automatic Rollback (Production)

Health check failures in production trigger automatic rollback:
```bash
# Rollback is automatic in CI/CD pipeline
# Manual rollback if needed:
ssh ubuntu@192.168.50.11 'docker service rollback simulaiz-prod_app'
```

### Manual Rollback to Specific Version

1. **Find Previous Image Tag**
   ```bash
   ssh ubuntu@192.168.50.11 'curl http://localhost:5000/v2/simulaiz/tags/list'
   ```

2. **Update Service to Previous Image**
   ```bash
   ssh ubuntu@192.168.50.11 'docker service update \
     --image 192.168.50.11:5000/simulaiz:PREVIOUS_TAG \
     simulaiz_app'
   ```

3. **Verify Rollback**
   ```bash
   ssh ubuntu@192.168.50.11 'docker service ps simulaiz_app'
   curl https://simulaiz.test.neutralaiz.com/health
   ```

## Best Practices

### Development Workflow

1. **Always use Pull Requests** for changes
   - Create feature branches for all work
   - Use descriptive branch names (feature/, bugfix/, hotfix/)
   - Keep PRs focused and reasonably sized

2. **Code Review Requirements**
   - All PRs require at least one approval
   - Address all review comments before merging
   - Verify CI build passes before requesting review

3. **Commit Message Standards**
   - Use conventional commit format: `type: description`
   - Types: feat, fix, docs, refactor, test, chore
   - Example: `feat: add avatar crop functionality`

4. **Testing Before PR**
   - Test locally with Docker Compose
   - Verify all functionality works
   - Check for console errors or warnings

### Pre-Deployment Checklist

- [ ] PR has been approved by reviewer(s)
- [ ] All CI checks passing on PR
- [ ] Local testing completed
- [ ] Environment variables configured
- [ ] GPU models available in shared storage
- [ ] LiveKit server accessible
- [ ] Commit messages are descriptive
- [ ] Breaking changes documented in PR

### Post-Deployment Verification

- [ ] Health endpoint responds successfully
- [ ] Service logs show no errors
- [ ] GPU resources allocated correctly
- [ ] LiveKit connection established
- [ ] Avatar rendering working
- [ ] WebRTC streaming functional

### Security Considerations

1. **Secrets Management**
   - Never commit API keys or secrets to repository
   - Use GitHub Secrets for CI/CD
   - Use `.env` files for manual deployments (in .gitignore)

2. **Registry Security**
   - Private registry on internal network only
   - SSH key authentication for swarm access
   - TLS for external endpoints

3. **Network Isolation**
   - Test and production use separate stacks
   - Internal services not exposed externally
   - Traefik handles all external ingress

## Continuous Improvement

### Metrics and Monitoring

Consider adding:
- Prometheus metrics endpoint
- Grafana dashboards for GPU/memory/request metrics
- Alert manager for deployment failures
- Log aggregation (ELK/Loki)

### Performance Optimization

- Monitor image size (currently requires CPU/GPU libraries)
- Consider multi-stage builds for smaller images
- Profile GPU memory usage under load
- Implement request queueing for GPU operations

## Support and Documentation

- **Project README**: `/home/neutralaiz/SimulAiz/README.md`
- **Infrastructure Docs**: `/home/neutralaiz/infrastructure/stacks/simulaiz/README.md`
- **Deployment Scripts**: `/home/neutralaiz/infrastructure/bin/`
- **Stack Configuration**: `/home/neutralaiz/infrastructure/stacks/simulaiz/`

For issues or questions:
1. Check service logs
2. Review this deployment guide
3. Consult infrastructure documentation
4. Contact DevOps team

---

**Last Updated**: 2025-10-17
**Version**: 1.0
