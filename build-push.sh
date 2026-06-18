#!/usr/bin/env bash
#
# Build the Mini Happie server as a multi-arch image and push it to Docker Hub.
#
# Usage:  ./build-push.sh <version>
#   e.g.  ./build-push.sh v0.1.0
#
# Builds linux/amd64 (homelab) + linux/arm64 (Mac), tags both <version> and
# latest, and pushes the multi-arch manifest. Multi-arch images can't be loaded
# locally, so this always pushes straight to the registry.
set -euo pipefail

IMAGE="tatsster/mini-happie"
PLATFORMS="linux/amd64,linux/arm64"
BUILDER="multi"

# --- args ---
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <version>   (e.g. $0 v0.1.0)" >&2
  exit 1
fi
VERSION="$1"

# Run from the repo root (where the Dockerfile lives) regardless of CWD.
cd "$(dirname "$0")"

# --- ensure a multi-arch capable builder exists and is selected ---
if ! docker buildx inspect "$BUILDER" >/dev/null 2>&1; then
  echo ">> creating buildx builder '$BUILDER'"
  docker buildx create --name "$BUILDER" --bootstrap >/dev/null
fi
docker buildx use "$BUILDER"

# --- build + push ---
echo ">> building $IMAGE:$VERSION ($PLATFORMS) and pushing"
docker buildx build \
  --platform "$PLATFORMS" \
  -t "$IMAGE:$VERSION" \
  -t "$IMAGE:latest" \
  --push .

echo ">> done: pushed $IMAGE:$VERSION and $IMAGE:latest"
