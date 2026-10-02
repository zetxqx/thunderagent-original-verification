#!/usr/bin/env bash
# Switch the vLLM model server between the step 20 states and record each one.
#   save-before  refuse if GPU pods are pending or the live deployment is not
#                ../model-server/deployment.yaml (the base both manifests were
#                generated from); save the live deployment and the main EPP
#                release under results/.
#   off          apply vllm-deploy-3rep-off.yaml (phase A)
#   on           apply vllm-deploy-3rep-offload400.yaml (phase B)
#   restore      apply results/vllm-deploy-before-clean.json (the original)
#   check-original  exit 0 if the live deployment is the saved original
# STATE_SUFFIX (default empty) is appended to the state names in the files
# below, so a later run does not overwrite an earlier run's records.
# Each switch waits for the rollout and writes results/vllm-deploy-live-<state>.yaml,
# vllm-pods-<state>.txt, vllm-cache-config-<state>.txt and
# vllm-startup-<state>-<pod>.log. Manifests are applied with kubectl replace,
# so the live object is exactly the file (no merge with earlier applies).
set -euo pipefail
source "$(dirname "$0")/lib.sh"
pin_kube
CMD="${1:?usage: offload.sh save-before|off|on|restore|check-original}"
SFX="${STATE_SUFFIX:-}"

# template_of <file|-> : the replicas and pod template of a deployment, as
# canonical JSON (runtime and kubectl-added fields dropped), for comparison.
template_of() {
  python3 -c '
import json, sys, subprocess
src = sys.argv[1]
if src == "-":
    d = json.load(sys.stdin)
else:
    d = json.loads(subprocess.check_output(["uv", "run", "--quiet", "--with", "pyyaml", "python", "-c",
        "import json,sys,yaml; print(json.dumps(yaml.safe_load(open(sys.argv[1]))))", src]))
t = d["spec"]["template"]
t.get("metadata", {}).pop("creationTimestamp", None)
t.get("metadata", {}).get("annotations", {}).pop("kubectl.kubernetes.io/restartedAt", None)
if not t.get("metadata", {}).get("annotations"):
    t.get("metadata", {}).pop("annotations", None)
print(json.dumps({"replicas": d["spec"]["replicas"], "template": t}, sort_keys=True))' "$1"
}

record() { # record <state>
  local S=$1
  kubectl get deploy "$DEPLOY" -n "$NS" -o yaml > "$RESULTS/vllm-deploy-live-$S.yaml"
  kubectl get pods -n "$NS" -l llm-d.ai/role=decode \
    -o custom-columns='POD:.metadata.name,UID:.metadata.uid,NODE:.spec.nodeName,IP:.status.podIP,PHASE:.status.phase,RESTARTS:.status.containerStatuses[0].restartCount' \
    > "$RESULTS/vllm-pods-$S.txt"
  : > "$RESULTS/vllm-cache-config-$S.txt"
  for P in $(kubectl get pods -n "$NS" -l llm-d.ai/role=decode --field-selector=status.phase=Running -o jsonpath='{.items[*].metadata.name}'); do
    { printf '%s ' "$P"; vllm_get "$P" /metrics | grep '^vllm:cache_config_info' || echo "(no cache_config_info)"; } >> "$RESULTS/vllm-cache-config-$S.txt"
    kubectl logs "$P" -n "$NS" -c modelserver > "$RESULTS/vllm-startup-$S-$P.log" 2>&1 || true
  done
  cat "$RESULTS/vllm-pods-$S.txt"
  sed 's/^\([^ ]*\) .*kv_offloading_size="\([^"]*\)".*num_gpu_blocks="\([^"]*\)".*/\1 kv_offloading_size=\2 num_gpu_blocks=\3/' "$RESULTS/vllm-cache-config-$S.txt"
}

switch() { # switch <manifest> <state> <expected --kv-offloading-size or none>
  local F=$1 S=$2 WANT=$3
  echo "applying $F ($(date))"
  kubectl replace -f "$F"
  # Recreate strategy: all pods go, then the new ones load the model and, with
  # offloading, prefault the whole CPU tier. The startup probe allows 60 min.
  kubectl rollout status "deploy/$DEPLOY" -n "$NS" --timeout=75m
  local GOT; GOT=$(deploy_offload_size)
  [ "${GOT%% *}" = "$WANT" ] || { echo "FATAL: live --kv-offloading-size is ${GOT%% *}, expected $WANT" >&2; exit 1; }
  record "$S"
  # One replica per node, on the lane nodes: only for the step 20 states (the
  # original deployment puts two replicas on one node).
  [ "${S%"$SFX"}" != after-restore ] || return 0
  local NODES; NODES=$(kubectl get pods -n "$NS" -l llm-d.ai/role=decode --field-selector=status.phase=Running -o jsonpath='{range .items[*]}{.spec.nodeName}{"\n"}{end}' | sort)
  [ "$(echo "$NODES" | uniq | wc -l | tr -d ' ')" = "$(echo "$NODES" | wc -l | tr -d ' ')" ] || { echo "FATAL: two replicas share a node" >&2; exit 1; }
  for L in $LANES; do
    echo "$NODES" | grep -qx "$(lane_node "$L")" || echo "WARNING: no replica on lane $L's node $(lane_node "$L"); set LANE_NODE_$L to one of: $(echo $NODES)"
  done
}

case "$CMD" in
  save-before)
    PENDING=$(kubectl get pods -A --field-selector=status.phase=Pending -o json | python3 -c '
import json, sys
print(" ".join(p["metadata"]["namespace"] + "/" + p["metadata"]["name"] for p in json.load(sys.stdin)["items"]
  if any("nvidia.com/gpu" in (c.get("resources", {}).get("requests") or {}) for c in p["spec"]["containers"])))')
    [ -z "$PENDING" ] || { echo "FATAL: GPU pods are pending and could take the GPUs step 20 frees: $PENDING" >&2; exit 1; }
    kubectl get deploy "$DEPLOY" -n "$NS" -o json > "$RESULTS/vllm-deploy-before.json"
    kubectl get deploy "$DEPLOY" -n "$NS" -o yaml > "$RESULTS/vllm-deploy-before.yaml"
    [ "$(template_of - < "$RESULTS/vllm-deploy-before.json")" = "$(template_of "$STEP20/../model-server/deployment.yaml")" ] || {
      echo "FATAL: the live deployment differs from ../model-server/deployment.yaml, the base of both step 20 manifests;" >&2
      echo "       regenerate them from the live deployment first (see the README)" >&2; exit 1; }
    # A clean copy to restore from: runtime fields dropped so kubectl replace applies it.
    python3 - "$RESULTS/vllm-deploy-before.json" "$RESULTS/vllm-deploy-before-clean.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
d.pop("status", None)
m = d["metadata"]
for k in ("creationTimestamp", "generation", "resourceVersion", "uid", "managedFields"):
    m.pop(k, None)
m.get("annotations", {}).pop("kubectl.kubernetes.io/last-applied-configuration", None)
json.dump(d, open(sys.argv[2], "w"), indent=1)
PY
    helm get manifest "$RELEASE" -n "$NS" > "$RESULTS/main-release-before.yaml"
    record before
    echo "saved: vllm-deploy-before.{yaml,json}, vllm-deploy-before-clean.json, main-release-before.yaml" ;;
  off) switch "$STEP20/vllm-deploy-3rep-off.yaml" "off$SFX" none ;;
  on)  switch "$STEP20/vllm-deploy-3rep-offload400.yaml" "offload400$SFX" 400 ;;
  check-original)
    if [ "$(kubectl get deploy "$DEPLOY" -n "$NS" -o json | template_of -)" = "$(template_of - < "$RESULTS/vllm-deploy-before.json")" ]; then
      echo "live deployment is the saved original"
    else
      echo "live deployment differs from results/vllm-deploy-before.json" >&2; exit 1
    fi ;;
  restore)
    [ -f "$RESULTS/vllm-deploy-before-clean.json" ] || { echo "FATAL: no saved deployment; run save-before first" >&2; exit 1; }
    switch "$RESULTS/vllm-deploy-before-clean.json" "after-restore$SFX" none
    kubectl get deploy "$DEPLOY" -n "$NS" -o yaml > "$RESULTS/vllm-deploy-after-restore$SFX.yaml"
    if [ "$(kubectl get deploy "$DEPLOY" -n "$NS" -o json | template_of -)" = "$(template_of - < "$RESULTS/vllm-deploy-before.json")" ]; then
      echo "restored: replicas and pod template match vllm-deploy-before.json"
    else
      echo "FATAL: the restored deployment differs from vllm-deploy-before.json" >&2; exit 1
    fi ;;
  *) echo "usage: offload.sh save-before|off|on|restore|check-original" >&2; exit 2 ;;
esac
