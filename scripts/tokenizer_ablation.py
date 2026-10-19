"""RQ5 / innovation 3: effect of identifier-aware tokenisation, stemming and stopwords on BM25.

Every variant runs with k1 = 1.2, b = 0.75. Variants other than the main BM25 run were not
in the judging pool, so Hole@10 is reported next to each score; unjudged documents count as
non-relevant (judge them in an extra round with make_pool.py --already-judged if Hole is high).

    python scripts/tokenizer_ablation.py --corpus data/corpus/cscr.jsonl --topics data/queries/topics.jsonl \
        --qrels data/qrels/qrels.txt --out results --tables report/tables --runs-dir runs/ablation
"""
import argparse
import json
from pathlib import Path

import numpy as np

from irproj import report as R
from irproj.bm25 import BM25Index
from irproj.io import doc_text, load_corpus, load_topics, read_qrels, require_qrels, write_run
from irproj.metrics import per_query
from irproj.stats import paired_randomization_test
from irproj.tokenize import ANALYZERS

ap = argparse.ArgumentParser()
ap.add_argument("--corpus", required=True)
ap.add_argument("--topics", required=True)
ap.add_argument("--qrels", required=True)
ap.add_argument("--variants", nargs="+", default=list(ANALYZERS))
ap.add_argument("--out", default="results")
ap.add_argument("--tables", default="report/tables")
ap.add_argument("--runs-dir", default="runs/ablation")
ap.add_argument("--label", default="")
a = ap.parse_args()

ids, docs = load_corpus(a.corpus)
qrels = require_qrels(a.qrels)
topics = [t for t in load_topics(a.topics) if t["qid"] in qrels]
qids = [t["qid"] for t in topics]
cat = {t["qid"]: t["category"] for t in topics}
queries = {t["qid"]: t["query"] for t in topics}
texts = [doc_text(d) for d in docs]

res, pq_all = {}, {}
for v in a.variants:
    idx = BM25Index(ANALYZERS[v]).build(ids, texts)
    run, _ = idx.batch_search(queries, k=1000)
    write_run(Path(a.runs_dir) / f"bm25-{v}.run", run, f"bm25-{v}")
    pq = per_query(run, qrels, ("ndcg@10", "mrr@10", "hole@10"), qids=qids)
    pq_all[v] = pq
    res[v] = {"vocab": len(idx.vocab), "index_mb": idx.index_bytes() / 2**20,
              "ndcg@10": float(np.mean(list(pq["ndcg@10"].values()))),
              "mrr@10": float(np.mean(list(pq["mrr@10"].values()))),
              "hole@10": float(np.mean(list(pq["hole@10"].values()))),
              "ndcg@10_identifier": float(np.mean([pq["ndcg@10"][q] for q in qids if cat[q] == "identifier"] or [np.nan]))}
    print(v, json.dumps(res[v]))

ref = "id" if "id" in res else a.variants[0]
for v in res:
    if v != ref:
        d, p = paired_randomization_test([pq_all[v]["ndcg@10"][q] for q in qids],
                                         [pq_all[ref]["ndcg@10"][q] for q in qids])
        res[v]["diff_vs_main"], res[v]["p_vs_main"] = d, p
Path(a.out).mkdir(parents=True, exist_ok=True)
Path(a.out, f"tokenizer_ablation{a.label}.json").write_text(json.dumps(res, indent=2))

names = {"id": "Identifier-aware + Porter (main)", "plain": "Lucene-like + Porter",
         "id-nostem": "Identifier-aware, no stemming", "plain-nostem": "Lucene-like, no stemming",
         "id-nostop": "Identifier-aware, no stopwords"}
rows = [[names.get(v, v), f"{r['vocab']:,}", R.fmt(r["ndcg@10"]), R.fmt(r["ndcg@10_identifier"]),
         R.fmt(r["mrr@10"]), R.fmt(100 * r["hole@10"], 1) + r"\%", R.fmt(r.get("p_vs_main"), 3)]
        for v, r in res.items()]
R.write(Path(a.tables) / f"tokenizer_ablation{a.label}.tex", R.latex_table(
    rows, ["Analyzer", "Vocab.", "nDCG@10", "nDCG@10 (ident.)", "MRR@10", "Hole@10", "$p$ vs main"],
    "lcccccc", "Tokenisation ablation for BM25 ($k_1$=1.2, $b$=0.75).", f"tab:tok{a.label}"))
