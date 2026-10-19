"""Validation on BEIR SciFact (success criteria (i) and (ii) of the proposal) and a first
end-to-end comparison of all five systems on a collection that already has judgments.

  (i)  our BM25 vs Pyserini/Lucene BM25 with the same settings (k1=0.9, b=0.4, title+text,
       Lucene-like analyzer): nDCG@10 must agree within 0.01
  (ii) our metric code vs pytrec_eval on every run: per-query values must agree

    python scripts/validate_scifact.py --data data/beir --out results            # BM25 only (CPU)
    python scripts/validate_scifact.py --data data/beir --out results --dense    # + E5, SPECTER2, RRF (GPU)

`--dataset-dir` points at any BEIR-format folder (used by the offline tests).
"""
import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from irproj import beir
from irproj import report as R
from irproj.bm25 import BM25Index
from irproj.efficiency import latency_summary
from irproj.fusion import rrf
from irproj.io import doc_text, write_run
from irproj.metrics import per_query
from irproj.tokenize import get_analyzer

ap = argparse.ArgumentParser()
ap.add_argument("--dataset", default="scifact")
ap.add_argument("--data", default="data/beir")
ap.add_argument("--dataset-dir", default=None)
ap.add_argument("--k1", type=float, default=0.9)
ap.add_argument("--b", type=float, default=0.4)
ap.add_argument("--dense", action="store_true")
ap.add_argument("--no-pyserini", action="store_true")
ap.add_argument("--rel-level", type=int, default=1)
ap.add_argument("--out", default="results")
ap.add_argument("--runs-dir", default="runs/scifact")
ap.add_argument("--tables", default="report/tables")
ap.add_argument("--threads", type=int, default=4)
a = ap.parse_args()

path = Path(a.dataset_dir) if a.dataset_dir else beir.download(a.dataset, a.data)
docs, queries, qrels = beir.load(path)
ids = list(docs)
qids = sorted(queries)
print(f"{a.dataset}: {len(docs)} docs, {len(queries)} test queries")
METRICS = ("ndcg@10", "p@5", "mrr@10", "map@10", "recall@10")
runs, eff = {}, {}

# ------------------------------------------------------------------ our BM25 (Lucene-like settings)
for analyzer in ("plain", "id"):
    t0 = time.perf_counter()
    idx = BM25Index(get_analyzer(analyzer)).build(ids, (doc_text(docs[d]) for d in ids))
    t_index = time.perf_counter() - t0
    run, lat = idx.batch_search({q: queries[q] for q in qids}, k=1000, k1=a.k1, b=a.b)
    name = "bm25" if analyzer == "id" else "bm25-plain"
    runs[name] = beir.remove_identical(run)
    eff[name] = {"index_seconds": t_index, "index_mb": idx.index_bytes() / 2**20, **latency_summary(lat)}

# ------------------------------------------------------------------ Pyserini reference
def run_pyserini():
    from pyserini.search.lucene import LuceneSearcher
    work = Path(tempfile.mkdtemp(prefix="pyserini_"))
    (work / "docs").mkdir()
    with open(work / "docs" / "docs.jsonl", "w", encoding="utf-8") as f:
        for d in ids:
            f.write(json.dumps({"id": d, "contents": doc_text(docs[d])}) + "\n")
    t0 = time.perf_counter()
    subprocess.run([sys.executable, "-m", "pyserini.index.lucene", "--collection", "JsonCollection",
                    "--input", str(work / "docs"), "--index", str(work / "index"),
                    "--generator", "DefaultLuceneDocumentGenerator", "--threads", str(a.threads),
                    "--storeRaw"], check=True, capture_output=True)
    t_index = time.perf_counter() - t0
    searcher = LuceneSearcher(str(work / "index"))
    searcher.set_bm25(a.k1, a.b)
    run, lat = {}, []
    for q in qids:
        t0 = time.perf_counter()
        hits = searcher.search(queries[q], k=1000)
        lat.append(time.perf_counter() - t0)
        run[q] = {h.docid: float(h.score) for h in hits}
    runs["pyserini"] = beir.remove_identical(run)
    size = sum(p.stat().st_size for p in (work / "index").rglob("*") if p.is_file())
    eff["pyserini"] = {"index_seconds": t_index, "index_mb": size / 2**20, **latency_summary(lat)}



if not a.no_pyserini:
    try:
        run_pyserini()
    except Exception as e:  # Java / Pyserini problems should not stop the rest of the validation
        print(f"Pyserini step failed ({type(e).__name__}: {e}); continuing without the Lucene reference")

# ------------------------------------------------------------------ dense + hybrids (GPU)
if a.dense:
    from irproj.dense import DenseIndex, EncodeStats, get_encoder
    for m in ("e5", "specter2"):
        enc = get_encoder(m)
        st = EncodeStats()
        emb = enc.encode_docs([docs[d] for d in ids], stats=st)
        di = DenseIndex(ids, emb)
        t0 = time.perf_counter()
        qemb = enc.encode_queries([queries[q] for q in qids])
        q_ms = 1000 * (time.perf_counter() - t0) / len(qids)
        run, lat = di.search(qemb, qids, k=1000)
        runs[m] = beir.remove_identical(run)
        eff[m] = {"index_seconds": st.seconds, "index_mb": di.index_bytes() / 2**20,
                  "mean_ms": latency_summary(lat)["mean_ms"] + q_ms, "truncated_pct": st.as_dict()["truncated_pct"]}
        del enc
    runs["bm25+e5"] = rrf([runs["bm25"], runs["e5"]])
    runs["bm25+specter2"] = rrf([runs["bm25"], runs["specter2"]])

for name, run in runs.items():
    write_run(Path(a.runs_dir) / f"{name}.run", run, name)

# ------------------------------------------------------------------ evaluation + metric check
results = {}
for name, run in runs.items():
    pq = per_query(run, qrels, METRICS, a.rel_level, qids)
    results[name] = {m: float(np.mean(list(pq[m].values()))) for m in METRICS}
    results[name]["_pq"] = pq

check = {}
try:
    import pytrec_eval
    ev = pytrec_eval.RelevanceEvaluator(qrels, {"ndcg_cut.10", "P.5", "map_cut.10", "recall.10"},
                                        relevance_level=a.rel_level)
    rr = pytrec_eval.RelevanceEvaluator(qrels, {"recip_rank"}, relevance_level=a.rel_level)
    pairs = {"ndcg@10": "ndcg_cut_10", "p@5": "P_5", "map@10": "map_cut_10", "recall@10": "recall_10"}
    for name, run in runs.items():
        res = ev.evaluate(run)
        top10 = {q: dict(sorted(r.items(), key=lambda x: (x[1], x[0]), reverse=True)[:10]) for q, r in run.items()}
        res_rr = rr.evaluate(top10)
        diffs = {}
        for ours, theirs in pairs.items():
            diffs[ours] = max(abs(results[name]["_pq"][ours][q] - res[q][theirs]) for q in res)
        diffs["mrr@10"] = max(abs(results[name]["_pq"]["mrr@10"][q] - res_rr[q]["recip_rank"]) for q in res_rr)
        check[name] = diffs
except ImportError:
    print("pytrec_eval not installed: metric check skipped")

out = {"dataset": a.dataset, "n_docs": len(docs), "n_queries": len(qids), "k1": a.k1, "b": a.b,
       "results": {k: {m: v for m, v in r.items() if m != "_pq"} for k, r in results.items()},
       "efficiency": eff, "metric_check_max_abs_diff": check}
if "pyserini" in results:
    out["bm25_vs_pyserini_ndcg10_diff"] = results["bm25-plain"]["ndcg@10"] - results["pyserini"]["ndcg@10"]
    out["criterion_i_pass"] = abs(out["bm25_vs_pyserini_ndcg10_diff"]) <= 0.01
    from irproj.io import rank_docs
    ov, ratio = [], []
    for q in qids:
        ta = [d for d, _ in rank_docs(runs["bm25-plain"].get(q, {}))[:10]]
        tb = [d for d, _ in rank_docs(runs["pyserini"].get(q, {}))[:10]]
        if ta and tb:
            ov.append(len(set(ta) & set(tb)) / 10)
        ratio += [runs["bm25-plain"][q][d] / runs["pyserini"][q][d] for d in ta if d in runs["pyserini"].get(q, {})]
    out["bm25_vs_pyserini_top10_overlap"] = float(np.mean(ov))
    # Lucene drops the constant (k1 + 1) factor, so scores should differ by exactly that ratio
    out["bm25_vs_pyserini_score_ratio"] = {"mean": float(np.mean(ratio)), "sd": float(np.std(ratio)),
                                           "expected": a.k1 + 1}
if check:
    out["criterion_ii_pass"] = all(v < 1e-6 for d in check.values() for v in d.values())
Path(a.out).mkdir(parents=True, exist_ok=True)
Path(a.out, f"{a.dataset}_validation.json").write_text(json.dumps(out, indent=2))

order = [s for s in ["pyserini", "bm25-plain", "bm25", "e5", "specter2", "bm25+e5", "bm25+specter2"] if s in results]
rows = [[R.pretty(s)] + [R.fmt(results[s][m]) for m in ("ndcg@10", "p@5", "mrr@10", "map@10", "recall@10")]
        + [R.fmt(eff.get(s, {}).get("mean_ms"), 1)] for s in order]
R.write(Path(a.tables) / f"{a.dataset}.tex", R.latex_table(
    rows, ["System", "nDCG@10", "P@5", "MRR@10", "MAP@10", "R@10", "ms/query"], "lcccccc",
    f"BEIR {'SciFact' if a.dataset == 'scifact' else a.dataset} test set ({len(qids)} queries, {len(docs):,} abstracts); "
    f"BM25 with $k_1$={a.k1}, $b$={a.b}.", f"tab:{a.dataset}", bold_max_cols=range(1, 6)))
print(json.dumps({k: v for k, v in out.items() if k != "efficiency"}, indent=2))
