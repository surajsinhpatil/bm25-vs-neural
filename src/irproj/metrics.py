"""Ranking metrics, computed per query exactly as trec_eval / pytrec_eval define them.

Conventions (checked against pytrec_eval in tests/test_metrics.py):
  * documents are ordered by score desc, ties by docid desc (trec_eval order)
  * unjudged documents count as non-relevant
  * nDCG@k uses linear gain (grade) and log2(rank + 1) discount, ideal list from all qrels
  * binary metrics use grade >= `rel_level` (2 in this project)
  * MAP@k divides by the total number of relevant documents R (trec_eval's map_cut)
  * MRR@k is the reciprocal rank of the first relevant document within the top k
  * Recall@k is relative to the judged pool (only judged documents can be relevant)
  * Hole@k is the fraction of the top-k that was never judged [BEIR, Thakur et al. 2021]
  * sNDCG@k (exploratory) is nDCG@k with gain max(grade - 1, 0)
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence

import numpy as np

from .io import Qrels, Run, rank_docs

DEFAULT_METRICS = ("ndcg@10", "ndcg@5", "p@5", "mrr@10", "map@10", "recall@10", "hole@10")


def _ranked(scores: Dict[str, float]) -> List[str]:
    return [d for d, _ in rank_docs(scores)]


def ndcg_at_k(ranked: Sequence[str], judged: Dict[str, int], k: int) -> float:
    dcg = sum(max(judged.get(d, 0), 0) / math.log2(i + 2) for i, d in enumerate(ranked[:k]))
    ideal = sorted((g for g in judged.values() if g > 0), reverse=True)[:k]
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0


def strict_ndcg_at_k(ranked: Sequence[str], judged: Dict[str, int], k: int) -> float:
    """Exploratory variant: gain = max(grade - 1, 0), so grade-1 documents ('on topic but does not
    answer / breaks a condition') earn nothing. Not the pre-registered metric."""
    return ndcg_at_k(ranked, {d: max(g - 1, 0) for d, g in judged.items()}, k)


def precision_at_k(ranked, judged, k, rel_level):
    return sum(judged.get(d, 0) >= rel_level for d in ranked[:k]) / k


def recall_at_k(ranked, judged, k, rel_level):
    r = sum(g >= rel_level for g in judged.values())
    if r == 0:
        return 0.0
    return sum(judged.get(d, 0) >= rel_level for d in ranked[:k]) / r


def mrr_at_k(ranked, judged, k, rel_level):
    for i, d in enumerate(ranked[:k]):
        if judged.get(d, 0) >= rel_level:
            return 1.0 / (i + 1)
    return 0.0


def map_at_k(ranked, judged, k, rel_level):
    r = sum(g >= rel_level for g in judged.values())
    if r == 0:
        return 0.0
    hits, total = 0, 0.0
    for i, d in enumerate(ranked[:k]):
        if judged.get(d, 0) >= rel_level:
            hits += 1
            total += hits / (i + 1)
    return total / r


def hole_at_k(ranked, judged, k):
    top = ranked[:k]
    return sum(d not in judged for d in top) / k if top else 0.0


def per_query(run: Run, qrels: Qrels, metrics: Sequence[str] = DEFAULT_METRICS,
              rel_level: int = 2, qids: Sequence[str] | None = None) -> Dict[str, Dict[str, float]]:
    """metric -> {qid: value}. Queries present in qrels but missing from the run score 0."""
    qids = list(qids) if qids is not None else sorted(qrels)
    out: Dict[str, Dict[str, float]] = {m: {} for m in metrics}
    for qid in qids:
        judged = qrels.get(qid, {})
        ranked = _ranked(run.get(qid, {}))
        for m in metrics:
            name, k = m.split("@")
            k = int(k)
            if name == "ndcg":
                v = ndcg_at_k(ranked, judged, k)
            elif name == "sndcg":
                v = strict_ndcg_at_k(ranked, judged, k)
            elif name == "p":
                v = precision_at_k(ranked, judged, k, rel_level)
            elif name == "recall":
                v = recall_at_k(ranked, judged, k, rel_level)
            elif name == "mrr":
                v = mrr_at_k(ranked, judged, k, rel_level)
            elif name == "map":
                v = map_at_k(ranked, judged, k, rel_level)
            elif name == "hole":
                v = hole_at_k(ranked, judged, k)
            else:
                raise ValueError(f"unknown metric {m}")
            out[m][qid] = v
    return out


def mean(values: Dict[str, float]) -> float:
    return float(np.mean(list(values.values()))) if values else float("nan")


def summarize(pq: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    return {m: mean(v) for m, v in pq.items()}
