# Shared settings for the step 20 scripts. Source it; do not run it.
# kubectl and helm are pinned to the bobbm context through a kubeconfig written
# to results/ (git-ignored), so a context switch in another terminal cannot
# redirect a run (see the memory note on kubectl contexts).

NS=llm-d-program-aware-scheduling
DEPLOY=program-aware-vllm-decode
RELEASE=program-aware-scheduling
CTX=gke_bobzetian-gke-dev_us-central1_bobbm
STEP20="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STEP10="$STEP20/../10-llm-d-router-replicates"
RESULTS="$STEP20/results"

# One lane per node. Lane a gets the node with no other workloads; the other
# two have neighbors (91qy: vllm-omni and a dynamo worker; zhnf: comfyui and sglang).
LANE_NODE_a="${LANE_NODE_a:-gke-bobbm-bobbm-spoth100-ef0c964e-trwg}"
LANE_NODE_b="${LANE_NODE_b:-gke-bobbm-bobbm-spoth100-ef0c964e-91qy}"
LANE_NODE_c="${LANE_NODE_c:-gke-bobbm-bobbm-spoth100-ef0c964e-zhnf}"
LANES="a b c"

# The step 19 build: same plugin code as thunder-agent-lease-main at 7d548355.
export EPP_IMAGE_TAG="${EPP_IMAGE_TAG:-thunder-agent-lease-44544c04}"
# Our inference-perf build (d2bfa20: v0.7.0 + the session-replay permit fix +
# session_id in the per-request report). The lane driver's default image is
# the official v0.7.0, which has the permit bug, so this must always be set.
export BENCH_IMAGE="${BENCH_IMAGE:-$(cat "$STEP20/../12-llm-d-router-pool/results/inference-perf-image.txt")}"
export RESULTS_DIR="$RESULTS"

# The CPU tier of --kv-offloading-size=400 in tokens (48 KiB per token); the
# tier arm's capacityTokens must match what vLLM reports (smoke test).
KV_BYTES_PER_TOKEN=49152
GPU_KV_TOKENS=2237040

pin_kube() {
  mkdir -p "$RESULTS"
  local src="${KUBECONFIG_SOURCE:-$HOME/.kube/config}" kcfg="$RESULTS/bobbm.kubeconfig"
  kubectl --kubeconfig "$src" config view --minify --context="$CTX" --flatten > "$kcfg.tmp" && mv "$kcfg.tmp" "$kcfg"
  chmod 600 "$kcfg"
  export KUBECONFIG="$kcfg"
  [ "$(kubectl config current-context)" = "$CTX" ] || { echo "FATAL: kubeconfig is not pinned to $CTX" >&2; exit 1; }
}

lane_node() { local v="LANE_NODE_$1"; echo "${!v}"; }

# vllm_pod_on <node>: the running vLLM pod on that node, empty if none.
vllm_pod_on() {
  kubectl get pods -n "$NS" -l llm-d.ai/role=decode --field-selector="status.phase=Running,spec.nodeName=$1" \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true
}

# vllm_get <pod> <path>: GET http://localhost:8000<path> inside the pod.
vllm_get() {
  kubectl exec "$1" -n "$NS" -c modelserver -- python3 -c "
import sys, urllib.request
sys.stdout.write(urllib.request.urlopen('http://localhost:8000$2', timeout=60).read().decode())"
}

# deploy_offload_size: the live deployment's --kv-offloading-size, "none" if unset.
deploy_offload_size() {
  kubectl get deploy "$DEPLOY" -n "$NS" -o json | python3 -c '
import json, sys
d = json.load(sys.stdin)
args = d["spec"]["template"]["spec"]["containers"][0]["args"]
v = [a.split("=", 1)[1] for a in args if a.startswith("--kv-offloading-size=")]
print(v[0] if v else "none", d["spec"]["replicas"])'
}
