"""RQ5: BM25 sensitivity to k1 and b, with 5-fold cross-validation over queries.

The sweep itself is a sensitivity analysis only. The only *tuned* BM25 number we report is
the cross-validated one: for each fold the best (k1, b) is picked on the other 4 folds and
evaluated on the held-out fold. Folds are stratified by query category.

    python scripts/bm25_sweep.py --corpus data/corpus/cscr.jsonl --topics data/queries/topics.jsonl \
        --qrels data/qrels/qrels.txt --out results --figures report/figures --tables report/tables
"""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

import numpy as np

from irproj import report as R
from irproj.bm25 import BM25Index
from irproj.io import doc_text, load_corpus, load_topics, read_qrels
from irproj.metrics import per_query
from irproj.tokenize import get_analyzer

ap = argparse.ArgumentParser()
ap.add_argument("--corpus", required=True)
ap.add_argument("--topics", required=True)
ap.add_argument("--qrels", required=True)
ap.add_argument("--analyzer", default="id")
ap.add_argument("--metric", default="ndcg@10")
ap.add_argument("--folds", type=int, default=5)
ap.add_argument("--seed", type=int, default=11)
ap.add_argument("--out", default="results")
ap.add_argument("--figures", default="report/figures")
ap.add_argument("--tables", default="report/tables")
ap.add_argument("--label", default="")
a = ap.parse_args()

K1S = np.round(np.arange(0.4, 2.01, 0.2), 2)
BS = np.array(sorted(set(np.round(np.arange(0.0, 1.01, 0.1), 2).tolist()) | {0.75}))  # includes the default b

ids, docs = load_corpus(a.corpus)
qrels = read_qrels(a.qrels)
topics = [t for t in load_topics(a.topics) if t["qid"] in qrels]
qids = [t["qid"] for t in topics]
queries = {t["qid"]: t["query"] for t in topics}
index = BM25Index(get_analyzer(a.analyzer)).build(ids, (doc_text(d) for d in docs))

scores = {}                                   # (k1, b) -> {qid: metric}
grid = np.zeros((len(K1S), len(BS)))
for i, k1 in enumerate(K1S):
    for j, b in enumerate(BS):
        run, _ = index.batch_search(queries, k=100, k1=float(k1), b=float(b))
        pq = per_query(run, qrels, (a.metric,), qids=qids)[a.metric]
        scores[(float(k1), float(b))] = pq
        grid[i, j] = np.mean(list(pq.values()))
    print(f"k1={k1:.1f} done, best so far {grid[:i+1].max():.4f}")

# stratified folds
by_cat = defaultdict(list)
for t in topics:
    by_cat[t["category"]].append(t["qid"])
rng = random.Random(a.seed)
fold_of = {}
for c, qs in by_cat.items():
    qs = sorted(qs)
    rng.shuffle(qs)
    for i, q in enumerate(qs):
        fold_of[q] = i % a.folds
cv_values, chosen = {}, []
for f in range(a.folds):
    train = [q for q in qids if fold_of[q] != f]
    test = [q for q in qids if fold_of[q] == f]
    best = max(scores, key=lambda p: (np.mean([scores[p][q] for q in train]), -abs(p[0] - 1.2) - abs(p[1] - 0.75)))
    chosen.append({"fold": f, "k1": best[0], "b": best[1],
                   "train": float(np.mean([scores[best][q] for q in train]))})
    for q in test:
        cv_values[q] = scores[best][q]

default = scores[(1.2, 0.75)]
best_overall = max(scores, key=lambda p: np.mean(list(scores[p].values())))
res = {
    "analyzer": a.analyzer, "metric": a.metric, "k1_grid": K1S.tolist(), "b_grid": BS.tolist(),
    "grid": grid.tolist(),
    "default_k1_1.2_b_0.75": float(np.mean(list(default.values()))),
    "oracle_best": {"k1": best_overall[0], "b": best_overall[1],
                    "value": float(np.mean(list(scores[best_overall].values()))),
                    "note": "tuned on the test queries, NOT a fair number - sensitivity only"},
    "cv_5fold": float(np.mean([cv_values[q] for q in qids])),
    "cv_per_query": cv_values,
    "cv_chosen": chosen,
    "range": [float(grid.min()), float(grid.max())],
}
Path(a.out).mkdir(parents=True, exist_ok=True)
Path(a.out, f"bm25_sweep{a.label}.json").write_text(json.dumps(res, indent=2))
R.heatmap(Path(a.figures) / f"bm25_sweep{a.label}.pdf", K1S, BS, grid,
          marks={"default": (1.2, 0.75), "best": best_overall}, label=R.METRIC_NAMES.get(a.metric, a.metric))
rows = [["Default ($k_1$=1.2, $b$=0.75)", R.fmt(res["default_k1_1.2_b_0.75"])],
        [f"5-fold CV (stratified)", R.fmt(res["cv_5fold"])],
        [f"Oracle best ($k_1$={best_overall[0]}, $b$={best_overall[1]}), not fair", R.fmt(res["oracle_best"]["value"])],
        ["Range over the grid", f"{grid.min():.3f}--{grid.max():.3f}"]]
R.write(Path(a.tables) / f"bm25_sweep{a.label}.tex", R.latex_table(
    rows, ["BM25 setting", R.METRIC_NAMES.get(a.metric, a.metric)], "lc",
    "BM25 parameter sensitivity ($k_1\\in[0.4,2.0]$, $b\\in[0,1]$).", f"tab:sweep{a.label}"))
print(json.dumps({k: v for k, v in res.items() if k not in ("grid", "cv_per_query")}, indent=2))
