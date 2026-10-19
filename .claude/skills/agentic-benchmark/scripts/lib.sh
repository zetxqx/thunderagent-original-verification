# Shared settings for the agentic benchmark scripts. Source it; do not run it.
# Cluster, namespace, deployment and image defaults come from a profile file,
# profiles/$PROFILE.env (default bobbm); a variable already set in the
# environment wins over the profile.
# kubectl is pinned to $CTX through a kubeconfig written to $RESULTS
# (git-ignored as *.kubeconfig), so a context switch in another terminal
# cannot redirect a run.

SKILL_SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SKILL_SCRIPTS/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
RESULTS=${RESULTS:-$PWD/results}  # each step passes its own results folder

PROFILE=${PROFILE:-bobbm}
PROFILE_FILE="$SKILL_DIR/profiles/$PROFILE.env"
[ -f "$PROFILE_FILE" ] || { echo "FATAL: no profile $PROFILE_FILE (PROFILE=$PROFILE)" >&2; exit 1; }
# shellcheck source=../profiles/bobbm.env
source "$PROFILE_FILE"

pin_kube() {
  mkdir -p "$RESULTS"
  local src="${KUBECONFIG_SOURCE:-$HOME/.kube/config}" kcfg="$RESULTS/$PROFILE.kubeconfig"
  # A per-process temp file: two run-point.sh started together (parallel arms)
  # must not move each other's file.
  kubectl --kubeconfig "$src" config view --minify --context="$CTX" --flatten > "$kcfg.tmp.$$" && mv "$kcfg.tmp.$$" "$kcfg"
  chmod 600 "$kcfg"
  export KUBECONFIG="$kcfg"
  [ "$(kubectl config current-context)" = "$CTX" ] || { echo "FATAL: kubeconfig is not pinned to $CTX" >&2; exit 1; }
}

# vllm_pod_on <node>: the running vLLM pod on that node, empty if none.
vllm_pod_on() {
  kubectl get pods -n "$NS" -l "$DECODE_SELECTOR" --field-selector="status.phase=Running,spec.nodeName=$1" \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true
}

# vllm_get <pod> <path>: GET http://localhost:<first VLLM port><path> inside the pod.
vllm_get() {
  kubectl exec "$1" -n "$NS" -c "$VLLM_CONTAINER" -- python3 -c "
import sys, urllib.request
sys.stdout.write(urllib.request.urlopen('http://localhost:${VLLM_PORTS%% *}$2', timeout=60).read().decode())"
}

# deploy_selector <deployment>: its pod selector as k=v,k=v.
deploy_selector() {
  kubectl get deploy "$1" -n "$NS" \
    -o go-template='{{range $k, $v := .spec.selector.matchLabels}}{{$k}}={{$v}},{{end}}' | sed 's/,$//'
}

# selector_yaml <k=v,k=v> [extra k=v ...]: the same selector as a YAML flow map,
# for a Service rendered by the scripts.
selector_yaml() {
  local all="$1" kv out=""
  shift
  for kv in "$@"; do all="$all,$kv"; done
  for kv in ${all//,/ }; do out="$out${out:+, }${kv%%=*}: \"${kv#*=}\""; done
  echo "{$out}"
}
