"""Check our metric code against pytrec_eval (trec_eval) on the actual runs and qrels.

For every run and every query, compares nDCG@5/10, P@5, MAP@10, Recall@10 and MRR@10.
Exit code 1 if any per-query value differs by more than 1e-9.

    python scripts/validate_metrics.py --qrels <qrels> --topics data/queries/topics.jsonl --runs runs/*.run
"""
import argparse
import json
import sys
from pathlib import Path

import pytrec_eval

from irproj.io import load_topics, rank_docs, read_qrels, read_run
from irproj.metrics import per_query

ap = argparse.ArgumentParser()
ap.add_argument("--qrels", required=True)
ap.add_argument("--topics", required=True)
ap.add_argument("--runs", nargs="+", required=True)
ap.add_argument("--rel-level", type=int, default=2)
ap.add_argument("--out", default=None)
a = ap.parse_args()

qrels = read_qrels(a.qrels)
qids = [t["qid"] for t in load_topics(a.topics) if t["qid"] in qrels]
ev = pytrec_eval.RelevanceEvaluator({q: qrels[q] for q in qids}, {"ndcg_cut.5,10", "P.5", "map_cut.10", "recall.10"},
                                    relevance_level=a.rel_level)
rr = pytrec_eval.RelevanceEvaluator({q: qrels[q] for q in qids}, {"recip_rank"}, relevance_level=a.rel_level)
pairs = {"ndcg@10": "ndcg_cut_10", "ndcg@5": "ndcg_cut_5", "p@5": "P_5", "map@10": "map_cut_10", "recall@10": "recall_10"}
report, worst = {}, 0.0
for p in a.runs:
    run = {q: v for q, v in read_run(p).items() if q in qids}
    ours = per_query(run, qrels, tuple(pairs) + ("mrr@10",), a.rel_level, qids)
    ref = ev.evaluate(run)
    top10 = {q: dict(rank_docs(r)[:10]) for q, r in run.items()}
    ref_rr = rr.evaluate(top10)
    d = {m: max(abs(ours[m][q] - ref[q][t]) for q in qids) for m, t in pairs.items()}
    d["mrr@10"] = max(abs(ours["mrr@10"][q] - ref_rr[q]["recip_rank"]) for q in qids)
    report[Path(p).stem] = d
    worst = max(worst, max(d.values()))
    print(f"{Path(p).stem:16s} max |ours - trec_eval| per query: " + "  ".join(f"{m}={v:.1e}" for m, v in d.items()))
res = {"qrels": a.qrels, "queries": len(qids), "max_abs_diff": worst, "per_run": report, "pass": worst < 1e-9}
if a.out:
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=2))
print("PASS" if res["pass"] else "FAIL", f"(largest difference {worst:.1e} over {len(qids)} queries x {len(a.runs)} runs)")
sys.exit(0 if res["pass"] else 1)
