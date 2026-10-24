"""Efficiency table from the measurement logs written by the run scripts (<run>.eff.json).
Nothing is re-measured or estimated here; missing values stay missing.

    python scripts/efficiency_report.py --out deliverables/efficiency
"""
import argparse
import csv
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--runs-dir", default="runs")
ap.add_argument("--out", default="deliverables/efficiency")
a = ap.parse_args()

SYS = [("bm25", "BM25"), ("e5", "E5"), ("specter2", "SPECTER2"), ("bm25+e5", "BM25+E5"),
       ("bm25+specter2", "BM25+SPECTER2"), ("ce", "Cross-encoder re-rank (S1, top-100 of BM25+E5)")]
rows = []
for s, name in SYS:
    p = Path(a.runs_dir) / f"{s}.run.eff.json"
    if not p.exists():
        continue
    e = json.loads(p.read_text())
    rows.append({"system": name, "index_seconds": e.get("index_seconds"), "index_mb": e.get("index_mb"),
                 "query_mean_ms": e.get("mean_ms"), "query_median_ms": e.get("median_ms"),
                 "query_p95_ms": e.get("p95_ms"), "search_only_mean_ms": e.get("search_only_mean_ms"),
                 "fusion_mean_ms": e.get("fusion_mean_ms"), "hardware": e.get("hardware") or "",
                 "source": str(p)})
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
with open(out / "efficiency.csv", "w", newline="") as f:
    w = csv.DictWriter(f, lineterminator="\n", fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
fmt = lambda v, d=1: "–" if v is None else f"{v:,.{d}f}"
L = ["# Efficiency (measured)", "",
     "| System | Index build (s) | Index size (MB) | Query mean (ms) | Query p95 (ms) | Hardware |",
     "|---|---|---|---|---|---|"]
for r in rows:
    L.append(f"| {r['system']} | {fmt(r['index_seconds'])} | {fmt(r['index_mb'])} | {fmt(r['query_mean_ms'])} | "
             f"{fmt(r['query_p95_ms'])} | {r['hardware']} |")
L += ["", "## How these were measured", "",
      "- All numbers come from the logs the run scripts wrote during the Kaggle run of 19 Oct 2026 "
      "(`runs/*.run.eff.json`); nothing is estimated.",
      "- Corpus: 39,613 cs.CR abstracts; 50 test queries, each timed separately with `time.perf_counter()`.",
      "- **BM25**: index build = tokenising the corpus and building the sparse term-document matrix, one CPU "
      "process (the Kaggle CPU model was not logged). Size = postings (data, indices, pointers) + document "
      "lengths + vocabulary in memory. Query time = tokenising the query + sparse matrix-vector product + top-1000.",
      "- **E5 / SPECTER2**: index build = encoding all abstracts on one Tesla T4 GPU in fp16, length-sorted "
      "batches. Size = 39,613 × 768 float32 vectors. Query time = encoding the query alone on the GPU "
      "(batch size 1, after one warm-up) + exact cosine search over all vectors on the CPU + top-1000; "
      f"the search part alone was {fmt(rows[1]['search_only_mean_ms'])} ms (E5) and "
      f"{fmt(rows[2]['search_only_mean_ms'])} ms (SPECTER2).",
      "- **Hybrids**: the logs hold the components' mean latencies plus the measured RRF time "
      f"(about {fmt(rows[3]['fusion_mean_ms'], 2)} ms); hybrid time = BM25 + dense + fusion, i.e. the components run "
      "one after the other. Running them in parallel would cost about the slower component. No p95 for hybrids.",
      "- **Cross-encoder (stretch S1)**: re-ranking time only (100 query–document pairs on the T4); add the "
      "BM25+E5 time for the full pipeline.",
      "- Not measured: CPU-only dense encoding, memory of a production ANN index, or throughput under load.", ""]
(out / "efficiency.md").write_text("\n".join(L))
print("\n".join(L))
