#!/usr/bin/env bash
# Build and push an inference-perf image from the local checkout (branch with
# the session-replay permit fix) using Cloud Build, with a minimal context:
# only what the Dockerfile copies. Usage: build-inference-perf.sh <tag>
set -euo pipefail
TAG="${1:?usage: build-inference-perf.sh <tag>}"
REPO="${INFERENCE_PERF:-$HOME/projects/llmdthunder/inference-perf}"
IMG=us-central1-docker.pkg.dev/bobzetian-gke-dev/bobinference/inference-perf
HERE="$(cd "$(dirname "$0")" && pwd)"  # resolved before the cd below
cd "$REPO"
SHA=$(git rev-parse --short HEAD); BR=$(git branch --show-current)
if gcloud artifacts docker tags list "$IMG" --format="value(tag)" 2>/dev/null | sed 's|.*/||' | grep -qx "$TAG"; then
  echo "ERROR: tag '$TAG' already exists on $IMG" >&2; exit 1; fi
CTX=$(mktemp -d /tmp/ip-build-XXXX)
cp Dockerfile pyproject.toml pdm.lock config.yml "$CTX/"
rsync -a --exclude='__pycache__' --exclude='*.pyc' inference_perf "$CTX/"
cat > "$CTX/cloudbuild.yaml" <<EOC
steps:
  - name: gcr.io/cloud-builders/docker
    args: ['build', '--platform=linux/amd64', '-t', '$IMG:$TAG',
           '--label', 'org.opencontainers.image.revision=$SHA',
           '--label', 'org.opencontainers.image.ref.name=$BR', '-f', 'Dockerfile', '.']
images: ['$IMG:$TAG']
options: { machineType: E2_HIGHCPU_8 }
timeout: 2400s
EOC
echo "Building $IMG:$TAG from $BR@$SHA (context $(du -sh "$CTX" | cut -f1))"
gcloud builds submit --config="$CTX/cloudbuild.yaml" "$CTX" || true
BUILD=$(gcloud builds list --limit=1 --format="value(id)")
while :; do ST=$(gcloud builds describe "$BUILD" --format="value(status)"); echo "  $BUILD: $ST"
  case "$ST" in SUCCESS|FAILURE|TIMEOUT|CANCELLED|EXPIRED) break;; esac; sleep 30; done
[ "$ST" = SUCCESS ] || exit 1
DIGEST=$(gcloud artifacts docker images describe "$IMG:$TAG" --format="value(image_summary.digest)")
echo "Pushed $IMG:$TAG  digest $DIGEST"
echo "$IMG@$DIGEST" > "$HERE/results/inference-perf-image.txt"
rm -rf "$CTX"
