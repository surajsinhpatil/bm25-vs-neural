"""Error analysis from the actual runs and the human grades.

Every example shows each document's ORIGINAL grades from both annotators (e.g. "3" if they
agreed, "1|3" if they did not), so the analysis does not depend on how conflicts are resolved.
Metric values use the given qrels (state which ones in the report).

Outputs (markdown + json):
  * queries with the largest BM25 vs E5 differences, with each system's top-5 documents
  * grade-1 share of the top-10 per system and category (on negation and time queries a
    grade of 1 mostly means the paper breaks the exclusion or the date limit)
  * complementarity: relevant documents found in the top-10 by only one of BM25 / E5
  * queries where every system fails (nDCG@10 < 0.3)

    python scripts/error_analysis.py --qrels <qrels> --pages judging/round1 --out deliverables/analysis
"""
import argparse
import glob
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from irproj.io import load_topics, rank_docs, read_qrels, read_run
from irproj.judging import parse_page
from irproj.metrics import per_query
from irproj.pool import load_exports

ap = argparse.ArgumentParser()
ap.add_argument("--qrels", required=True)
ap.add_argument("--qrels-label", default="")
ap.add_argument("--topics", default="data/queries/topics.jsonl")
ap.add_argument("--exports", nargs="+", default=["judging/exports/judgments_*_main.json"])
ap.add_argument("--runs-dir", default="runs")
ap.add_argument("--pages", default=None, help="judging pages folder, for paper titles")
ap.add_argument("--corpus", default=None)
ap.add_argument("--out", default="deliverables/analysis")
ap.add_argument("--n-examples", type=int, default=4)
a = ap.parse_args()

SYS = ["bm25", "e5", "specter2", "bm25+e5", "bm25+specter2"]
NAME = {"bm25": "BM25", "e5": "E5", "specter2": "SPECTER2", "bm25+e5": "BM25+E5", "bm25+specter2": "BM25+SPECTER2"}
topics = {t["qid"]: t for t in load_topics(a.topics)}
qids = sorted(topics, key=int)
qrels = read_qrels(a.qrels)
runs = {s: read_run(Path(a.runs_dir) / f"{s}.run") for s in SYS}
judg = load_exports(sorted({p for pat in a.exports for p in glob.glob(pat)}))
orig = defaultdict(list)
for ann in sorted(judg):
    for k, g in judg[ann].items():
        orig[k].append(g)
titles = {}
if a.pages:
    for p in Path(a.pages).glob("judge_*.html"):
        for it in parse_page(p)[1]:
            titles[it["docid"]] = it["title"]
if a.corpus:
    from irproj.io import read_jsonl
    titles.update({d["id"]: d["title"] for d in read_jsonl(a.corpus)})
pq = {s: per_query(runs[s], qrels, ("ndcg@10",), 2, qids)["ndcg@10"] for s in SYS}
top = {s: {q: [d for d, _ in rank_docs(runs[s][q])[:10]] for q in qids} for s in SYS}


def g_str(q, d):
    gs = orig.get((q, d))
    if not gs:
        return "unjudged"
    return str(gs[0]) if len(set(gs)) == 1 else "|".join(str(x) for x in sorted(gs))


def doc_line(q, d, rank):
    t = titles.get(d, "")
    return f"{rank}. `{d}` [{g_str(q, d)}] {t[:110]}".rstrip()


res = {"qrels": a.qrels, "qrels_label": a.qrels_label}
L = [f"# Error analysis", "",
     f"Metric values use `{a.qrels}` ({a.qrels_label or 'see report'}). Grades in brackets are the two annotators' "
     "original grades: `3` = both gave 3, `1|3` = they disagreed." + ("" if titles else
     " Paper titles are not shown because the paper text was not available when this was generated "
     "(re-run with `--pages judging/round1`)."), ""]

# ---------------------------------------------------------------- BM25 vs E5 largest differences
diff = sorted(((pq["bm25"][q] - pq["e5"][q], q) for q in qids))
res["bm25_minus_e5"] = {q: d for d, q in diff}
L += ["## Where BM25 and E5 differ most", "",
      f"BM25 better on {sum(d > 1e-9 for d, _ in diff)} queries, E5 better on {sum(d < -1e-9 for d, _ in diff)}, "
      f"ties {sum(abs(d) <= 1e-9 for d, _ in diff)}.", ""]
for title, chosen in (("E5 much better than BM25", diff[:a.n_examples]),
                      ("BM25 much better than E5", diff[::-1][:a.n_examples])):
    L += [f"### {title}", ""]
    for d, q in chosen:
        t = topics[q]
        L += [f"**Query {q} ({t['category']}): \"{t['query']}\"**: nDCG@10 BM25 {pq['bm25'][q]:.3f}, "
              f"E5 {pq['e5'][q]:.3f}, BM25+E5 {pq['bm25+e5'][q]:.3f}", ""]
        for s in ("bm25", "e5"):
            L += [f"- {NAME[s]} top 5:"] + [f"  {doc_line(q, x, i + 1)}" for i, x in enumerate(top[s][q][:5])]
        L.append("")

# ---------------------------------------------------------------- grade-1 share by category
cats = ["identifier", "homonym", "negation", "time", "paraphrase"]
share = {s: {} for s in SYS}
for s in SYS:
    for c in cats:
        qs = [q for q in qids if topics[q]["category"] == c]
        vals = [np.mean([qrels[q].get(d, 0) == 1 for d in top[s][q]]) for q in qs]
        share[s][c] = float(np.mean(vals))
res["grade1_share_top10"] = share
L += ["## Share of the top 10 graded 1 (on topic, but does not answer the query or breaks a condition)", "",
      "| System | " + " | ".join(cats) + " |", "|---|" + "---|" * len(cats)]
L += [f"| {NAME[s]} | " + " | ".join(f"{share[s][c]:.2f}" for c in cats) + " |" for s in SYS]
L += ["", "On negation and time queries a grade of 1 is mostly a document that breaks the exclusion or the "
      "date limit, so a high share means the system ignores the condition.", ""]

# ---------------------------------------------------------------- complementarity
only_b, only_e, both = 0, 0, 0
per_cat = defaultdict(lambda: [0, 0, 0])
for q in qids:
    rb = {d for d in top["bm25"][q] if qrels[q].get(d, 0) >= 2}
    re_ = {d for d in top["e5"][q] if qrels[q].get(d, 0) >= 2}
    c = topics[q]["category"]
    only_b += len(rb - re_); only_e += len(re_ - rb); both += len(rb & re_)
    per_cat[c][0] += len(rb - re_); per_cat[c][1] += len(re_ - rb); per_cat[c][2] += len(rb & re_)
res["complementarity_relevant_top10"] = {"only_bm25": only_b, "only_e5": only_e, "both": both,
                                         "by_category": {c: dict(zip(("only_bm25", "only_e5", "both"), v)) for c, v in per_cat.items()}}
L += ["## Complementarity of BM25 and E5", "",
      f"Relevant documents (grade ≥ 2) in the top 10: found by both {both}, only by BM25 {only_b}, only by E5 {only_e}.", "",
      "| Category | Only BM25 | Only E5 | Both |", "|---|---|---|---|"]
L += [f"| {c} | {per_cat[c][0]} | {per_cat[c][1]} | {per_cat[c][2]} |" for c in cats]
L += ["", "Many relevant documents are found by only one of the two systems, which is why rank fusion "
      "can help even when neither component is better overall.", ""]

# ---------------------------------------------------------------- hard queries
hard = [q for q in qids if max(pq[s][q] for s in SYS) < 0.3]
res["all_systems_below_0.3"] = hard
L += ["## Queries where every system fails (best nDCG@10 < 0.3)", ""]
for q in hard:
    t = topics[q]
    n_rel = sum(g >= 2 for g in qrels[q].values())
    L.append(f"- Query {q} ({t['category']}): \"{t['query']}\". Best system {max(pq[s][q] for s in SYS):.3f}; "
             f"documents with grade ≥ 2 in the pool: {n_rel}")
if not hard:
    L.append("- none")
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
(out / "error_analysis.json").write_text(json.dumps(res, indent=2))
(out / "error_analysis.md").write_text("\n".join(L) + "\n")
print("\n".join(L[:12]))
print(json.dumps({k: res[k] for k in ("grade1_share_top10", "complementarity_relevant_top10", "all_systems_below_0.3")}, indent=1))
