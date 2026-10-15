"""Add the arms and points of one bundle (export_bundle.py output) to a dashboard bundle, and update index.json.

  python3 dashboard/merge_bundle.py dashboard/data/glm52-nvfp4-8xb200.json /tmp/dep8.json \\
      --name dep8-direct="DEP=8, no-router ..." --cpu-tier-tokens 18173440 \\
      --rename no-router="TP=8, no-router + offload" --title "..." --description-append "..."

A point whose id is already in the target replaces it. --cpu-tier-tokens sets cpu_tier_tokens of the added points
(export_bundle.py computes it from --kv-offloading-size, which is per rank under data parallel). --rename changes
the display name of an arm in the target.

Used for (2026-10-15): step 27 DEP=8 points into the GLM bundle:
  uv run export_bundle.py --out /tmp/dep8-bundle/dep8.json --title x --arm dep8-affinity-retry=dep8-affinity \\
      --arm dep8-affinity-r2=dep8-affinity --replicate-suffix 'NOSUFFIX$' --kv-bytes-per-token 48408 \\
      27-glm52-dep8/b200/results/{dep8-direct/c24,c32,c48,c64, dep8-affinity/c24, dep8-affinity-r2/c32,
      dep8-affinity/c48, dep8-affinity-retry/c64, dep8-thunder-l10/c24,c32,c48,c64}
  CPU tier 18,173,440 = 8 ranks x 35,495 chunks x 64 tokens (measured), the same total as TP=8.
"""
import argparse, json
from datetime import datetime, timezone
from pathlib import Path

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("target", type=Path)
ap.add_argument("source", type=Path)
ap.add_argument("--name", action="append", default=[], help="ARM=TEXT display name of an added arm")
ap.add_argument("--rename", action="append", default=[], help="ARM=TEXT new display name of a target arm")
ap.add_argument("--cpu-tier-tokens", type=int)
ap.add_argument("--title")
ap.add_argument("--description-append", default="")
args = ap.parse_args()

target, source = json.load(open(args.target)), json.load(open(args.source))
names, renames = (dict(x.split("=", 1) for x in xs) for xs in (args.name, args.rename))
for arm in target["arms"]:
    arm["name"] = renames.get(arm["id"], arm["name"])
known = {a["id"] for a in target["arms"]}
for arm in source["arms"]:
    if arm["id"] not in known:
        target["arms"].append({"id": arm["id"], "name": names.get(arm["id"], arm["name"]), "baseline": False})
added = {p["id"] for p in source["points"]}
target["points"] = [p for p in target["points"] if p["id"] not in added]
for p in source["points"]:
    if args.cpu_tier_tokens:
        p["cpu_tier_tokens"] = args.cpu_tier_tokens
    target["points"].append(p)
order = [a["id"] for a in target["arms"]]
target["points"].sort(key=lambda p: (order.index(p["arm"]), p["conc"]))
if args.title:
    target["title"] = args.title
if args.description_append:
    target["description"] = target["description"].rstrip() + " " + args.description_append
target["created_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
json.dump(target, open(args.target, "w"), separators=(",", ":"))

index_path = args.target.parent / "index.json"
index = json.load(open(index_path))
for entry in index:
    if entry["file"] == args.target.name:
        entry.update(title=target["title"], created_utc=target["created_utc"], points=len(target["points"]))
json.dump(index, open(index_path, "w"), indent=1)
print(f"{args.target}: {len(target['arms'])} arms, {len(target['points'])} points")
