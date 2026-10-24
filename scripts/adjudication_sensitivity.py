"""How much can adjudication change the results?

Every unresolved conflict is resolved to one of the two submitted grades. For each query all
2^c combinations of its c conflicts are enumerated (c <= 13 here), which gives EXACT bounds,
over every such adjudication, on
  * each system's mean nDCG@10 (queries are independent, so the bound on the mean is the mean
    of the per-query bounds), and
  * each pairwise mean difference A - B.
For significance (not decomposable over queries) it reports
  * the paired randomisation test on the WORST-CASE adjudication for each pair (per query, the
    combination that minimises A - B, and the one that maximises it), Holm-corrected over the
    10 pairs, and
  * the share of N random adjudications (each conflict picks one of its two grades at random)
    in which each pair is significant after Holm correction, and the share in which each
    system ranks first.
Note: nDCG is not monotone in the grades (raising the grade of a document a system did not
retrieve lowers its nDCG), so the 'all lower' / 'all upper' runs are NOT bounds; this script is.

    python scripts/adjudication_sensitivity.py --out deliverables/preliminary/sensitivity
"""
import argparse
import glob
import itertools
import json
from pathlib import Path

import numpy as np

from irproj.io import load_topics, rank_docs, read_run
from irproj.pool import load_exports
from irproj.stats import holm_bonferroni, paired_randomization_test

ap = argparse.ArgumentParser()
ap.add_argument("--exports", nargs="+", default=["judging/exports/judgments_*_main.json"])
ap.add_argument("--topics", default="data/queries/topics.jsonl")
ap.add_argument("--runs-dir", default="runs")
ap.add_argument("--samples", type=int, default=500)
ap.add_argument("--perm", type=int, default=10_000)
ap.add_argument("--worst-perm", type=int, default=100_000)
ap.add_argument("--seed", type=int, default=3)
ap.add_argument("--out", default="deliverables/preliminary/sensitivity")
a = ap.parse_args()

SYS = ["bm25", "e5", "specter2", "bm25+e5", "bm25+specter2"]
PAIRS = list(itertools.combinations(SYS, 2))
qids = sorted((t["qid"] for t in load_topics(a.topics)), key=int)
judg = load_exports(sorted({p for pat in a.exports for p in glob.glob(pat)}))
grades = {}
for ann in judg:
    for k, g in judg[ann].items():
        grades.setdefault(k, []).append(g)
top = {s: {q: [d for d, _ in rank_docs(read_run(Path(a.runs_dir) / f"{s}.run")[q])[:10]] for q in qids} for s in SYS}
disc = 1.0 / np.log2(np.arange(2, 12))

# per query: matrix of all combinations -> nDCG@10 per system (rows = combinations)
per_q = {}
for q in qids:
    docs = sorted(d for (qq, d) in grades if qq == q)
    fixed = {d: grades[(q, d)][0] for d in docs if len(set(grades[(q, d)])) == 1}
    conf = [d for d in docs if d not in fixed]
    opts = [sorted(set(grades[(q, d)])) for d in conf]
    combos = np.array(list(itertools.product(*opts)), dtype=float) if conf else np.zeros((1, 0))
    G = np.zeros((len(combos), len(docs)))
    col = {d: i for i, d in enumerate(docs)}
    for d, g in fixed.items():
        G[:, col[d]] = g
    for j, d in enumerate(conf):
        G[:, col[d]] = combos[:, j]
    ideal = -np.sort(-G, axis=1)[:, :10]
    idcg = (ideal * disc[:ideal.shape[1]]).sum(1)
    vals = {}
    for s in SYS:
        idx = [col.get(d) for d in top[s][q]]
        gains = np.stack([G[:, i] if i is not None else np.zeros(len(G)) for i in idx], axis=1)
        dcg = (gains * disc[:gains.shape[1]]).sum(1)
        vals[s] = np.where(idcg > 0, dcg / np.where(idcg > 0, idcg, 1), 0.0)
    per_q[q] = {"n_conflicts": len(conf), "vals": vals, "combos": len(combos)}

res = {"queries": len(qids), "conflicts": int(sum(v["n_conflicts"] for v in per_q.values())),
       "combinations_enumerated": int(sum(v["combos"] for v in per_q.values()))}
res["mean_bounds"] = {s: [float(np.mean([per_q[q]["vals"][s].min() for q in qids])),
                          float(np.mean([per_q[q]["vals"][s].max() for q in qids]))] for s in SYS}
res["diff_bounds"] = {}
worst = {}
for x, y in PAIRS:
    lo_vec, hi_vec = [], []
    for q in qids:
        d = per_q[q]["vals"][x] - per_q[q]["vals"][y]
        i_lo, i_hi = int(d.argmin()), int(d.argmax())
        lo_vec.append((per_q[q]["vals"][x][i_lo], per_q[q]["vals"][y][i_lo]))
        hi_vec.append((per_q[q]["vals"][x][i_hi], per_q[q]["vals"][y][i_hi]))
    res["diff_bounds"][f"{x} vs {y}"] = [float(np.mean([u - v for u, v in lo_vec])), float(np.mean([u - v for u, v in hi_vec]))]
    worst[(x, y, "min")] = lo_vec
    worst[(x, y, "max")] = hi_vec

# worst-case significance: for a claim "x > y" use the min-difference adjudication, for "x < y" the max
claims = {}
for x, y in PAIRS:
    lo, hi = res["diff_bounds"][f"{x} vs {y}"]
    if lo > 0:
        vec = worst[(x, y, "min")]; direction = f"{x} > {y}"
    elif hi < 0:
        vec = worst[(x, y, "max")]; direction = f"{x} < {y}"
    else:
        continue          # sign can flip: no robust direction to test
    _, p = paired_randomization_test([u for u, _ in vec], [v for _, v in vec], a.worst_perm, a.seed)
    claims[direction] = p
holm = holm_bonferroni({**claims, **{f"_{i}": 1.0 for i in range(len(PAIRS) - len(claims))}})
res["worst_case_tests"] = {k: {"p": claims[k], "p_holm_over_10": holm[k][0], "significant": holm[k][1]} for k in claims}

# random adjudications
rng = np.random.default_rng(a.seed)
sig_count = {f"{x} vs {y}": 0 for x, y in PAIRS}
first = {s: 0 for s in SYS}
order_counts = {}
for n in range(a.samples):
    pick = {q: rng.integers(len(per_q[q]["vals"]["bm25"])) for q in qids}
    v = {s: np.array([per_q[q]["vals"][s][pick[q]] for q in qids]) for s in SYS}
    means = {s: v[s].mean() for s in SYS}
    first[max(means, key=means.get)] += 1
    order = " > ".join(sorted(SYS, key=lambda s: -means[s]))
    order_counts[order] = order_counts.get(order, 0) + 1
    ps = {f"{x} vs {y}": paired_randomization_test(v[x], v[y], a.perm, a.seed + n)[1] for x, y in PAIRS}
    for k, (_, sig) in holm_bonferroni(ps).items():
        sig_count[k] += sig
res["random_adjudications"] = {
    "samples": a.samples, "permutations": a.perm,
    "share_significant": {k: c / a.samples for k, c in sig_count.items()},
    "share_ranked_first": {s: c / a.samples for s, c in first.items()},
    "orders": dict(sorted(order_counts.items(), key=lambda kv: -kv[1]))}

out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
(out / "adjudication_sensitivity.json").write_text(json.dumps(res, indent=2))
N = {"bm25": "BM25", "e5": "E5", "specter2": "SPECTER2", "bm25+e5": "BM25+E5", "bm25+specter2": "BM25+SPECTER2"}
L = ["# Sensitivity of the results to adjudication", "",
     f"{res['conflicts']} conflicts over {res['queries']} queries; all {res['combinations_enumerated']:,} per-query "
     "combinations of the two submitted grades were enumerated. Bounds are exact over every adjudication that picks one "
     "of the two submitted grades for each conflict.", "",
     "## Exact bounds on mean nDCG@10", "", "| System | Min | Max |", "|---|---|---|"]
L += [f"| {N[s]} | {lo:.3f} | {hi:.3f} |" for s, (lo, hi) in res["mean_bounds"].items()]
L += ["", "## Exact bounds on mean differences, worst-case tests, random adjudications", "",
      "| Pair (A vs B) | Min A−B | Max A−B | Worst-case p (Holm, 10 pairs) | Significant in % of random adjudications |",
      "|---|---|---|---|---|"]
for x, y in PAIRS:
    k = f"{x} vs {y}"
    lo, hi = res["diff_bounds"][k]
    wc = next((v for c, v in res["worst_case_tests"].items() if c in (f"{x} > {y}", f"{x} < {y}")), None)
    wtxt = (f"{wc['p_holm_over_10']:.4f} ({'sig.' if wc['significant'] else 'n.s.'})" if wc else "sign can flip")
    L.append(f"| {N[x]} vs {N[y]} | {lo:+.3f} | {hi:+.3f} | {wtxt} | {100 * res['random_adjudications']['share_significant'][k]:.0f}% |")
L += ["", "Share of random adjudications in which each system has the highest mean nDCG@10: " +
      ", ".join(f"{N[s]} {100 * v:.0f}%" for s, v in res["random_adjudications"]["share_ranked_first"].items()), "",
      "Most frequent system orders: " + "; ".join(f"{o} ({100 * c / a.samples:.0f}%)"
                                                for o, c in list(res["random_adjudications"]["orders"].items())[:3]), ""]
(out / "adjudication_sensitivity.md").write_text("\n".join(L))
print("\n".join(L))
