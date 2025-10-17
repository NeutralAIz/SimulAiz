#!/bin/bash
# Setup CI/CD for SimulAiz
# This script helps configure the necessary GitHub secrets and SSH keys

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}==================================${NC}"
echo -e "${BLUE}SimulAiz CI/CD Setup${NC}"
echo -e "${BLUE}==================================${NC}"
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}GitHub CLI (gh) is not installed${NC}"
    echo "Install it with: sudo apt install gh"
    echo "Then authenticate with: gh auth login"
    exit 1
fi

# Check authentication
if ! gh auth status &> /dev/null; then
    echo -e "${YELLOW}Not authenticated with GitHub${NC}"
    echo "Please run: gh auth login"
    exit 1
fi

echo -e "${GREEN}✓ GitHub CLI is installed and authenticated${NC}"
echo ""

# Get repository info
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo -e "${BLUE}Repository: $REPO${NC}"
echo ""

# Function to set secret
set_secret() {
    local name=$1
    local value=$2
    local env=${3:-""}

    if [ -n "$env" ]; then
        echo -e "${BLUE}Setting secret: $name (environment: $env)${NC}"
        echo "$value" | gh secret set "$name" --env "$env"
    else
        echo -e "${BLUE}Setting secret: $name${NC}"
        echo "$value" | gh secret set "$name"
    fi
}

# Configure secrets
echo -e "${YELLOW}=== Configuring GitHub Secrets ===${NC}"
echo ""

# Check if .env exists
if [ ! -f "../.env" ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please create .env file with your LiveKit credentials"
    exit 1
fi

# Source environment variables
source ../.env

# Test environment secrets
echo -e "${BLUE}Test Environment Secrets:${NC}"

if [ -z "$LIVEKIT_URL" ]; then
    echo -e "${YELLOW}Warning: LIVEKIT_URL not set in .env${NC}"
else
    set_secret "LIVEKIT_URL" "$LIVEKIT_URL" "test"
    echo -e "${GREEN}✓ LIVEKIT_URL configured${NC}"
fi

if [ -z "$LIVEKIT_API_KEY" ]; then
    echo -e "${YELLOW}Warning: LIVEKIT_API_KEY not set in .env${NC}"
else
    set_secret "LIVEKIT_API_KEY" "$LIVEKIT_API_KEY" "test"
    echo -e "${GREEN}✓ LIVEKIT_API_KEY configured${NC}"
fi

if [ -z "$LIVEKIT_API_SECRET" ]; then
    echo -e "${YELLOW}Warning: LIVEKIT_API_SECRET not set in .env${NC}"
else
    set_secret "LIVEKIT_API_SECRET" "$LIVEKIT_API_SECRET" "test"
    echo -e "${GREEN}✓ LIVEKIT_API_SECRET configured${NC}"
fi

echo ""

# Production environment secrets
echo -e "${BLUE}Production Environment Secrets:${NC}"
echo -e "${YELLOW}Note: Using same credentials for production (update manually if different)${NC}"

if [ -n "$LIVEKIT_URL" ]; then
    set_secret "PROD_LIVEKIT_URL" "$LIVEKIT_URL" "production"
    echo -e "${GREEN}✓ PROD_LIVEKIT_URL configured${NC}"
fi

if [ -n "$LIVEKIT_API_KEY" ]; then
    set_secret "PROD_LIVEKIT_API_KEY" "$LIVEKIT_API_KEY" "production"
    echo -e "${GREEN}✓ PROD_LIVEKIT_API_KEY configured${NC}"
fi

if [ -n "$LIVEKIT_API_SECRET" ]; then
    set_secret "PROD_LIVEKIT_API_SECRET" "$LIVEKIT_API_SECRET" "production"
    echo -e "${GREEN}✓ PROD_LIVEKIT_API_SECRET configured${NC}"
fi

echo ""
echo -e "${GREEN}=== GitHub Secrets Configured ===${NC}"
echo ""

# Setup SSH key for swarm access
echo -e "${YELLOW}=== Setting up SSH Access to Swarm ===${NC}"
echo ""

SWARM_KEY="$HOME/.ssh/id_rsa"
if [ -f "$SWARM_KEY" ]; then
    echo -e "${BLUE}SSH key found: $SWARM_KEY${NC}"

    # Check if key is added to swarm manager
    if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ubuntu@192.168.50.11 'echo "Connection successful"' &> /dev/null; then
        echo -e "${GREEN}✓ SSH access to swarm manager verified${NC}"
    else
        echo -e "${RED}✗ Cannot connect to swarm manager${NC}"
        echo "Please ensure your SSH key is added to ubuntu@192.168.50.11"
        echo ""
        echo "Run on the swarm manager:"
        echo "  ssh-copy-id ubuntu@192.168.50.11"
    fi
else
    echo -e "${YELLOW}No SSH key found at $SWARM_KEY${NC}"
    echo "Generate one with: ssh-keygen -t rsa -b 4096"
    echo "Then add it to swarm manager: ssh-copy-id ubuntu@192.168.50.11"
fi

echo ""

# Setup self-hosted runner
echo -e "${YELLOW}=== GitHub Actions Runner Setup ===${NC}"
echo ""
echo -e "${BLUE}For the CI/CD pipeline to work, you need a self-hosted runner.${NC}"
echo ""
echo "To set up a runner:"
echo "1. Go to: https://github.com/$REPO/settings/actions/runners/new"
echo "2. Follow the instructions to download and configure the runner"
echo "3. Run the runner as a service:"
echo "   sudo ./svc.sh install"
echo "   sudo ./svc.sh start"
echo ""
echo -e "${YELLOW}Or use the automated script:${NC}"
echo "   cd ~/infrastructure/bin"
echo "   ./setup-github-runner.sh"
echo ""

# Final summary
echo -e "${GREEN}==================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}==================================${NC}"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "1. Ensure self-hosted runner is configured"
echo "2. Verify SSH access to swarm manager (ubuntu@192.168.50.11)"
echo ""
echo "3. Enable branch protection (RECOMMENDED):"
echo "   Go to: https://github.com/$REPO/settings/branches"
echo "   Add rule for 'main' branch:"
echo "   - ✓ Require pull request before merging"
echo "   - ✓ Require approvals (at least 1)"
echo "   - ✓ Require status checks to pass (select 'Build Docker Image')"
echo ""
echo "4. Create first feature branch and PR:"
echo "   git checkout -b feature/initial-deployment"
echo "   git add .github/workflows/deploy.yml deploy/stack.yml DEPLOYMENT.md"
echo "   git commit -m 'feat: Add PR-gated CI/CD pipeline'"
echo "   git push origin feature/initial-deployment"
echo "   Then create PR at: https://github.com/$REPO/pulls"
echo ""
echo "5. After PR approval and merge, monitor deployment:"
echo "   https://github.com/$REPO/actions"
echo ""
echo -e "${BLUE}Alternative - Direct push to main (not recommended):${NC}"
echo "   git add .github/workflows/deploy.yml deploy/stack.yml DEPLOYMENT.md"
echo "   git commit -m 'Add CI/CD pipeline'"
echo "   git push origin main"
echo ""
echo -e "${BLUE}Manual deployment option:${NC}"
echo "   cd ~/infrastructure/bin"
echo "   ./deploy-simulaiz.sh"
echo ""
