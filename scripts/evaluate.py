"""Step 5: evaluate all runs against the frozen qrels.

    python scripts/evaluate.py --qrels data/qrels/qrels.txt --topics data/queries/topics.jsonl \
        --runs runs/bm25.run runs/e5.run runs/specter2.run runs/bm25+e5.run runs/bm25+specter2.run \
        --out results --tables report/tables --figures report/figures

Writes: summary.csv, per_query.csv, per_category.csv, significance.csv,
significance_by_category.csv, efficiency.csv, LaTeX tables and the per-category figure.
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from irproj import report as R
from irproj.io import load_topics, read_qrels, require_qrels, read_run, sha256_file
from irproj.metrics import DEFAULT_METRICS, per_query
from irproj.stats import bootstrap_ci, pairwise_tests

ap = argparse.ArgumentParser()
ap.add_argument("--qrels", required=True)
ap.add_argument("--topics", required=True)
ap.add_argument("--runs", nargs="+", required=True)
ap.add_argument("--out", default="results")
ap.add_argument("--tables", default="report/tables")
ap.add_argument("--figures", default="report/figures")
ap.add_argument("--main-metric", default="ndcg@10")
ap.add_argument("--rel-level", type=int, default=2)
ap.add_argument("--n-perm", type=int, default=100_000)
ap.add_argument("--label", default="", help="suffix for output names, e.g. '-prelim'")
ap.add_argument("--status", default="", help="text added to table captions, e.g. 'PRELIMINARY (conflicts at lower grade)'")
a = ap.parse_args()

out, tables, figs = Path(a.out), Path(a.tables), Path(a.figures)
out.mkdir(parents=True, exist_ok=True)
qrels = require_qrels(a.qrels)
topics = load_topics(a.topics)
cat = {t["qid"]: t["category"] for t in topics}
qids = [t["qid"] for t in topics if t["qid"] in qrels]
missing = [t["qid"] for t in topics if t["qid"] not in qrels]
if missing:
    print(f"warning: {len(missing)} topics have no judgments and are skipped: {missing}")
systems = [Path(p).stem for p in a.runs]
runs = {Path(p).stem: read_run(p) for p in a.runs}
# compatibility checks: every run must cover the evaluated topics and retrieve judged documents
judged_docs = {d for q in qrels for d in qrels[q]}
for s_, r_ in runs.items():
    gone = [q for q in qids if not r_.get(q)]
    if gone:
        raise SystemExit(f"ERROR: run {s_} has no results for topics {gone[:10]}")
    extra = sorted(set(r_) - {t['qid'] for t in topics})
    if extra:
        print(f"note: run {s_} has results for {len(extra)} topics that are not evaluated: {extra[:5]}")
    if not any(d in judged_docs for q in qids for d in r_[q]):
        raise SystemExit(f"ERROR: run {s_} retrieves no judged document at all - wrong qrels or run?")
METRICS = tuple(DEFAULT_METRICS) + ("sndcg@10",)
pq = {s: per_query(runs[s], qrels, METRICS, a.rel_level, qids) for s in systems}
M = a.main_metric
categories = [c for c in ["identifier", "homonym", "negation", "time", "paraphrase"] if c in set(cat.values())]

# ------------------------------------------------------------------ overall summary
summary = []
for s in systems:
    row = {"system": s}
    for m in METRICS:
        row[m] = float(np.mean([pq[s][m][q] for q in qids]))
    mu, lo, hi = bootstrap_ci([pq[s][M][q] for q in qids])
    row[f"{M}_ci_low"], row[f"{M}_ci_high"] = lo, hi
    summary.append(row)
with open(out / f"summary{a.label}.csv", "w", newline="") as f:
    w = csv.DictWriter(f, lineterminator="\n", fieldnames=list(summary[0]))
    w.writeheader()
    w.writerows(summary)

with open(out / f"per_query{a.label}.csv", "w", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["system", "qid", "category"] + list(METRICS))
    for s in systems:
        for q in qids:
            w.writerow([s, q, cat[q]] + [f"{pq[s][m][q]:.4f}" for m in METRICS])

# ------------------------------------------------------------------ per category with CIs
means, lows, highs = {s: {} for s in systems}, {s: {} for s in systems}, {s: {} for s in systems}
rows = []
for s in systems:
    for c in categories:
        qs = [q for q in qids if cat[q] == c]
        mu, lo, hi = bootstrap_ci([pq[s][M][q] for q in qs])
        means[s][c], lows[s][c], highs[s][c] = mu, lo, hi
        extra_m = {m: float(np.mean([pq[s][m][q] for q in qs])) for m in ("p@5", "mrr@10", "sndcg@10")}
        rows.append({"system": s, "category": c, "n": len(qs), M: mu, "ci_low": lo, "ci_high": hi, **extra_m,
                     "hole@10": float(np.mean([pq[s]["hole@10"][q] for q in qs])) if qs else np.nan})
with open(out / f"per_category{a.label}.csv", "w", newline="") as f:
    w = csv.DictWriter(f, lineterminator="\n", fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

# ------------------------------------------------------------------ significance
sig = pairwise_tests({s: pq[s][M] for s in systems}, systems, n_perm=a.n_perm)
with open(out / f"significance{a.label}.csv", "w", newline="") as f:
    w = csv.DictWriter(f, lineterminator="\n", fieldnames=list(sig[0]))
    w.writeheader()
    w.writerows(sig)
sig_cat = []
for c in categories:
    qs = [q for q in qids if cat[q] == c]
    for r in pairwise_tests({s: {q: pq[s][M][q] for q in qs} for s in systems}, systems, n_perm=a.n_perm):
        sig_cat.append({"category": c, **r})
with open(out / f"significance_by_category{a.label}.csv", "w", newline="") as f:
    w = csv.DictWriter(f, lineterminator="\n", fieldnames=list(sig_cat[0]))
    w.writeheader()
    w.writerows(sig_cat)

# ------------------------------------------------------------------ efficiency
eff_rows = []
for s, run_path in zip(systems, a.runs):
    p = Path(run_path + ".eff.json")
    e = json.loads(p.read_text()) if p.exists() else {}
    eff_rows.append({"system": s, "index_seconds": e.get("index_seconds"), "index_mb": e.get("index_mb"),
                     "mean_ms": e.get("mean_ms"), "p95_ms": e.get("p95_ms"), "hardware": e.get("hardware")})
with open(out / f"efficiency{a.label}.csv", "w", newline="") as f:
    w = csv.DictWriter(f, lineterminator="\n", fieldnames=list(eff_rows[0]))
    w.writeheader()
    w.writerows(eff_rows)

# ------------------------------------------------------------------ LaTeX + figure
mcols = ["ndcg@10", "ndcg@5", "p@5", "mrr@10", "map@10", "hole@10"]
trows = []
for r in summary:
    trows.append([R.pretty(r["system"])] +
                 [R.fmt(r[m]) for m in mcols[:-1]] + [R.fmt(100 * r["hole@10"], 1) + r"\%"])
R.write(tables / f"main_results{a.label}.tex", R.latex_table(
    trows, ["System"] + [R.METRIC_NAMES[m] for m in mcols], "l" + "c" * len(mcols),
    f"{a.status + ' ' if a.status else ''}Effectiveness on {len(qids)} cs.CR queries (graded judgments; binary metrics use grade $\\geq$ {a.rel_level}).",
    f"tab:main{a.label}", bold_max_cols=range(1, len(mcols))))

crows = []
for s in systems:
    crows.append([R.pretty(s)] + [R.fmt(means[s][c]) for c in categories])
R.write(tables / f"per_category{a.label}.tex", R.latex_table(
    crows, ["System"] + [R.CATEGORY_NAMES[c] for c in categories], "l" + "c" * len(categories),
    f"{R.METRIC_NAMES[M]} by query category (10 queries each; indicative, see CIs in Fig.~\\ref{{fig:cat}}).",
    f"tab:cat{a.label}", bold_max_cols=range(1, len(categories) + 1)))

srows = [[f"{R.pretty(r['a'])} vs {R.pretty(r['b'])}", f"{r['diff']:+.3f}",
          f"[{r['diff_ci_low']:+.3f}, {r['diff_ci_high']:+.3f}]", f"{r['a_better']}/{r['ties']}/{r['b_better']}",
          R.fmt(r["p"], 4), R.fmt(r["p_holm"], 4), "yes" if r["significant"] else "no"] for r in sig]
R.write(tables / f"significance{a.label}.tex", R.latex_table(
    srows, ["Comparison", r"$\Delta$", "95\\% CI", "W/T/L", "$p$", "$p_{\\text{Holm}}$", r"Sig.\ ($\alpha$=0.05)"], "lcccccc",
    f"Paired randomisation tests on {R.METRIC_NAMES[M]} ({a.n_perm:,} permutations, Holm--Bonferroni over all pairs).",
    f"tab:sig{a.label}"))

erows = [[R.pretty(e["system"]), R.fmt(e["index_seconds"], 1), R.fmt(e["index_mb"], 1),
          R.fmt(e["mean_ms"], 1), R.fmt(e["p95_ms"], 1), str(e["hardware"] or "--")] for e in eff_rows]
R.write(tables / f"efficiency{a.label}.tex", R.latex_table(
    erows, ["System", "Index time (s)", "Index size (MB)", "Query mean (ms)", "Query p95 (ms)", "Hardware"],
    "lccccl", "Efficiency. Dense index time is corpus encoding; dense query time includes encoding the query. "
    "Hybrid figures are the sum of their components.", f"tab:eff{a.label}"))

R.grouped_bars(figs / f"per_category{a.label}.pdf", categories, systems, means, lows, highs,
               ylabel=R.METRIC_NAMES[M])

meta = {"qrels_sha256": sha256_file(a.qrels), "n_queries": len(qids),
        "runs": {s: sha256_file(p) for s, p in zip(systems, a.runs)}}
(out / f"eval_meta{a.label}.json").write_text(json.dumps(meta, indent=2))

# sensitivity: only queries with at least one document of grade >= rel_level in the pool
with_rel = [q for q in qids if any(g >= a.rel_level for g in qrels[q].values())]
sens = {s: {m: float(np.mean([pq[s][m][q] for q in with_rel])) for m in ("ndcg@10", "p@5", "mrr@10")} for s in systems}
(out / f"sensitivity_queries_with_relevant{a.label}.json").write_text(json.dumps(
    {"n_queries": len(with_rel), "excluded": [q for q in qids if q not in with_rel], "means": sens}, indent=2))

print(f"{'system':16s}" + "".join(f"{R.METRIC_NAMES.get(m, m):>9s}" for m in METRICS))
for r in summary:
    print(f"{r['system']:16s}" + "".join(f"{r[m]:9.3f}" for m in METRICS))
print("\nsignificance on", M)
for r in sig:
    print(f"  {r['a']:>14s} vs {r['b']:<14s} diff={r['diff']:+.3f} [{r['diff_ci_low']:+.3f},{r['diff_ci_high']:+.3f}]  p={r['p']:.4f}  p_holm={r['p_holm']:.4f}"
          f"  {'*' if r['significant'] else ''}")
