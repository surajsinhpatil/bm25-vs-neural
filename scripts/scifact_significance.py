"""Significance tests and bootstrap CIs for the five systems on BEIR SciFact (300 judged queries).
Gives a judged comparison against the BM25 baseline independent of our own judging.

    python scripts/scifact_significance.py --runs-dir runs/scifact --qrels data/beir/scifact.test.qrels.txt

The SciFact qrels ship with Pyserini:  pyserini.search.get_qrels('beir-v1.0.0-scifact-test')
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from irproj import report as R
from irproj.io import read_qrels, read_run
from irproj.metrics import per_query
from irproj.stats import bootstrap_ci, pairwise_tests

ap = argparse.ArgumentParser()
ap.add_argument("--runs-dir", default="runs/scifact")
ap.add_argument("--qrels", default="data/beir/scifact.test.qrels.txt")
ap.add_argument("--systems", nargs="+", default=["bm25", "e5", "specter2", "bm25+e5", "bm25+specter2"])
ap.add_argument("--metric", default="ndcg@10")
ap.add_argument("--n-perm", type=int, default=100_000)
ap.add_argument("--out", default="results")
ap.add_argument("--tables", default="report/tables")
a = ap.parse_args()

qrels = read_qrels(a.qrels)
if not qrels:
    raise SystemExit(f"{a.qrels} is empty")
qids = sorted(qrels)
pq = {s: per_query(read_run(Path(a.runs_dir) / f"{s}.run"), qrels, (a.metric,), rel_level=1, qids=qids)[a.metric]
      for s in a.systems}
ci = {s: bootstrap_ci([pq[s][q] for q in qids]) for s in a.systems}
tests = pairwise_tests(pq, a.systems, n_perm=a.n_perm)
# share of queries where each system beats / ties / loses to BM25
wtl = {}
for s in a.systems:
    if s == "bm25":
        continue
    d = np.array([pq[s][q] - pq["bm25"][q] for q in qids])
    wtl[s] = {"win": int((d > 1e-9).sum()), "tie": int((np.abs(d) <= 1e-9).sum()), "loss": int((d < -1e-9).sum())}

res = {"n_queries": len(qids), "metric": a.metric,
       "ci": {s: {"mean": m, "low": lo, "high": hi} for s, (m, lo, hi) in ci.items()},
       "tests": tests, "win_tie_loss_vs_bm25": wtl}
Path(a.out).mkdir(parents=True, exist_ok=True)
Path(a.out, "scifact_significance.json").write_text(json.dumps(res, indent=2))

name = R.METRIC_NAMES.get(a.metric, a.metric)
key = {("bm25", "e5"), ("bm25", "specter2"), ("e5", "specter2"), ("bm25", "bm25+e5"), ("e5", "bm25+e5"),
       ("bm25", "bm25+specter2"), ("specter2", "bm25+specter2")}
rows = []
for t in tests:
    if (t["a"], t["b"]) not in key:
        continue
    # report as (second minus first) so that "X vs BM25" reads as X's gain
    rows.append([f"{R.pretty(t['b'])} $-$ {R.pretty(t['a'])}", f"{-t['diff']:+.3f}", R.fmt(t["p_holm"], 4),
                 "yes" if t["significant"] else "no"])
R.write(Path(a.tables) / "scifact_significance.tex", R.latex_table(
    rows, [r"Comparison on SciFact", r"$\Delta$" + name, r"$p_{\text{Holm}}$", "Sig."], "lccc",
    f"Paired randomisation tests on SciFact {name} ({len(qids)} queries, {a.n_perm:,} permutations, "
    "Holm over all 10 pairs).", "tab:scisig"))
for s, (m, lo, hi) in ci.items():
    print(f"{s:14s} {m:.3f} [{lo:.3f}, {hi:.3f}]")
for t in tests:
    print(f"{t['a']:>14s} vs {t['b']:<14s} diff={t['diff']:+.3f} p={t['p']:.5f} p_holm={t['p_holm']:.5f} {'*' if t['significant'] else ''}")
print(wtl)
