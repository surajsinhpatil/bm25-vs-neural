"""Step 2c: dense run from cached document embeddings.

    python scripts/run_dense.py --model e5 --index indexes/e5 --topics data/queries/topics.jsonl --out runs/e5.run
"""
import argparse
import json
import time
from pathlib import Path

from irproj.dense import DenseIndex, encoder_from_args
from irproj.efficiency import latency_summary, save_efficiency
from irproj.io import load_topics, write_run

ap = argparse.ArgumentParser()
ap.add_argument("--model", choices=["e5", "specter2"], required=True)
ap.add_argument("--index", required=True)
ap.add_argument("--topics", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--depth", type=int, default=1000)
ap.add_argument("--device", default=None)
ap.add_argument("--model-name", default=None)
ap.add_argument("--adapters", nargs=2, default=None, metavar=("DOC", "QUERY"))
ap.add_argument("--include-practice", action="store_true")
a = ap.parse_args()

enc = encoder_from_args(a.model, a.model_name, a.adapters, a.device)
index = DenseIndex.load(a.index)
topics = load_topics(a.topics, include_practice=a.include_practice)
qids = [t["qid"] for t in topics]

# per-query latency = encoding the query on its own + exact search
enc.encode_queries(["warm up"], batch_size=1)
enc_lat, q_emb = [], []
for t in topics:
    t0 = time.perf_counter()
    q_emb.append(enc.encode_queries([t["query"]], batch_size=1)[0])
    enc_lat.append(time.perf_counter() - t0)
import numpy as np
run, search_lat = index.search(np.stack(q_emb), qids, k=a.depth)
write_run(a.out, run, a.model, a.depth)

encode_info = {}
p = Path(a.index + ".encode.json")
if p.exists():
    encode_info = json.loads(p.read_text())
total = [x + y for x, y in zip(enc_lat, search_lat)]
save_efficiency(a.out + ".eff.json", {
    "system": a.model, "n_docs": len(index.doc_ids), "index_mb": round(index.index_bytes() / 2**20, 2),
    "index_seconds": encode_info.get("seconds"), "hardware": encode_info.get("gpu", str(enc.device)),
    "truncated_pct": encode_info.get("truncated_pct"), "query_device": str(enc.device),
    **latency_summary(total),
    "search_only_mean_ms": latency_summary(search_lat)["mean_ms"]})
print(f"{a.model}: {len(run)} queries -> {a.out}")
