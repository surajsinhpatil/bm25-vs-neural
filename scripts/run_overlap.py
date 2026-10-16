"""Judgment-free analysis: how much do the systems' top-10 lists overlap, per query category?
Low overlap between BM25 and a dense model means the hybrid has something to gain and the
pool is not dominated by one family. Useful before the qrels exist.

    python scripts/run_overlap.py --runs runs/bm25.run runs/e5.run runs/specter2.run \
        --topics data/queries/topics.jsonl --out results --tables report/tables
"""
import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np

from irproj import report as R
from irproj.io import load_topics, rank_docs, read_run

ap = argparse.ArgumentParser()
ap.add_argument("--runs", nargs="+", required=True)
ap.add_argument("--topics", required=True)
ap.add_argument("--k", type=int, default=10)
ap.add_argument("--out", default="results")
ap.add_argument("--tables", default="report/tables")
ap.add_argument("--label", default="")
a = ap.parse_args()

topics = load_topics(a.topics)
cats = ["identifier", "homonym", "negation", "time", "paraphrase"]
runs = {Path(p).stem: read_run(p) for p in a.runs}
top = {s: {q: [d for d, _ in rank_docs(r.get(q, {}))[:a.k]] for q in r} for s, r in runs.items()}
res = {}
for s1, s2 in combinations(runs, 2):
    key = f"{s1}|{s2}"
    res[key] = {}
    for c in cats + ["all"]:
        qs = [t["qid"] for t in topics if c == "all" or t["category"] == c]
        ov = [len(set(top[s1].get(q, [])) & set(top[s2].get(q, []))) / a.k for q in qs]
        res[key][c] = float(np.mean(ov)) if ov else float("nan")
Path(a.out).mkdir(parents=True, exist_ok=True)
Path(a.out, f"overlap{a.label}.json").write_text(json.dumps(res, indent=2))
rows = [[f"{R.pretty(k.split('|')[0])} / {R.pretty(k.split('|')[1])}"] + [R.fmt(v[c], 2) for c in cats + ["all"]]
        for k, v in res.items()]
R.write(Path(a.tables) / f"overlap{a.label}.tex", R.latex_table(
    rows, ["Pair"] + [R.CATEGORY_NAMES[c].split()[0] for c in cats] + ["All"], "l" + "c" * 6,
    f"Mean overlap of the top-{a.k} lists (fraction of shared documents), no judgments needed.",
    f"tab:overlap{a.label}"))
for k, v in res.items():
    print(f"{k:28s}" + " ".join(f"{c[:5]}={v[c]:.2f}" for c in cats + ["all"]))
