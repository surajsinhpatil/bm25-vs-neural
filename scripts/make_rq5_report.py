"""Report tables, macros and figure for RQ5, made only from the committed outputs in deliverables/rq5/.

    python scripts/make_rq5_report.py
Writes report/tables/rq5_sweep.tex, report/tables/rq5_tok.tex, report/tables/rq5_macros.tex and
report/figures/rq5_sweep.pdf. Stops unless the outputs come from a run whose checks all passed
(frozen qrels checksum, corpus = EXPECTED.json, default run reproduced, corpus check not skipped).
Nothing is re-run; every number is read from the JSON / CSV files (or, for the count of unjudged
pairs, from the saved top-100 runs and the frozen qrels).
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from irproj import report as R
from irproj import rq5
from irproj.io import rank_docs, read_qrels, read_run

ROOT = rq5.ROOT
ap = argparse.ArgumentParser()
ap.add_argument("--rq5", default=str(ROOT / "deliverables/rq5"))
ap.add_argument("--qrels", default=str(ROOT / "data/qrels/qrels.txt"))
ap.add_argument("--tables", default=str(ROOT / "report/tables"))
ap.add_argument("--figures", default=str(ROOT / "report/figures"))
a = ap.parse_args()
D = Path(a.rq5)
TAB, FIG = rq5.guard_output(a.tables), rq5.guard_output(a.figures)

sw = json.loads((D / "sweep/bm25_sweep.json").read_text())
tk = json.loads((D / "tokenisation/tokenizer_ablation.json").read_text())
metas = [json.loads((D / s / "metadata.json").read_text()) for s in ("sweep", "tokenisation")]
frozen = rq5.frozen_qrels_sha()
rq5.verify_qrels(a.qrels, frozen)
for name, r, m in (("sweep", sw, metas[0]), ("tokenisation", tk, metas[1])):
    c = r["checks"]
    problems = [txt for ok, txt in (
        (r["status"] == "EXPLORATORY", f"status is {r['status']!r}"),
        (c["qrels_sha256"] == frozen, "qrels checksum differs from data/qrels/qrels.sha256"),
        (c["corpus"].get("match") is True and not c["corpus"].get("skipped"), "corpus check failed or skipped"),
        (c["reproduction"].get("ok") is True, "default BM25 run not reproduced"),
        (m["files_sha256"]["qrels"] == frozen and m["git"]["commit"] and m["git"]["dirty"] is False,
         "metadata: wrong qrels, no commit or dirty tree")) if not ok]
    if problems:
        raise SystemExit(f"ERROR: {name} outputs fail validation: {'; '.join(problems)}")

grid = {(float(r["k1"]), float(r["b"])): {k: float(v) for k, v in r.items()}
        for r in csv.DictReader(open(D / "sweep/bm25_sweep_grid.csv"))}
K1S = sorted({p[0] for p in grid})
BS = sorted({p[1] for p in grid})
DEF = rq5.DEFAULT
dflt = grid[DEF]
cv = sw["cv"]
oc = sw["oracle_ndcgc@10"]
oc_set = (oc["k1"], oc["b"])
on = sw["oracle_ndcg@10"]
nd = np.array([v["ndcg@10"] for v in grid.values()])
cd = np.array([v["ndcgc@10"] for v in grid.values()])
ho = np.array([v["hole@10"] for v in grid.values()])
within = sorted(p for p, v in grid.items() if v["ndcg@10"] >= dflt["ndcg@10"] - 0.01)


def f3(x, signed=False):
    # differences smaller than 0.0005 get 4 decimals, so they never print as a signed zero
    t = (f"{x:+.4f}" if abs(x) < 0.0005 else f"{x:+.3f}") if signed else f"{x:.3f}"
    return t.replace("-", "$-$").replace("+", "$+$")


def fp(p):
    return "$<$0.001" if p < 0.001 else f"{p:.3f}"


def pct(x, d=1):
    return f"{100 * x:.{d}f}\\%"


def htb(tex):
    """RQ5 tables may also float here or at the bottom, so they stay before the Limitations section."""
    return tex.replace("\\begin{table}[t]", "\\begin{table}[htb]", 1)


def setting(p):
    return f"$k_1$={p[0]:g}, $b$={p[1]:g}"


# ------------------------------------------------------------------ sweep table
anserini = (0.9, 0.4)
rows = [
    [f"Default ({setting(DEF)})", f3(dflt["ndcg@10"]), "--", f3(dflt["ndcgc@10"]), "--", pct(dflt["hole@10"])],
    [f"{sw['design']['folds']}-fold CV, seed {sw['design']['cv_seed']}", f3(cv["ndcg@10"]),
     f"{f3(cv['diff_vs_default'], True)} ({fp(cv['p_vs_default'])})", f3(cv["ndcgc@10"]),
     f"{f3(cv['diff_vs_default_condensed'], True)} ({fp(cv['p_vs_default_condensed'])})", pct(cv["hole@10"])],
    [f"CV, {len(cv['other_seeds']['values'])} other fold seeds",
     f"{f3(cv['other_seeds']['min'])}--{f3(cv['other_seeds']['max'])}", "", "", "", ""],
    [f"Anserini default ({setting(anserini)})", f3(grid[anserini]["ndcg@10"]), "", f3(grid[anserini]["ndcgc@10"]), "",
     pct(grid[anserini]["hole@10"])],
    [f"Best, nDCG@10$^\\dagger$ ({setting((on['k1'], on['b']))})", f3(on["ndcg@10"]), "", f3(on["ndcgc@10"]), "",
     pct(on["hole@10"])],
    [f"Best, cond.$^\\dagger$ ({setting(oc_set)})", f3(oc["ndcg@10"]), "", f3(oc["ndcgc@10"]), "",
     pct(oc["hole@10"])],
    [f"Range, all {len(grid)} settings", f"{f3(nd.min())}--{f3(nd.max())}", "", f"{f3(cd.min())}--{f3(cd.max())}", "",
     f"{pct(ho.min(), 0)}--{pct(ho.max(), 0)}"],
]
cap = ("RQ5a (exploratory): BM25 (identifier-aware analyzer) over 132 $(k_1, b)$ settings on the 50 cs.CR queries. "
       "$\\Delta$ ($p$): cross-validated minus default, paired randomisation test. Only the default run was in the "
       "judging pool; nDCG@10 counts unjudged documents as non-relevant, condensed nDCG@10 removes them, Hole@10 is "
       "the share of unjudged documents in the top 10. $^\\dagger$Chosen on the same queries it is scored on: "
       "sensitivity only, not a performance estimate.")
R.write(TAB / "rq5_sweep.tex", htb(R.latex_table(
    rows, ["BM25 setting", "nDCG@10", "$\\Delta$ ($p$)", "Cond.\\ nDCG@10", "$\\Delta$ ($p$)", "Hole@10"],
    "lccccc", cap, "tab:rq5sweep")))

# ------------------------------------------------------------------ tokenisation table
NAMES = {"id": "Identifier-aware (main)", "plain": "Lucene-like",
         "id-nostem": "Identifier-aware, no stem.", "plain-nostem": "Lucene-like, no stem.",
         "id-nostop": "Identifier-aware, stopwords kept"}
V = tk["variants"]
rows = []
for v, r in V.items():
    if v == "id":
        rows.append([NAMES[v], f3(r["ndcg@10"]), "--", f3(r["ndcgc@10"]), "--", pct(r["hole@10"]), "--"])
    else:
        w, t, l = r["wins_ties_losses_vs_id"]
        rows.append([NAMES.get(v, v), f3(r["ndcg@10"]), f"{f3(r['diff_vs_id'], True)} ({fp(r['p_holm_vs_id'])})",
                     f3(r["ndcgc@10"]), f"{f3(r['diff_vs_id_condensed'], True)} ({fp(r['p_holm_vs_id_condensed'])})",
                     pct(r["hole@10"]), f"{w}/{t}/{l}"])
cap = ("RQ5b (exploratory): tokenisation ablation, $k_1$=1.2, $b$=0.75 for every analyzer; all use Lucene's stopwords "
       "and the Porter stemmer unless stated. $\\Delta$ ($p_{\\text{Holm}}$): "
       "difference from the main analyzer, paired randomisation test, Holm over the 4 comparisons, for nDCG@10 and for "
       "condensed nDCG@10 separately. W/T/L: queries where the variant is better / equal / worse on nDCG@10. Only the main "
       "run was in the judging pool, so a high Hole@10 penalises a variant in nDCG@10 for documents nobody judged.")
R.write(TAB / "rq5_tok.tex", htb(R.latex_table(
    rows, ["Analyzer", "nDCG@10", "$\\Delta$ ($p_{\\text{Holm}}$)", "Cond.\\ nDCG@10", "$\\Delta$ ($p_{\\text{Holm}}$)",
           "Hole@10", "W/T/L"], "lcccccc", cap, "tab:rq5tok").replace("\\small\n", "\\small\\setlength{\\tabcolsep}{5pt}\n", 1)))

# ------------------------------------------------------------------ unjudged pairs an extra judging round would need
qrels = read_qrels(a.qrels)
unjudged = {}
for v in V:
    if v == "id":
        continue
    run = read_run(D / "tokenisation/runs" / f"bm25-{v}.run")
    unjudged[v] = {(q, d) for q in run for d, _ in rank_docs(run[q])[:10] if d not in qrels.get(q, {})}
union = set().union(*unjudged.values())

# ------------------------------------------------------------------ macros
pl, ns, nst = V["plain"], V["id-nostem"], V["id-nostop"]
mac = {
    "rqCommit": metas[0]["git"]["commit"][:7], "rqCorpusSha": sw["checks"]["corpus"]["sha256"][:12],
    "rqReproMax": f"{sw['checks']['reproduction']['max_abs_score_diff']:.0e}".replace("e-0", "\\times10^{-") + "}",
    "rqDefault": f3(dflt["ndcg@10"]), "rqCV": f3(cv["ndcg@10"]), "rqCVDiff": f3(cv["diff_vs_default"], True),
    "rqCVlo": f3(cv["diff_ci95"][0], True), "rqCVhi": f3(cv["diff_ci95"][1], True), "rqCVp": fp(cv["p_vs_default"]),
    "rqCVcDiff": f"{cv['diff_vs_default_condensed']:+.4f}".replace("-", "$-$").replace("+", "$+$"),
    "rqCVcp": fp(cv["p_vs_default_condensed"]), "rqCVHole": pct(cv["hole@10"]),
    "rqCVwins": str(cv["wins_ties_losses"][0]), "rqCVties": str(cv["wins_ties_losses"][1]),
    "rqCVlosses": str(cv["wins_ties_losses"][2]),
    "rqCVchosen": ", ".join(f"({c['k1']:g}, {c['b']:g})" for c in cv["chosen_per_fold"]),
    "rqSeedMin": f3(cv["other_seeds"]["min"]), "rqSeedMax": f3(cv["other_seeds"]["max"]),
    "rqSeedN": str(len(cv["other_seeds"]["values"])),
    "rqGridMin": f3(nd.min()), "rqAbove": str(int((nd > dflt["ndcg@10"] + 1e-12).sum())),
    "rqWithinN": str(len(within)), "rqWithinTwo": f"{100 * sw['share_within_0.02_of_default']:.0f}",
    "rqPlateauK": f"{min(p[0] for p in within):g}--{max(p[0] for p in within):g}",
    "rqPlateauB": f"{min(p[1] for p in within):g}--{max(p[1] for p in within):g}",
    "rqLowK": f"{f3(min(v['ndcg@10'] for p, v in grid.items() if p[0] <= 0.4))}--{f3(max(v['ndcg@10'] for p, v in grid.items() if p[0] <= 0.4))}",
    "rqCondBest": setting(oc_set), "rqCondBestC": f3(oc["ndcgc@10"]), "rqCondBestN": f3(oc["ndcg@10"]),
    "rqCondBestHole": pct(oc["hole@10"]),
    "rqRHoleN": f"{np.corrcoef(ho, nd)[0, 1]:.2f}".replace("-", "$-$"), "rqRHoleC": f"{np.corrcoef(ho, cd)[0, 1]:.2f}",
    "rqPlainDiff": f3(pl["diff_vs_id"], True), "rqPlainP": fp(pl["p_holm_vs_id"]),
    "rqPlainTies": str(pl["wins_ties_losses_vs_id"][1]), "rqPlainHole": pct(pl["hole@10"]),
    "rqPlainIdent": f3(pl["ndcg@10_identifier"]), "rqIdIdent": f3(V["id"]["ndcg@10_identifier"]),
    "rqPlainUnjudged": str(len(unjudged["plain"])),
    "rqNostemDiff": f3(ns["diff_vs_id"], True), "rqNostemP": fp(ns["p_holm_vs_id"]), "rqNostemHole": pct(ns["hole@10"]),
    "rqNostemC": f3(ns["ndcgc@10"]), "rqNostemCDiff": f3(ns["diff_vs_id_condensed"], True),
    "rqNostemCP": fp(ns["p_holm_vs_id_condensed"]),
    "rqNostemPara": f3(ns["ndcg@10_paraphrase"]), "rqIdPara": f3(V["id"]["ndcg@10_paraphrase"]),
    "rqNostopDiff": f3(nst["diff_vs_id"], True), "rqNostopP": fp(nst["p_holm_vs_id"]),
    "rqNostopCDiff": f3(nst["diff_vs_id_condensed"], True), "rqNostopCP": fp(nst["p_holm_vs_id_condensed"]),
    "rqNostopHole": pct(nst["hole@10"]), "rqUnjudgedUnion": str(len(union)),
    "rqNostopNeg": f3(nst["ndcg@10_negation"]), "rqIdNeg": f3(V["id"]["ndcg@10_negation"]),
}
(TAB / "rq5_macros.tex").write_text("% generated by scripts/make_rq5_report.py from deliverables/rq5 - do not edit\n"
                                    + "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in mac.items()))

# ------------------------------------------------------------------ figure: three heatmaps side by side
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

panels = [("nDCG@10", "ndcg@10", "Blues", 1, "{:.2f}"), ("Condensed nDCG@10", "ndcgc@10", "Blues", 1, "{:.2f}"),
          ("Hole@10 (%)", "hole@10", "Oranges", 100, "{:.0f}")]
fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.45), dpi=300)
for ax, (title, m, cmap, scale, _) in zip(axes, panels):
    G = np.array([[scale * grid[(k, b)][m] for b in BS] for k in K1S])
    im = ax.imshow(G, origin="lower", aspect="auto", cmap=cmap)
    ax.set_xticks(range(len(BS)), [f"{b:g}" for b in BS], fontsize=5, rotation=90)
    ax.set_yticks(range(len(K1S)), [f"{k:g}" for k in K1S], fontsize=5)
    ax.set_xlabel("$b$", fontsize=7, color=R.INK2)
    ax.set_ylabel("$k_1$", fontsize=7, color=R.INK2)
    ax.set_title(title, fontsize=8, color=R.INK)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cb.ax.tick_params(labelsize=5)
    marks = {"default": DEF}
    if m == "ndcgc@10":
        marks["best"] = oc_set
    for name, (k1, b) in marks.items():
        x, y = BS.index(b), K1S.index(k1)
        ax.add_patch(plt.Rectangle((x - 0.5, y - 0.5), 1, 1, fill=False, ec="#d6336c", lw=1.1))
        ax.annotate(name, (x, y + 0.55), fontsize=5, color="#d6336c", ha="center", va="bottom")
fig.tight_layout()
FIG.mkdir(parents=True, exist_ok=True)
fig.savefig(FIG / "rq5_sweep.pdf", bbox_inches="tight")
plt.close(fig)
print("wrote", TAB / "rq5_sweep.tex", TAB / "rq5_tok.tex", TAB / "rq5_macros.tex", FIG / "rq5_sweep.pdf")
