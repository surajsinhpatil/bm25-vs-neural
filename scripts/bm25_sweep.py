"""RQ5a: sensitivity of BM25 to k1 and b on the frozen cs.CR qrels (EXPLORATORY).

Design (fixed before any result was computed):
  * analyzer `id` (the main one), same corpus, queries, qrels and metric code as the main experiment
  * grid k1 in {0.2, 0.4, ..., 2.0} + {0.9}, b in {0.0, 0.1, ..., 1.0} + {0.75}  (132 settings)
  * primary metric nDCG@10; also condensed nDCG@10 (unjudged documents removed) and Hole@10,
    because only the default setting (k1=1.2, b=0.75) was in the judging pool
  * there is no separate tuning set, so the only tuned number reported is 5-fold cross-validated
    (folds stratified by category, seed 11; 20 further seeds as a robustness check). The best grid
    setting is reported as sensitivity only, never as a performance estimate.

    python scripts/bm25_sweep.py --corpus data/corpus/cscr.jsonl
Outputs: deliverables/rq5/sweep/ (CSV, JSON, metadata, figures) and report/tables/rq5_sweep.tex
"""
import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np

from irproj import report as R
from irproj import rq5
from irproj.bm25 import BM25Index
from irproj.io import doc_text, load_corpus, load_topics, require_qrels
from irproj.metrics import per_query
from irproj.stats import bootstrap_ci, paired_randomization_test
from irproj.tokenize import get_analyzer

ROOT = rq5.ROOT
ap = argparse.ArgumentParser()
ap.add_argument("--corpus", required=True)
ap.add_argument("--topics", default=str(ROOT / "data/queries/topics.jsonl"))
ap.add_argument("--qrels", default=str(ROOT / "data/qrels/qrels.txt"))
ap.add_argument("--expected-qrels-sha", default=None, help="default: data/qrels/qrels.sha256")
ap.add_argument("--expected-corpus", default=str(ROOT / "data/corpus/EXPECTED.json"),
                help="EXPECTED.json to check the corpus against, or 'none' to skip (synthetic tests only)")
ap.add_argument("--reference-run", default=str(ROOT / "runs/bm25.run"),
                help="committed default BM25 run; the rebuilt default must reproduce it")
ap.add_argument("--allow-corpus-mismatch", action="store_true",
                help="continue (results labelled NOT COMPARABLE) if the corpus checks fail")
ap.add_argument("--analyzer", default="id")
ap.add_argument("--folds", type=int, default=5)
ap.add_argument("--depth", type=int, default=1000)
ap.add_argument("--out", default=str(ROOT / "deliverables/rq5/sweep"))
ap.add_argument("--tables", default=str(ROOT / "report/tables"))
a = ap.parse_args()

OUT = rq5.guard_output(a.out)
TAB = rq5.guard_output(Path(a.tables) / "rq5_sweep.tex")
METRICS = ("ndcg@10", "ndcgc@10", "hole@10", "mrr@10", "p@5")
CATS = ["identifier", "homonym", "negation", "time", "paraphrase"]

# ------------------------------------------------------------------ inputs and checks
qrels_sha = rq5.verify_qrels(a.qrels, a.expected_qrels_sha or rq5.frozen_qrels_sha())
qrels = require_qrels(a.qrels)
topics = [t for t in load_topics(a.topics) if t["qid"] in qrels]
qids = [t["qid"] for t in topics]
cat = {t["qid"]: t["category"] for t in topics}
queries = {t["qid"]: t["query"] for t in topics}
CATS = [c for c in CATS if any(cat[q] == c for q in qids)]     # categories that have judged queries
ids, docs = load_corpus(a.corpus)
corpus_check = rq5.verify_corpus(a.corpus, len(ids), a.expected_corpus)
print("corpus:", json.dumps({k: v for k, v in corpus_check.items() if k != "path"}))

t0 = time.perf_counter()
index = BM25Index(get_analyzer(a.analyzer)).build(ids, (doc_text(d) for d in docs))
t_index = time.perf_counter() - t0
default_run, _ = index.batch_search(queries, k=a.depth, k1=rq5.DEFAULT[0], b=rq5.DEFAULT[1])
repro = rq5.reproduction_check(default_run, a.reference_run) if a.reference_run else {"ok": None}
print("reproduction of the committed default run:", json.dumps({k: v for k, v in repro.items() if k != "mismatched_queries"}))
comparable = bool(corpus_check["match"] is not False and repro["ok"] is not False)
if not comparable and not a.allow_corpus_mismatch:
    raise SystemExit("ERROR: the corpus is not the one behind the frozen runs (see the checks above). "
                     "Attach the arXiv dataset version used on 19 Oct 2026, or re-run with "
                     "--allow-corpus-mismatch to get results labelled NOT COMPARABLE.")
status = "EXPLORATORY" if comparable else "NOT COMPARABLE (corpus differs from the frozen runs)"
if corpus_check["skipped"]:
    status += " (corpus check skipped)"

# ------------------------------------------------------------------ sweep
t0 = time.perf_counter()
pq = {}                                       # (k1, b) -> metric -> {qid: value}
for k1 in rq5.K1_GRID:
    for b in rq5.B_GRID:
        run, _ = index.batch_search(queries, k=a.depth, k1=k1, b=b)
        pq[(k1, b)] = per_query(run, qrels, METRICS, qids=qids)
t_sweep = time.perf_counter() - t0
mean = {p: {m: float(np.mean([v[m][q] for q in qids])) for m in METRICS} for p, v in pq.items()}
nd = {p: v["ndcg@10"] for p, v in pq.items()}
ndc = {p: v["ndcgc@10"] for p, v in pq.items()}
D = rq5.DEFAULT

# ------------------------------------------------------------------ cross-validation
def cv(seed):
    fold_of = rq5.stratified_folds(topics, a.folds, seed)
    used, chosen = rq5.cv_select(nd, fold_of, a.folds)
    return used, chosen


used, chosen = cv(rq5.CV_SEED)
cv_nd = [nd[used[q]][q] for q in qids]
cv_ndc = [ndc[used[q]][q] for q in qids]
cv_hole = [pq[used[q]]["hole@10"][q] for q in qids]
def_nd = [nd[D][q] for q in qids]
def_ndc = [ndc[D][q] for q in qids]
diff, p = paired_randomization_test(cv_nd, def_nd)
_, dlo, dhi = bootstrap_ci(np.asarray(cv_nd) - np.asarray(def_nd))
diffc, pc = paired_randomization_test(cv_ndc, def_ndc)
extra = {}
for s in rq5.EXTRA_SEEDS:
    u, _ = cv(s)
    extra[s] = float(np.mean([nd[u[q]][q] for q in qids]))

oracle = rq5.best_setting(nd, qids)
oracle_c = rq5.best_setting(ndc, qids)
vals = np.array([mean[p]["ndcg@10"] for p in pq])
dflt = mean[D]["ndcg@10"]
per_cat = {}
for c in CATS:
    qs = [q for q in qids if cat[q] == c]
    bc = rq5.best_setting(nd, qs)
    per_cat[c] = {"default": float(np.mean([nd[D][q] for q in qs])), "best_k1": bc[0], "best_b": bc[1],
                  "best": float(np.mean([nd[bc][q] for q in qs])), "n_queries": len(qs)}

res = {
    "status": status,
    "design": {"analyzer": a.analyzer, "k1_grid": list(rq5.K1_GRID), "b_grid": list(rq5.B_GRID),
               "n_settings": len(pq), "primary_metric": "ndcg@10", "depth": a.depth,
               "folds": a.folds, "cv_seed": rq5.CV_SEED, "extra_seeds": list(rq5.EXTRA_SEEDS),
               "selection": "best mean nDCG@10 on the training folds; exact ties to the setting closest to (1.2, 0.75)"},
    "checks": {"qrels_sha256": qrels_sha, "corpus": corpus_check, "reproduction": repro},
    "default": {"k1": D[0], "b": D[1], **mean[D]},
    "cv": {"ndcg@10": float(np.mean(cv_nd)), "ndcgc@10": float(np.mean(cv_ndc)), "hole@10": float(np.mean(cv_hole)),
           "diff_vs_default": diff, "diff_ci95": [dlo, dhi], "p_vs_default": p,
           "diff_vs_default_condensed": diffc, "p_vs_default_condensed": pc,
           "wins_ties_losses": [int(np.sum(np.asarray(cv_nd) - def_nd > 1e-12)),
                                int(np.sum(np.abs(np.asarray(cv_nd) - def_nd) <= 1e-12)),
                                int(np.sum(np.asarray(cv_nd) - def_nd < -1e-12))],
           "chosen_per_fold": chosen,
           "other_seeds": {"values": extra, "mean": float(np.mean(list(extra.values()))),
                           "min": float(min(extra.values())), "max": float(max(extra.values()))}},
    "oracle_ndcg@10": {"k1": oracle[0], "b": oracle[1], **mean[oracle],
                       "note": f"chosen on the same {len(qids)} queries it is scored on: sensitivity only, NOT a performance estimate"},
    "oracle_ndcgc@10": {"k1": oracle_c[0], "b": oracle_c[1], **mean[oracle_c]},
    "grid_range_ndcg@10": [float(vals.min()), float(vals.max())],
    "share_within_0.01_of_default": float(np.mean(np.abs(vals - dflt) <= 0.01)),
    "share_within_0.02_of_default": float(np.mean(np.abs(vals - dflt) <= 0.02)),
    "share_above_default": float(np.mean(vals > dflt + 1e-12)),
    "per_category_exploratory": per_cat,
    "timing_seconds": {"index": round(t_index, 2), "sweep": round(t_sweep, 2)},
}

# ------------------------------------------------------------------ write
OUT.mkdir(parents=True, exist_ok=True)
with open(OUT / "bm25_sweep_grid.csv", "w", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["k1", "b"] + list(METRICS) + [f"ndcg@10_{c}" for c in CATS])
    for (k1, b) in sorted(pq):
        w.writerow([k1, b] + [f"{mean[(k1, b)][m]:.6f}" for m in METRICS]
                   + [f"{np.mean([nd[(k1, b)][q] for q in qids if cat[q] == c]):.6f}" for c in CATS])
with open(OUT / "bm25_sweep_per_query.csv", "w", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["k1", "b", "qid", "category"] + list(METRICS))
    for (k1, b) in sorted(pq):
        for q in qids:
            w.writerow([k1, b, q, cat[q]] + [f"{pq[(k1, b)][m][q]:.6f}" for m in METRICS])
with open(OUT / "bm25_sweep_cv_per_query.csv", "w", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["qid", "category", "k1_used", "b_used", "ndcg@10_cv", "ndcg@10_default", "ndcgc@10_cv", "ndcgc@10_default"])
    for i, q in enumerate(qids):
        w.writerow([q, cat[q], used[q][0], used[q][1], f"{cv_nd[i]:.6f}", f"{def_nd[i]:.6f}",
                    f"{cv_ndc[i]:.6f}", f"{def_ndc[i]:.6f}"])
(OUT / "bm25_sweep.json").write_text(json.dumps(res, indent=2))
(OUT / "metadata.json").write_text(json.dumps(rq5.metadata(
    vars(a), {"corpus": a.corpus, "topics": a.topics, "qrels": a.qrels},
    {"script": "scripts/bm25_sweep.py", "status": status}), indent=2))

grid = lambda m: np.array([[mean[(k1, b)][m] for b in rq5.B_GRID] for k1 in rq5.K1_GRID])
marks = {"default": D, "best": oracle}
rq5.heatmap(OUT / "bm25_sweep_ndcg10.pdf", rq5.K1_GRID, rq5.B_GRID, grid("ndcg@10"), "nDCG@10", marks)
rq5.heatmap(OUT / "bm25_sweep_ndcgc10.pdf", rq5.K1_GRID, rq5.B_GRID, grid("ndcgc@10"), "condensed nDCG@10",
            {"default": D, "best": oracle_c})
rq5.heatmap(OUT / "bm25_sweep_hole10.pdf", rq5.K1_GRID, rq5.B_GRID, 100 * grid("hole@10"),
            "Hole@10 (%)", {"default": D}, fmt="{:.0f}")

f3 = lambda v: R.fmt(v).replace("-", "$-$")
cvd = res["cv"]
rows = [
    [r"Default ($k_1$=1.2, $b$=0.75)", f3(dflt), f3(mean[D]["ndcgc@10"]), R.fmt(100 * mean[D]["hole@10"], 1) + r"\%"],
    [f"{a.folds}-fold CV (seed {rq5.CV_SEED})", f3(cvd["ndcg@10"]), f3(cvd["ndcgc@10"]), R.fmt(100 * cvd["hole@10"], 1) + r"\%"],
    [f"{a.folds}-fold CV, {len(extra)} other seeds (min--max)", f"{f3(cvd['other_seeds']['min'])}--{f3(cvd['other_seeds']['max'])}", "--", "--"],
    [f"Best on test queries ($k_1$={oracle[0]:g}, $b$={oracle[1]:g}); not a fair estimate",
     f3(mean[oracle]["ndcg@10"]), f3(mean[oracle]["ndcgc@10"]), R.fmt(100 * mean[oracle]["hole@10"], 1) + r"\%"],
    [f"Range over the {len(pq)} settings", f"{f3(vals.min())}--{f3(vals.max())}", "--", "--"],
]
cap = (f"{'' if comparable else 'NOT COMPARABLE: corpus differs. '}BM25 sensitivity to $k_1$ and $b$ "
       f"(identifier-aware analyzer; exploratory). CV $-$ default: {cvd['diff_vs_default']:+.3f} nDCG@10, "
       f"$p$={cvd['p_vs_default']:.3f} (paired randomisation). Only the default was in the judging pool: "
       "unjudged documents count as non-relevant in nDCG@10 and are removed in condensed nDCG@10.").replace("-0", "$-$0").replace("+", "$+$")
R.write(TAB, R.latex_table(rows, ["BM25 setting", "nDCG@10", "nDCG@10 (cond.)", "Hole@10"], "lccc", cap, "tab:rq5sweep"))
print(json.dumps({k: res[k] for k in ("status", "default", "oracle_ndcg@10", "grid_range_ndcg@10")}, indent=1))
print(json.dumps({k: v for k, v in res["cv"].items() if k not in ("chosen_per_fold",)}, indent=1, default=str)[:1500])
print("wrote", OUT, TAB)
