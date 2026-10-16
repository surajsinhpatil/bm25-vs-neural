"""Hybrid retrieval by combining ranked lists.

* RRF  [Cormack et al. 2009]: score(d) = sum_r 1 / (k + rank_r(d)), k = 60 fixed in advance,
  over the top `depth` results of each run. Only ranks are used, so BM25 scores and cosine
  similarities never have to be put on the same scale.
* CC   [Bruch et al. 2023]: convex combination  a * norm(lexical) + (1 - a) * norm(dense)
  with per-query min-max normalisation; `a` is tuned by cross-validation (stretch goal S4).
"""
from __future__ import annotations

from typing import Dict, List

from .io import Run, rank_docs


def rrf(runs: List[Run], k: int = 60, depth: int = 100, out_depth: int = 1000) -> Run:
    fused: Run = {}
    qids = set().union(*[r.keys() for r in runs])
    for qid in qids:
        acc: Dict[str, float] = {}
        for run in runs:
            for rank, (docid, _) in enumerate(rank_docs(run.get(qid, {}))[:depth], start=1):
                acc[docid] = acc.get(docid, 0.0) + 1.0 / (k + rank)
        fused[qid] = dict(rank_docs(acc)[:out_depth])
    return fused


def _minmax(scores: Dict[str, float]) -> Dict[str, float]:
    if not scores:
        return {}
    lo, hi = min(scores.values()), max(scores.values())
    if hi - lo < 1e-12:
        return {d: 1.0 for d in scores}
    return {d: (s - lo) / (hi - lo) for d, s in scores.items()}


def convex_combination(lexical: Run, dense: Run, alpha: float, depth: int = 100,
                       out_depth: int = 1000) -> Run:
    fused: Run = {}
    for qid in set(lexical) | set(dense):
        lx = _minmax(dict(rank_docs(lexical.get(qid, {}))[:depth]))
        dn = _minmax(dict(rank_docs(dense.get(qid, {}))[:depth]))
        acc = {d: alpha * lx.get(d, 0.0) + (1 - alpha) * dn.get(d, 0.0) for d in set(lx) | set(dn)}
        fused[qid] = dict(rank_docs(acc)[:out_depth])
    return fused
