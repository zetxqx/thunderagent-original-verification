#!/usr/bin/env bash
# Roll the main EPP release back to the state saved in a manifest file.
# Helm keeps only the last 10 revisions, so a fixed revision number can be
# pruned by the upgrades of a long run (that lost revision 71 on 2026-09-28).
# This finds the newest revision whose manifest is identical to the saved one,
# rolls back to it and verifies the live manifest; it fails if none is left.
# Usage: restore-main-release.sh <saved-manifest.yaml>
#   save one with: helm get manifest program-aware-scheduling -n llm-d-program-aware-scheduling > file
set -euo pipefail
NS=llm-d-program-aware-scheduling; RELEASE=program-aware-scheduling
SAVED=${1:?saved manifest file}
helm get manifest "$RELEASE" -n "$NS" | cmp -s - "$SAVED" && { echo "release already matches $SAVED"; exit 0; }
for REV in $(helm history "$RELEASE" -n "$NS" --max 100 -o json | python3 -c 'import json,sys; print(" ".join(str(r["revision"]) for r in sorted(json.load(sys.stdin), key=lambda r: -r["revision"])))'); do
  if helm get manifest "$RELEASE" -n "$NS" --revision "$REV" | cmp -s - "$SAVED"; then
    helm rollback "$RELEASE" "$REV" -n "$NS"
    kubectl rollout status "deploy/$RELEASE-epp" -n "$NS" --timeout=300s
    helm get manifest "$RELEASE" -n "$NS" | cmp -s - "$SAVED" || { echo "FATAL: live manifest differs from $SAVED after rollback" >&2; exit 1; }
    echo "restored: rolled back to revision $REV (matches $SAVED)"; exit 0
  fi
done
echo "FATAL: no revision in the release history matches $SAVED; restore by hand" >&2; exit 1
