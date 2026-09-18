#!/usr/bin/env python3
"""initContainer: download the weka traces, filter, split one file per trace.

Filtering is deliberately ONE content rule, so the corpus is easy to
reproduce and audit:

    keep a trace if its total request count (turns, including nested
    subagent requests) is <= MAX_TURNS (default 400)

Reason for that one rule: datagen compiles every trace into a full event
graph with synthesized prompts BEFORE replay starts, so a 1418-turn trace
(the dataset also contains a 10,393-turn one) costs disproportionate memory
and compile time. It is a resource guard, not a workload judgement. On the
first 60MB it keeps 35 of 39 traces (90%).

There is deliberately NO input-token filter. The dataset is already
256k-capped (see its name) and the served model's window is 262,144, and
measured server-side re-tokenization drift is only ~0.24% (a trace recorded
at <=245,000 counted 245,592 server-side), so recorded-256k prompts fit with
room to spare. An earlier 245,000-token rule dropped 33% of the corpus for
no benefit - and corpus size is the binding constraint on sustainable
concurrency, so that cost was real.

Mechanical (non-content) exclusions: the last line of a byte-range download
is truncated, and any line that fails to parse is skipped. Both are recorded
in the manifest.

Output: OUT_DIR/trace_<idx>.json (one JSON object per file; the v0.7.0
loader globs `*.json`) plus MANIFEST with the download sha256 and, for every
line, its turns / max input tokens / keep decision - so the exact corpus can
be verified or re-derived by anyone.

Env: SLICE_BYTES (default 700MB = whole file), MAX_TURNS (400),
MAX_TRACES (0 = no cap; smoke sets a small number), OUT_DIR (/data/traces),
MANIFEST (/results/trace-manifest.json).
"""
import hashlib
import json
import os
import urllib.request

URL = ("https://huggingface.co/datasets/semianalysisai/"
       "cc-traces-weka-with-subagents-060826-256k/resolve/main/traces.jsonl")

# 700MB range end is past EOF, i.e. the whole 640MB file. A bigger corpus is
# required to SUSTAIN concurrency: sessions finish and must be replaced, and
# measured session durations imply corpus >= ~3x the target concurrency.
SLICE_BYTES = int(os.environ.get("SLICE_BYTES", 700_000_000))
MAX_TURNS = int(os.environ.get("MAX_TURNS", 400))
MAX_TRACES = int(os.environ.get("MAX_TRACES", 0))
OUT_DIR = os.environ.get("OUT_DIR", "/data/traces")
MANIFEST = os.environ.get("MANIFEST", "/results/trace-manifest.json")


def walk_requests(reqs):
    """Yield every request dict, descending into subagent entries."""
    for r in reqs:
        if r.get("type") == "subagent":
            yield from walk_requests(r.get("requests", []))
        else:
            yield r


def handle_line(idx, line, kept, stats):
    """Parse one trace line, apply the single rule, write it if kept."""
    try:
        trace = json.loads(line)
    except json.JSONDecodeError:
        stats.append({"idx": idx, "kept": False, "reason": "bad json"})
        return kept
    reqs = list(walk_requests(trace.get("requests", [])))
    turns = len(reqs)
    max_in = max((r.get("in", 0) for r in reqs), default=0)
    # The one content rule; max_in is recorded for auditing but not used.
    keep = turns <= MAX_TURNS and (MAX_TRACES == 0 or kept < MAX_TRACES)
    stats.append({"idx": idx, "kept": keep, "turns": turns, "max_in": max_in})
    if keep:
        with open(os.path.join(OUT_DIR, f"trace_{idx:04d}.json"), "wb") as f:
            f.write(line + b"\n")
        kept += 1
    return kept


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)

    # Stream: the full corpus is 640MB, so never hold it in memory. Keeps RSS
    # to roughly one trace line (~1.5MB) instead of ~2GB.
    req = urllib.request.Request(URL, headers={"Range": f"bytes=0-{SLICE_BYTES - 1}"})
    sha = hashlib.sha256()
    nbytes = idx = kept = 0
    stats = []
    buf = b""
    with urllib.request.urlopen(req, timeout=1800) as resp:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            sha.update(chunk)
            nbytes += len(chunk)
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                kept = handle_line(idx, line, kept, stats)
                idx += 1
    # Whatever remains in buf has no trailing newline: either a range-truncated
    # line or (for a whole-file read) a final line without EOL. Dropped either
    # way and recorded, so the corpus is exactly "complete lines".
    trailing = len(buf)
    digest = sha.hexdigest()
    print(f"downloaded {nbytes} bytes, sha256={digest}, {idx} complete lines, "
          f"{trailing} trailing bytes discarded")

    with open(MANIFEST, "w") as f:
        json.dump({"url": URL, "slice_bytes": SLICE_BYTES, "downloaded_bytes": nbytes,
                   "slice_sha256": digest, "trailing_bytes_discarded": trailing,
                   "filter_rule": f"turns <= {MAX_TURNS}",
                   "max_turns": MAX_TURNS, "max_traces": MAX_TRACES,
                   "complete_lines": idx, "kept": kept,
                   "traces": stats}, f, indent=2)
    print(f"kept {kept}/{idx} traces -> {OUT_DIR}")
    for s in [s for s in stats if not s["kept"]][:10]:
        print("dropped:", s)


if __name__ == "__main__":
    main()
