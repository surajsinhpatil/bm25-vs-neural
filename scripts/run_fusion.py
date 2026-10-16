"""Step 2d: hybrid run with Reciprocal Rank Fusion (k = 60, top-100 of each run).

    python scripts/run_fusion.py --runs runs/bm25.run runs/e5.run --tag bm25+e5 --out runs/bm25+e5.run
"""
import argparse
import json
import time
from pathlib import Path

from irproj.efficiency import save_efficiency
from irproj.fusion import rrf
from irproj.io import read_run, write_run

ap = argparse.ArgumentParser()
ap.add_argument("--runs", nargs="+", required=True)
ap.add_argument("--k", type=int, default=60)
ap.add_argument("--depth", type=int, default=100)
ap.add_argument("--tag", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()

runs = [read_run(p) for p in a.runs]
t0 = time.perf_counter()
fused = rrf(runs, k=a.k, depth=a.depth)
fuse_ms = 1000 * (time.perf_counter() - t0) / max(len(fused), 1)
write_run(a.out, fused, a.tag)

# latency of a hybrid = components (run in parallel in a real system we take the sum, conservative)
parts = []
for p in a.runs:
    ep = Path(p + ".eff.json")
    if ep.exists():
        parts.append(json.loads(ep.read_text()))
rec = {"system": a.tag, "components": [p.get("system") for p in parts], "fusion_mean_ms": fuse_ms}
if parts:
    rec["mean_ms"] = sum(p.get("mean_ms", 0) or 0 for p in parts) + fuse_ms
    rec["index_mb"] = sum(p.get("index_mb", 0) or 0 for p in parts)
    rec["index_seconds"] = sum(p.get("index_seconds", 0) or 0 for p in parts)
save_efficiency(a.out + ".eff.json", rec)
print(f"{a.tag}: fused {len(a.runs)} runs -> {a.out}")
