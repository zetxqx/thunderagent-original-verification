#!/usr/bin/env bash
# Build the upstream ThunderAgent image with Google Cloud Build and push to Artifact Registry.
# The upstream checkout (../ThunderAgent relative to the project root) is staged, not modified.
set -euo pipefail

PROJECT=bobzetian-gke-dev
REGION=us-central1
REPO=bobinference
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$SCRIPT_DIR/../../ThunderAgent"

GIT_SHA="$(git -C "$SRC_DIR" rev-parse --short HEAD)"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/thunderagent-original:${GIT_SHA}"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

rsync -a --exclude .git --exclude assets --exclude wiki --exclude examples "$SRC_DIR/" "$STAGE/"
cp "$SCRIPT_DIR/Dockerfile" "$STAGE/Dockerfile"

echo "Building $IMAGE from ThunderAgent commit $GIT_SHA"
gcloud builds submit "$STAGE" --project "$PROJECT" --tag "$IMAGE"

echo "Pushed: $IMAGE"
