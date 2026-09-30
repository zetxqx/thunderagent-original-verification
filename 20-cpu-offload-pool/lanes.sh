#!/usr/bin/env bash
# The three step 20 lanes: one EPP per vLLM replica, lane a/b/c pinned to the
# nodes in lib.sh (step 10's lane plumbing: render-lane.sh, lane-rbac.yaml).
#   label     label the replica on each lane node thunder-lane=<lane> and write
#             results/lanes.env (run before every point: a spot replacement
#             brings a new pod name)
#   deploy    label, then render and apply each lane's EPP with the given arms
#             (default: all thunder-lease-main) and wait for it
#   teardown  delete the lane EPPs and the labels
# Usage: lanes.sh label | deploy [a:<arm> b:<arm> c:<arm>] | teardown
set -euo pipefail
source "$(dirname "$0")/lib.sh"
pin_kube
CMD="${1:?usage: lanes.sh label|deploy|teardown}"; shift || true
CHART="${LLM_D_ROUTER:-$HOME/projects/llmdthunder/llm-d-router}/config/charts/llm-d-router-standalone"

label() {
  local TMP; TMP=$(mktemp)
  for L in $LANES; do
    local N P; N=$(lane_node "$L"); P=$(vllm_pod_on "$N")
    [ -n "$P" ] || { echo "FATAL: no running vLLM pod on lane $L's node $N" >&2; rm -f "$TMP"; exit 1; }
    for old in $(kubectl get pods -n "$NS" -l "thunder-lane=$L" -o name); do
      [ "$old" = "pod/$P" ] || kubectl label "$old" -n "$NS" thunder-lane- >/dev/null
    done
    kubectl label pod "$P" -n "$NS" "thunder-lane=$L" --overwrite >/dev/null
    { echo "LANE_${L}_POD=$P"; echo "LANE_${L}_IP=$(kubectl get pod "$P" -n "$NS" -o jsonpath='{.status.podIP}')"; echo "LANE_${L}_NODE=$N"; } >> "$TMP"
  done
  mv "$TMP" "$RESULTS/lanes.env"
  cat "$RESULTS/lanes.env"
}

case "$CMD" in
  label) label ;;
  deploy)
    helm dependency update "$CHART" >/dev/null
    git -C "$CHART" log -1 --format='%H %s' > "$RESULTS/lane-chart-commit.txt"
    kubectl apply -f "$STEP10/lane-rbac.yaml" >/dev/null
    label
    ARMS="${*:-a:thunder-lease-main b:thunder-lease-main c:thunder-lease-main}"
    for LA in $ARMS; do
      L=${LA%%:*} ARM=${LA#*:}
      "$STEP10/render-lane.sh" "$L" "$ARM" > "$RESULTS/lane-$L-manifest.yaml"
      kubectl apply -f "$RESULTS/lane-$L-manifest.yaml" >/dev/null
      kubectl rollout restart "deploy/thunder-lane-$L-epp" -n "$NS" >/dev/null
    done
    for LA in $ARMS; do
      L=${LA%%:*}
      kubectl rollout status "deploy/thunder-lane-$L-epp" -n "$NS" --timeout=300s >/dev/null
      echo "lane $L: thunder-lane-$L-epp, arm ${LA#*:}, image $EPP_IMAGE_TAG"
    done ;;
  teardown)
    for L in $LANES; do
      [ -f "$RESULTS/lane-$L-manifest.yaml" ] && kubectl delete -f "$RESULTS/lane-$L-manifest.yaml" --ignore-not-found >/dev/null && echo "removed thunder-lane-$L"
      for p in $(kubectl get pods -n "$NS" -l "thunder-lane=$L" -o name); do kubectl label "$p" -n "$NS" thunder-lane- >/dev/null && echo "unlabeled $p"; done
    done ;;
  *) echo "usage: lanes.sh label|deploy|teardown" >&2; exit 2 ;;
esac
