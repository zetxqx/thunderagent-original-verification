#!/usr/bin/env python3
"""Make a CPU KV offloading variant of the vLLM deployment, or a clean copy of it.

  kubectl get deploy program-aware-vllm-decode -o json | vllm-offload.py clean > before.json
  kubectl get deploy program-aware-vllm-decode -o json | vllm-offload.py 400 > offload400.json
  kubectl replace -f offload400.json     # and later: kubectl replace -f before.json

The variant changes only what vLLM's native OffloadingConnector needs (as in step 20):
  --kv-offloading-size=<GiB> (summed over the TP ranks);
  memory request and limit <GiB>+50 Gi: the tier is a tmpfs file in /dev/shm and its
    pages count against the pod's memory limit, plus process memory and headroom;
  /dev/shm sizeLimit <GiB>+10 Gi: the connector checks /dev/shm free space first;
  a required pod anti-affinity, one replica per node: two 450 Gi pods do not fit the
    895 GiB allocatable of an a3-highgpu-4g node.
"""

import json
import sys

DROP_META = ("resourceVersion", "uid", "creationTimestamp", "generation", "managedFields", "selfLink")


def clean(d: dict) -> dict:
    d.pop("status", None)
    for k in DROP_META:
        d["metadata"].pop(k, None)
    ann = d["metadata"].get("annotations", {})
    for k in ("deployment.kubernetes.io/revision", "kubectl.kubernetes.io/last-applied-configuration"):
        ann.pop(k, None)
    tmeta = d["spec"]["template"].get("metadata", {})
    tmeta.get("annotations", {}).pop("kubectl.kubernetes.io/restartedAt", None)
    return d


def offload(d: dict, gib: int) -> dict:
    spec = d["spec"]["template"]["spec"]
    c = spec["containers"][0]
    c["args"] = [a for a in c.get("args", []) if not a.startswith("--kv-offloading-size")] + [f"--kv-offloading-size={gib}"]
    mem = f"{gib + 50}Gi"
    c.setdefault("resources", {}).setdefault("requests", {})["memory"] = mem
    c["resources"].setdefault("limits", {})["memory"] = mem
    shm = [v for v in spec.get("volumes", []) if v.get("emptyDir", {}).get("medium") == "Memory"]
    if len(shm) != 1:
        sys.exit(f"expected one memory emptyDir (/dev/shm), found {len(shm)}")
    shm[0]["emptyDir"]["sizeLimit"] = f"{gib + 10}Gi"
    spec.setdefault("affinity", {})["podAntiAffinity"] = {
        "requiredDuringSchedulingIgnoredDuringExecution": [{
            "labelSelector": {"matchLabels": d["spec"]["selector"]["matchLabels"]},
            "topologyKey": "kubernetes.io/hostname",
        }]
    }
    return d


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    d = clean(json.load(sys.stdin))
    if mode != "clean":
        if not mode.isdigit():
            sys.exit("usage: vllm-offload.py clean|<GiB>")
        d = offload(d, int(mode))
    json.dump(d, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
