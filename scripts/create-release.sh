#!/bin/bash
# Create a new release for SimulAiz
# This script helps with version bumping and release creation

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}==================================${NC}"
echo -e "${BLUE}SimulAiz Release Creator${NC}"
echo -e "${BLUE}==================================${NC}"
echo ""

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}Error: Not in a git repository${NC}"
    exit 1
fi

# Check if gh CLI is available
if ! command -v gh &> /dev/null; then
    echo -e "${YELLOW}Warning: GitHub CLI (gh) not installed${NC}"
    echo "Install it with: sudo apt install gh"
    echo "Without gh CLI, you'll need to create the GitHub release manually"
    GH_AVAILABLE=false
else
    GH_AVAILABLE=true
fi

# Get current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo -e "${BLUE}Current branch: $CURRENT_BRANCH${NC}"

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo -e "${RED}Error: You have uncommitted changes${NC}"
    echo "Please commit or stash your changes before creating a release"
    exit 1
fi

# Get the latest tag
LATEST_TAG=$(git tag --sort=-version:refname | head -n 1)
if [ -z "$LATEST_TAG" ]; then
    echo -e "${YELLOW}No existing tags found${NC}"
    LATEST_TAG="v0.0.0"
else
    echo -e "${BLUE}Latest tag: $LATEST_TAG${NC}"
fi

# Parse current version
if [[ $LATEST_TAG =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
    MAJOR="${BASH_REMATCH[1]}"
    MINOR="${BASH_REMATCH[2]}"
    PATCH="${BASH_REMATCH[3]}"
else
    echo -e "${YELLOW}Cannot parse version from tag, starting from v0.0.0${NC}"
    MAJOR=0
    MINOR=0
    PATCH=0
fi

echo ""
echo -e "${BLUE}Current version: v$MAJOR.$MINOR.$PATCH${NC}"
echo ""

# Ask for release type
echo "Select release type:"
echo "  1) Patch   (v$MAJOR.$MINOR.$((PATCH+1))) - Bug fixes, minor changes"
echo "  2) Minor   (v$MAJOR.$((MINOR+1)).0) - New features, backward compatible"
echo "  3) Major   (v$((MAJOR+1)).0.0) - Breaking changes"
echo "  4) Custom  - Enter your own version"
echo ""
read -p "Enter choice (1-4): " CHOICE

case $CHOICE in
    1)
        NEW_VERSION="v$MAJOR.$MINOR.$((PATCH+1))"
        RELEASE_TYPE="patch"
        ;;
    2)
        NEW_VERSION="v$MAJOR.$((MINOR+1)).0"
        RELEASE_TYPE="minor"
        ;;
    3)
        NEW_VERSION="v$((MAJOR+1)).0.0"
        RELEASE_TYPE="major"
        ;;
    4)
        read -p "Enter custom version (e.g., v1.2.3): " NEW_VERSION
        if [[ ! $NEW_VERSION =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            echo -e "${RED}Error: Invalid version format. Must be vX.Y.Z${NC}"
            exit 1
        fi
        RELEASE_TYPE="custom"
        ;;
    *)
        echo -e "${RED}Error: Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}New version: $NEW_VERSION${NC}"
echo ""

# Check if tag already exists
if git tag | grep -q "^$NEW_VERSION$"; then
    echo -e "${RED}Error: Tag $NEW_VERSION already exists${NC}"
    exit 1
fi

# Ask for release notes
echo "Enter release notes (Ctrl+D when done):"
echo "(You can leave this empty for auto-generated changelog)"
echo ""
RELEASE_NOTES=$(cat)

# Ask for confirmation
echo ""
echo -e "${YELLOW}==================================${NC}"
echo -e "${YELLOW}Release Summary${NC}"
echo -e "${YELLOW}==================================${NC}"
echo "Version: $NEW_VERSION"
echo "Type: $RELEASE_TYPE"
echo "Branch: $CURRENT_BRANCH"
if [ -n "$RELEASE_NOTES" ]; then
    echo "Notes: (provided)"
else
    echo "Notes: (will be auto-generated from commits)"
fi
echo ""
read -p "Create this release? (y/N): " CONFIRM

if [[ ! $CONFIRM =~ ^[Yy]$ ]]; then
    echo "Release creation cancelled"
    exit 0
fi

# Create and push the tag
echo ""
echo -e "${BLUE}Creating tag $NEW_VERSION...${NC}"

if [ -n "$RELEASE_NOTES" ]; then
    git tag -a "$NEW_VERSION" -m "$RELEASE_NOTES"
else
    git tag -a "$NEW_VERSION" -m "Release $NEW_VERSION"
fi

echo -e "${BLUE}Pushing tag to origin...${NC}"
git push origin "$NEW_VERSION"

echo -e "${GREEN}✓ Tag created and pushed${NC}"
echo ""

# Inform about GitHub Actions
echo -e "${BLUE}GitHub Actions will now:${NC}"
echo "  1. Build Docker image tagged as $NEW_VERSION"
echo "  2. Push image to shared registry"
echo "  3. Create GitHub Release with changelog"
echo ""
echo -e "${BLUE}Monitor the build at:${NC}"
if [ "$GH_AVAILABLE" = true ]; then
    REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "your-repo")
    echo "  https://github.com/$REPO/actions"
else
    echo "  https://github.com/YOUR-USERNAME/YOUR-REPO/actions"
fi
echo ""

# Instructions for production deployment
echo -e "${GREEN}==================================${NC}"
echo -e "${GREEN}Next Steps${NC}"
echo -e "${GREEN}==================================${NC}"
echo ""
echo "1. Wait for GitHub Actions to complete the build"
echo ""
echo "2. Verify the release was created:"
if [ "$GH_AVAILABLE" = true ]; then
    echo "   gh release view $NEW_VERSION"
else
    echo "   Check: https://github.com/YOUR-REPO/releases"
fi
echo ""
echo "3. Deploy to production:"
echo "   - Go to repository → Actions"
echo "   - Select 'Build and Deploy to Shared Swarm'"
echo "   - Click 'Run workflow'"
echo "   - Select environment: production"
echo "   - Enter release tag: $NEW_VERSION"
echo "   - Click 'Run workflow'"
echo ""
echo "4. Monitor deployment and verify health checks pass"
echo ""

# Suggest next steps based on branch
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo -e "${YELLOW}Note: You created the release from branch '$CURRENT_BRANCH'${NC}"
    echo "Consider merging this to main if not already done:"
    echo "  git checkout main"
    echo "  git merge $CURRENT_BRANCH"
    echo "  git push origin main"
    echo ""
fi

echo -e "${GREEN}Release $NEW_VERSION created successfully! 🎉${NC}"
