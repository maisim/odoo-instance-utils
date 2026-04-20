#!/usr/bin/env bash
# Usage: ./scripts/release.sh 1.2.3
set -e

VERSION=$1

if [[ -z "$VERSION" ]]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 1.2.3"
    exit 1
fi

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: version must be in format X.Y.Z (got '$VERSION')"
    exit 1
fi

BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [[ "$BRANCH" != "main" ]]; then
    echo "Error: must be on main branch (currently on '$BRANCH')"
    exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
    echo "Error: working directory is not clean"
    git status --short
    exit 1
fi

echo "Releasing version $VERSION..."

# Bump version in pyproject.toml
sed -i "s/^version = \".*\"/version = \"$VERSION\"/" pyproject.toml

# Commit and tag
git add pyproject.toml
git commit -m "chore: release $VERSION"
git tag "$VERSION"

# Push commit and tag
git push origin main
git push origin "$VERSION"

echo "Done. Pipeline will build and publish $VERSION to the GitLab PyPI registry."
