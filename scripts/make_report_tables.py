"""LaTeX tables + macros for report/final_report.tex.

--mode preliminary : every cell shows "lower–upper", the value with unresolved conflicts at
                     the lower grade and at the higher grade (deliverables/preliminary/{lower,upper})
--mode final       : single values from deliverables/final (frozen qrels)
"""
import argparse
import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys  # noqa: E402
sys.path.insert(0, str(ROOT / "src"))
from irproj import report as R  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--mode", choices=["preliminary", "final"], required=True)
ap.add_argument("--out", default=str(ROOT / "report" / "tables"))
a = ap.parse_args()
OUT = Path(a.out)
OUT.mkdir(parents=True, exist_ok=True)
SYS = ["bm25", "e5", "specter2", "bm25+e5", "bm25+specter2"]
CATS = ["identifier", "homonym", "negation", "time", "paraphrase"]
D = ROOT / "deliverables"
dirs = [D / "preliminary" / "lower", D / "preliminary" / "upper"] if a.mode == "preliminary" else [D / "final"]
for d in dirs:
    if not (d / "results" / "summary.csv").exists():
        raise SystemExit(f"missing {d}/results - run scripts/final_pipeline.sh {a.mode} first")


def rd(path):
    return list(csv.DictReader(open(path)))


summ = [{r["system"]: r for r in rd(d / "results" / "summary.csv")} for d in dirs]
cat = [{(r["system"], r["category"]): r for r in rd(d / "results" / "per_category.csv")} for d in dirs]
sig = [{(r["a"], r["b"]): r for r in rd(d / "results" / "significance.csv")} for d in dirs]
ana = [json.loads((d / "analysis" / "error_analysis.json").read_text()) for d in dirs]


def num(v, d, signed):
    t = f"{v:+.{d}f}" if signed else f"{v:.{d}f}"
    return t.replace("-", "$-$")


def cell(vals, d=3, signed=False):
    vals = sorted(float(v) for v in vals)
    if len(vals) == 1 or abs(vals[0] - vals[-1]) < 5e-4:
        return num(vals[0], d, signed)
    sep = " to " if signed or vals[0] < 0 else "--"
    return f"{num(vals[0], d, signed)}{sep}{num(vals[-1], d, signed)}"


def pcell(ps):
    f = lambda p: "$<$0.001" if p < 0.001 else f"{p:.3f}"
    ps = sorted(ps)
    return f(ps[0]) if len(ps) == 1 or f(ps[0]) == f(ps[-1]) else f"{f(ps[0])}--{f(ps[-1])}"


# ---------------------------------------------------------------- main results
M = ["ndcg@10", "ndcg@5", "p@5", "mrr@10", "map@10", "hole@10"]
rows = []
for s in SYS:
    r = [R.pretty(s)] + [cell([x[s][m] for x in summ]) for m in M[:-1]]
    r.append(cell([100 * float(x[s]["hole@10"]) for x in summ], 1) + r"\%")
    rows.append(r)
if a.mode == "final":
    for r, s in zip(rows, SYS):
        x = summ[0][s]
        r[1] = f"{float(x['ndcg@10']):.3f} [{float(x['ndcg@10_ci_low']):.2f}, {float(x['ndcg@10_ci_high']):.2f}]"
cap = ("Effectiveness on the 50 cs.CR queries. PRELIMINARY: each cell gives the value with all 325 unresolved "
       "conflicts at the lower grade -- at the higher grade (a sensitivity check, not bounds; see Table~\\ref{tab:fsens}). "
       if a.mode == "preliminary" else
       "Effectiveness on the 50 cs.CR queries (frozen, adjudicated qrels; nDCG@10 with 95\\% bootstrap CI). ")
cap += "Binary metrics use grade $\\geq$ 2; Hole@10 = share of top-10 documents never judged."
R.write(OUT / "fin_main.tex", R.latex_table(rows, ["System", "nDCG@10", "nDCG@5", "P@5", "MRR@10", "MAP@10", "Hole@10"],
                                            "lcccccc", cap, "tab:fmain"))

# ---------------------------------------------------------------- per category
rows = [[R.pretty(s)] + [cell([x[(s, c)]["ndcg@10"] for x in cat]) for c in CATS] for s in SYS]
cap = ("nDCG@10 by query category (10 queries each; exploratory). "
       + ("PRELIMINARY ranges as in Table~\\ref{tab:fmain}." if a.mode == "preliminary" else "95\\% CIs in Fig.~\\ref{fig:fcat}."))
R.write(OUT / "fin_cat.tex", R.latex_table(rows, ["System"] + [R.CATEGORY_NAMES[c] for c in CATS], "lccccc", cap, "tab:fcat"))

# ---------------------------------------------------------------- significance
rows = []
for k in sig[0]:
    xs = [x[k] for x in sig]
    diffs = [float(x["diff"]) for x in xs]
    ps = [float(x["p_holm"]) for x in xs]
    sigs = {x["significant"] for x in xs}
    verdict = "yes" if sigs == {"True"} else "no" if sigs == {"False"} else "depends"
    if len(xs) == 1:
        x = xs[0]
        dtxt = f"{num(diffs[0], 3, True)} [{num(float(x['diff_ci_low']), 3, True)}, {num(float(x['diff_ci_high']), 3, True)}]"
    else:
        dtxt = cell(diffs, signed=True)
    rows.append([f"{R.pretty(k[0])} $-$ {R.pretty(k[1])}", dtxt, pcell(ps), verdict])
cap = ("Paired randomisation tests on nDCG@10 over the 50 queries (100{,}000 permutations; Holm--Bonferroni "
       "over all 10 pairs; $\\alpha=0.05$). "
       + ("PRELIMINARY: ranges over the lower and upper fallback runs; `depends' = significant in only one of them. Robustness to adjudication: Table~\\ref{tab:fsens}."
          if a.mode == "preliminary" else ""))
R.write(OUT / "fin_sig.tex", R.latex_table(rows, ["Comparison", "$\\Delta$nDCG@10", "$p_{\\text{Holm}}$", "Significant"],
                                           "lccc", cap, "tab:fsig"))

# ---------------------------------------------------------------- grade-1 share (error analysis)
rows = [[R.pretty(s)] + [cell([x["grade1_share_top10"][s][c] for x in ana], 2) for c in CATS] for s in SYS]
R.write(OUT / "fin_g1.tex", R.latex_table(
    rows, ["System"] + [R.CATEGORY_NAMES[c] for c in CATS], "lccccc",
    "Share of each system's top 10 graded 1 (on topic but does not answer, or breaks the exclusion / date limit).",
    "tab:fg1"))

# ---------------------------------------------------------------- adjudication sensitivity (preliminary only)
sens_path = D / "preliminary" / "sensitivity" / "adjudication_sensitivity.json"
if a.mode == "preliminary" and sens_path.exists():
    sj = json.loads(sens_path.read_text())
    rows = []
    for k, (lo, hi) in sj["diff_bounds"].items():
        x, y = k.split(" vs ")
        wc = next((v for c, v in sj["worst_case_tests"].items() if c in (f"{x} > {y}", f"{x} < {y}")), None)
        rows.append([f"{R.pretty(x)} $-$ {R.pretty(y)}", f"{num(lo, 3, True)} to {num(hi, 3, True)}",
                     "no" if lo > 0 or hi < 0 else "yes",
                     f"{100 * sj['random_adjudications']['share_significant'][k]:.0f}\\%",
                     ("n.s." if not wc["significant"] else "sig.") if wc else "--"])
    R.write(OUT / "fin_sens.tex", R.latex_table(
        rows, ["Comparison", "Exact range of $\\Delta$nDCG@10", "Sign can flip", "Sig.\\ in random adj.", "Worst case"],
        "lcccc", f"Sensitivity to adjudication. Exact range of each mean difference over every adjudication that picks "
        f"one of the two submitted grades ({sj['combinations_enumerated']:,} per-query combinations enumerated); share of "
        f"{sj['random_adjudications']['samples']} random adjudications in which the pair is significant (Holm, 10 pairs); and "
        "the test on the single most adversarial adjudication.", "tab:fsens"))
    mb = sj["mean_bounds"]
    sens_mac = {"finSensFirst": f"{100 * sj['random_adjudications']['share_ranked_first']['bm25+e5']:.0f}",
                "finSensN": str(sj["random_adjudications"]["samples"]),
                "finSensTopOrder": f"{100 * max(sj['random_adjudications']['orders'].values()) / sj['random_adjudications']['samples']:.0f}",
                "finBoundHybE": f"{mb['bm25+e5'][0]:.3f}--{mb['bm25+e5'][1]:.3f}",
                "finBoundBM": f"{mb['bm25'][0]:.3f}--{mb['bm25'][1]:.3f}",
                "finBoundE": f"{mb['e5'][0]:.3f}--{mb['e5'][1]:.3f}"}
else:
    sens_mac = {}
    if a.mode == "final":
        (OUT / "fin_sens.tex").unlink(missing_ok=True)      # preliminary-only table must not survive

# ---------------------------------------------------------------- figure + macros
fig_src = dirs[0] / "figures" / "per_category.pdf"
if fig_src.exists():
    (ROOT / "report" / "figures").mkdir(parents=True, exist_ok=True)
    shutil.copy(fig_src, ROOT / "report" / "figures" / "fin_per_category.pdf")
au = json.loads((D / "judging" / "audit.json").read_text())["summary"]
comp = [x["complementarity_relevant_top10"] for x in ana]
mac = {"finStatus": "PRELIMINARY: 325 annotator conflicts are not yet adjudicated" if a.mode == "preliminary"
       else "Final results on frozen, adjudicated qrels",
       "finKappaLin": f"{au['kappa_linear']:.3f}", "finKappaQuad": f"{au['kappa_quadratic']:.3f}",
       "finKappaBin": f"{au['kappa_binary_ge2']:.3f}", "finExact": f"{au['exact_agreement']:.3f}",
       "finConflicts": str(au["conflicting_pairs"]), "finZeroThree": str(au["zero_vs_three"]),
       "finCross": str(au["binary_relevance_disagreements"]), "finPairs": str(au["pool_pairs"]),
       "finOnlyBM": cell([c["only_bm25"] for c in comp], 0), "finOnlyE": cell([c["only_e5"] for c in comp], 0),
       "finBoth": cell([c["both"] for c in comp], 0)}
mac.update(sens_mac)
(OUT / "fin_macros.tex").write_text("".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in mac.items()))
print("wrote", ", ".join(sorted(p.name for p in OUT.glob("fin_*"))))
