#!/usr/bin/env bash
# Re-collect every fact in README.md from the live cluster.
# Read-only: safe to run while a benchmark is in flight.
set -euo pipefail

NS="${NS:-llm-d-program-aware-scheduling}"
DEPLOY=program-aware-vllm-decode

POD=$(kubectl get pods -n "$NS" -l llm-d.ai/role=decode --field-selector=status.phase=Running \
        -o jsonpath='{.items[0].metadata.name}')
NODE=$(kubectl get pod "$POD" -n "$NS" -o jsonpath='{.spec.nodeName}')
echo "sampling pod $POD on node $NODE"

echo; echo "===== 1. launch arguments, image, resources ====="
kubectl get deploy "$DEPLOY" -n "$NS" -o json | python3 -c '
import json,sys
d=json.load(sys.stdin); c=d["spec"]["template"]["spec"]["containers"][0]
print("image     :",c["image"])
print("replicas  :",d["spec"]["replicas"],"strategy:",d["spec"]["strategy"]["type"])
print("command   :"," ".join(c.get("command",[])))
print("args      :"); [print("   ",a) for a in c.get("args",[])]
print("env       :",[e["name"] for e in c.get("env",[])])
print("resources :",json.dumps(c.get("resources")))'

echo; echo "===== 2. hardware ====="
kubectl get node "$NODE" -o jsonpath='nodepool={.metadata.labels.cloud\.google\.com/gke-nodepool}{"\n"}machine={.metadata.labels.node\.kubernetes\.io/instance-type}{"\n"}gpu={.metadata.labels.cloud\.google\.com/gke-accelerator}{"\n"}spot={.metadata.labels.cloud\.google\.com/gke-spot}{"\n"}zone={.metadata.labels.topology\.kubernetes\.io/zone}{"\n"}kubelet={.status.nodeInfo.kubeletVersion}{"\n"}capacity={.status.capacity}{"\n"}'

echo; echo "===== 3. pod placement ====="
kubectl get pods -n "$NS" -l llm-d.ai/role=decode \
  -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName,IP:.status.podIP,START:.status.startTime

echo; echo "===== 4. deployment revision history ====="
kubectl get rs -n "$NS" -l llm-d.ai/role=decode --sort-by=.metadata.creationTimestamp \
  -o custom-columns=RS:.metadata.name,REV:.metadata.annotations.deployment\\.kubernetes\\.io/revision,CREATED:.metadata.creationTimestamp,REPLICAS:.spec.replicas

echo; echo "===== 5. engine version and resolved config (live) ====="
kubectl exec "$POD" -n "$NS" -c modelserver -- python3 -c '
import urllib.request,json,re
print("version:",urllib.request.urlopen("http://localhost:8000/version",timeout=15).read().decode())
s=json.loads(urllib.request.urlopen("http://localhost:8000/server_info",timeout=15).read().decode())["vllm_config"]
for k in ("tensor_parallel_size","pipeline_parallel_size","max_seq_len","dtype","quantization",
          "kv_cache_dtype","enable_prefix_caching","enable_chunked_prefill"):
    m=re.search(k+r"=([^,)]+)",s)
    v=m.group(1) if m else "(not reported)"
    print("  %-24s %s"%(k,v))'

echo; echo "===== 6. KV cache pool (live metric) ====="
kubectl exec "$POD" -n "$NS" -c modelserver -- sh -c \
  "curl -s localhost:8000/metrics | grep '^vllm:cache_config_info'" | tr ',' '\n' | \
  grep -E 'block_size|num_gpu_blocks|kv_cache_size_tokens|kv_cache_max_concurrency|cache_dtype|enable_prefix_caching|gpu_memory_utilization'

echo; echo "===== 7. batch limits (REPRODUCED, not read from the engine) ====="
echo "v0.28.0 exposes neither max_num_batched_tokens nor max_num_seqs at runtime."
echo "Re-running vLLM's own resolution with the same flags and usage context:"
kubectl exec "$POD" -n "$NS" -c modelserver -- python3 -c '
from vllm.engine.arg_utils import EngineArgs
from vllm.usage.usage_lib import UsageContext
s=EngineArgs(model="Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8", tensor_parallel_size=2,
             max_model_len=262144, kv_cache_dtype="fp8_e4m3", gpu_memory_utilization=0.88
             ).create_engine_config(UsageContext.OPENAI_API_SERVER).scheduler_config
for k in ("max_num_batched_tokens","max_num_seqs","enable_chunked_prefill",
          "long_prefill_token_threshold","policy","async_scheduling"):
    print(f"  {k:30s} {getattr(s,k,None)}")' 2>/dev/null

echo; echo "===== 8. model architecture ====="
kubectl exec "$POD" -n "$NS" -c modelserver -- python3 -c '
from transformers import AutoConfig
d=AutoConfig.from_pretrained("Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8").to_dict()
for k in ("model_type","num_hidden_layers","hidden_size","num_attention_heads",
          "num_key_value_heads","num_experts_per_tok","max_position_embeddings","vocab_size"):
    if k in d: print(f"  {k:26s} {d[k]}")
q=d.get("quantization_config") or {}
print("  quantization              ",{k:q[k] for k in ("quant_method","fmt","weight_block_size","activation_scheme") if k in q})' 2>/dev/null
