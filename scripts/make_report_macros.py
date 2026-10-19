"""Write report/tables/macros.tex: every number quoted in the report text, read from the
result files, so the text can never disagree with the tables. A value that does not exist
yet is printed as a red ?? in the PDF.

    python scripts/make_report_macros.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MISSING = r"\textcolor{red}{??}"


def load(rel):
    p = ROOT / rel
    return json.loads(p.read_text()) if p.exists() else None


def f(x, d=3):
    if x is None or (isinstance(x, float) and x != x):     # None or NaN
        return MISSING
    return f"{x:.{d}f}"


def i(x):
    return MISSING if x is None else f"{int(x):,}".replace(",", "{,}")


M = {}
man = load("data/corpus/cscr.jsonl.manifest.json") or {}
fc = man.get("filter_counts", {})
M["corpusN"] = i(man.get("n_docs"))
M["corpusPrimary"] = i(man.get("n_primary_cr"))
M["corpusInCat"] = i(fc.get("in_category"))
M["corpusFiltered"] = i(fc.get("after_filtering"))
M["corpusDup"] = i(fc.get("duplicate_title"))
M["corpusWithdrawn"] = i(fc.get("withdrawn"))
M["corpusSha"] = man["sha256"][:12] if man.get("sha256") else MISSING

sci = load("results/scifact_validation.json") or {}
res = sci.get("results", {})
M["sciDiff"] = f(sci.get("bm25_vs_pyserini_ndcg10_diff"), 4)
M["sciOverlap"] = f(100 * sci["bm25_vs_pyserini_top10_overlap"], 1) if "bm25_vs_pyserini_top10_overlap" in sci else MISSING
M["sciCritI"] = {True: "passes", False: "fails"}.get(sci.get("criterion_i_pass"), MISSING)
M["sciCritII"] = {True: "passes", False: "fails"}.get(sci.get("criterion_ii_pass"), MISSING)
for key, name in [("pyserini", "sciPys"), ("bm25-plain", "sciBMplain"), ("bm25", "sciBM"), ("e5", "sciEfive"),
                  ("specter2", "sciSpec"), ("bm25+e5", "sciHybE"), ("bm25+specter2", "sciHybS")]:
    M[name] = f(res.get(key, {}).get("ndcg@10"))

reu = load("results/offline_checks/reuters_validation.json") or {}
M["reuDiff"] = f(reu.get("bm25_vs_pyserini_ndcg10_diff"), 4)
M["reuOverlap"] = f(100 * reu["bm25_vs_pyserini_top10_overlap"], 1) if "bm25_vs_pyserini_top10_overlap" in reu else MISSING
M["reuRatio"] = f(reu.get("bm25_vs_pyserini_score_ratio", {}).get("mean"), 3)
M["reuDocs"] = i(reu.get("n_docs"))
M["reuQueries"] = i(reu.get("n_queries"))

for model, name in [("e5", "Efive"), ("specter2", "Spec")]:
    e = load(f"indexes/{model}.encode.json") or {}
    M[f"trunc{name}"] = f(e.get("truncated_pct"), 1)
    M[f"encMin{name}"] = f(e["seconds"] / 60, 1) if e.get("seconds") else MISSING
    M[f"medTok{name}"] = i(e.get("median_tokens"))
    if e.get("gpu"):
        M["gpuName"] = e["gpu"].replace("_", r"\_")
M.setdefault("gpuName", MISSING)

bm = load("runs/bm25.run.eff.json") or {}
M["bmIndexSec"] = f(bm.get("index_seconds"), 1)
M["bmIndexMB"] = f(bm.get("index_mb"), 1)
M["bmMs"] = f(bm.get("mean_ms"), 1)
M["bmVocab"] = i(bm.get("vocab"))

pool = load("judging/round1/pool_summary.json") or {}
M["poolSize"] = i(pool.get("pool_size"))
M["poolPerQ"] = f(pool.get("mean_per_query"), 1)
M["poolPrio"] = i(pool.get("priority_size"))

qc = load("results/query_check.json") or {}
M["anchorsFound"] = i(qc.get("anchors_found"))
M["anchorsMissing"] = i(len(qc["missing"])) if "missing" in qc else MISSING

ag = load("data/qrels/agreement.json") or {}
if not ag.get("n"):
    ag = {}
M["kappaLin"] = f(ag.get("kappa_linear"))
M["kappaQuad"] = f(ag.get("kappa_quadratic"))
M["nDouble"] = i(ag.get("n"))

ss = load("results/scifact_significance.json") or {}
for s_, name in [("e5", "Efive"), ("specter2", "Spec"), ("bm25+e5", "HybE"), ("bm25+specter2", "HybS")]:
    w = ss.get("win_tie_loss_vs_bm25", {}).get(s_)
    M[f"sciWin{name}"] = i(w["win"]) if w else MISSING
    M[f"sciLoss{name}"] = i(w["loss"]) if w else MISSING
for lo_, hi_ in [("bm25", "e5"), ("bm25", "specter2"), ("e5", "bm25+e5"), ("specter2", "bm25+specter2"), ("e5", "specter2")]:
    t = next((t for t in ss.get("tests", []) if t["a"] == lo_ and t["b"] == hi_), None)
    key = "sciP" + "".join(x.capitalize() for x in (lo_ + "-" + hi_).replace("+", "-").split("-")).replace("5", "five").replace("2", "two")
    M[key] = (r"$<$0.001" if t["p_holm"] < 0.001 else f(t["p_holm"], 3)) if t else MISSING

ov = load("results/overlap.json") or {}
for key, name in [("bm25|e5", "ovBE"), ("bm25|specter2", "ovBS"), ("e5|specter2", "ovES")]:
    M[name] = f(ov.get(key, {}).get("all"), 2)
    M[name + "Id"] = f(ov.get(key, {}).get("identifier"), 2)
    M[name + "Para"] = f(ov.get(key, {}).get("paraphrase"), 2)

# efficiency table for the cs.CR runs (does not need judgments)
import sys
sys.path.insert(0, str(ROOT / "src"))
from irproj import report as R  # noqa: E402
rows = []
for s in ["bm25", "e5", "specter2", "bm25+e5", "bm25+specter2"]:
    e = load(f"runs/{s}.run.eff.json")
    if e:
        rows.append([R.pretty(s), R.fmt(e.get("index_seconds"), 1), R.fmt(e.get("index_mb"), 1),
                     R.fmt(e.get("mean_ms"), 1), R.fmt(e.get("p95_ms"), 1),
                     str(e.get("hardware") or "--").replace("_", r"\_")])
if rows:
    R.write(ROOT / "report" / "tables" / "efficiency_prelim.tex", R.latex_table(
        rows, ["System", "Index (s)", "Index (MB)", "Query (ms)", "p95 (ms)", "Hardware"], "lccccl",
        "Efficiency on the cs.CR corpus. Dense indexing = encoding the corpus on the GPU; dense query time "
        "includes encoding the query; hybrid = sum of its components (p95 not defined).", "tab:eff"))

# values computed on Kaggle from files that are not in this checkout (corpus manifest, encoding
# logs, pool summary) are taken from the macros file written there, if it is given
import re
import argparse
ap = argparse.ArgumentParser()
ap.add_argument("--fallback", default=None, help="macros.tex produced on Kaggle")
args = ap.parse_args()
if args.fallback and Path(args.fallback).exists():
    for k, v in re.findall(r"\\newcommand\{\\(\w+)\}\{(.*)\}\n", Path(args.fallback).read_text()):
        if M.get(k, MISSING) == MISSING and v not in (MISSING, "nan"):
            M[k] = v

out = ROOT / "report" / "tables" / "macros.tex"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("% generated by scripts/make_report_macros.py - do not edit\n" +
               "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in M.items()))
missing = [k for k, v in M.items() if v == MISSING]
print(f"wrote {out} ({len(M)} values, {len(missing)} still missing: {missing})")
