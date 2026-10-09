# Shared settings for the agentic benchmark scripts. Source it; do not run it.
# kubectl is pinned to the bobbm context through a kubeconfig written to
# $RESULTS (git-ignored as bobbm.kubeconfig), so a context switch in another
# terminal cannot redirect a run.
# Every value can be overridden from the environment.

NS=${NS:-llm-d-program-aware-scheduling}
DEPLOY=${DEPLOY:-program-aware-vllm-decode}
CTX=${CTX:-gke_bobzetian-gke-dev_us-central1_bobbm}
RESULTS=${RESULTS:-$PWD/results}  # each step passes its own results folder
SKILL_SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SKILL_SCRIPTS/../../../.." && pwd)"

pin_kube() {
  mkdir -p "$RESULTS"
  local src="${KUBECONFIG_SOURCE:-$HOME/.kube/config}" kcfg="$RESULTS/bobbm.kubeconfig"
  kubectl --kubeconfig "$src" config view --minify --context="$CTX" --flatten > "$kcfg.tmp" && mv "$kcfg.tmp" "$kcfg"
  chmod 600 "$kcfg"
  export KUBECONFIG="$kcfg"
  [ "$(kubectl config current-context)" = "$CTX" ] || { echo "FATAL: kubeconfig is not pinned to $CTX" >&2; exit 1; }
}

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

# deploy_selector <deployment>: its pod selector as k=v,k=v.
deploy_selector() {
  kubectl get deploy "$1" -n "$NS" \
    -o go-template='{{range $k, $v := .spec.selector.matchLabels}}{{$k}}={{$v}},{{end}}' | sed 's/,$//'
}
