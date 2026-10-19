"""S4: convex combination (CC) of min-max normalised BM25 and dense scores [Bruch et al. 2023],
with the weight alpha chosen by 5-fold cross-validation over queries (stratified by category).
The output run is assembled from the held-out folds, so no query is scored with an alpha
tuned on itself.

    python scripts/stretch_cc_fusion.py --lexical runs/bm25.run --dense runs/e5.run \
        --topics data/queries/topics.jsonl --qrels data/qrels/qrels.txt --out runs/cc-bm25+e5.run
"""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

import numpy as np

from irproj.fusion import convex_combination
from irproj.io import load_topics, read_qrels, require_qrels, read_run, write_run
from irproj.metrics import per_query

ap = argparse.ArgumentParser()
ap.add_argument("--lexical", required=True)
ap.add_argument("--dense", required=True)
ap.add_argument("--topics", required=True)
ap.add_argument("--qrels", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--folds", type=int, default=5)
ap.add_argument("--seed", type=int, default=11)
a = ap.parse_args()

lex, den = read_run(a.lexical), read_run(a.dense)
qrels = require_qrels(a.qrels)
topics = [t for t in load_topics(a.topics) if t["qid"] in qrels]
qids = [t["qid"] for t in topics]
alphas = np.round(np.arange(0, 1.01, 0.05), 2)
runs = {al: convex_combination(lex, den, float(al)) for al in alphas}
score = {al: per_query(runs[al], qrels, ("ndcg@10",), qids=qids)["ndcg@10"] for al in alphas}

by_cat = defaultdict(list)
for t in topics:
    by_cat[t["category"]].append(t["qid"])
rng = random.Random(a.seed)
fold = {}
for c, qs in by_cat.items():
    qs = sorted(qs)
    rng.shuffle(qs)
    for i, q in enumerate(qs):
        fold[q] = i % a.folds
final, chosen = {}, []
for f in range(a.folds):
    train = [q for q in qids if fold[q] != f]
    best = max(alphas, key=lambda al: (np.mean([score[al][q] for q in train]), -abs(al - 0.5)))
    chosen.append(float(best))
    for q in qids:
        if fold[q] == f:
            final[q] = runs[best][q]
write_run(a.out, final, Path(a.out).stem)
res = {"alphas_per_fold": chosen,
       "cv_ndcg@10": float(np.mean(list(per_query(final, qrels, ("ndcg@10",), qids=qids)["ndcg@10"].values()))),
       "curve": {float(al): float(np.mean(list(score[al].values()))) for al in alphas}}
Path(a.out + ".cv.json").write_text(json.dumps(res, indent=2))
print(json.dumps(res, indent=2))
