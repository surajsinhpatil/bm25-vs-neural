"""Step 3: pool the top-10 of every run and write one blind judging page per annotator.

    python scripts/make_pool.py --runs runs/bm25.run runs/e5.run runs/specter2.run \
        runs/bm25+e5.run runs/bm25+specter2.run --topics data/queries/topics.jsonl \
        --corpus data/corpus/cscr.jsonl --annotators Suraj Tejas Swayam Saksham --out judging/round1

For a later round (e.g. stretch-goal runs) pass --already-judged data/qrels/qrels.txt so
only new documents are pooled.
"""
import argparse
import json
from pathlib import Path

from irproj.io import load_corpus, load_topics, read_qrels, read_run
from irproj.pool import assign_queries, build_pool, judging_items, write_judging_page

ap = argparse.ArgumentParser()
ap.add_argument("--runs", nargs="+", required=True)
ap.add_argument("--topics", required=True)
ap.add_argument("--corpus", required=True)
ap.add_argument("--annotators", nargs="+", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--depth", type=int, default=10)
ap.add_argument("--priority-depth", type=int, default=5)
ap.add_argument("--per-query", type=int, default=2)
ap.add_argument("--already-judged", default=None)
ap.add_argument("--round", default="main")
ap.add_argument("--seed", type=int, default=7)
a = ap.parse_args()

topics_all = load_topics(a.topics, include_practice=True)
topics = {t["qid"]: t for t in topics_all}
main_q = [t["qid"] for t in topics_all if t.get("category") != "practice"]
practice_q = [t["qid"] for t in topics_all if t.get("category") == "practice"]
runs = {Path(p).stem: read_run(p) for p in a.runs}
_, docs = load_corpus(a.corpus)
docs = {d["id"]: d for d in docs}
judged = read_qrels(a.already_judged) if a.already_judged else None

pool = build_pool(runs, main_q + practice_q, a.depth, a.priority_depth, judged)
assign = assign_queries(main_q, a.annotators, a.per_query, a.seed)
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)

summary = {"runs": list(runs), "depth": a.depth, "n_queries": len(main_q),
           "pool_size": sum(len(pool[q]) for q in main_q),
           "priority_size": sum(sum(p for _, p in pool[q]) for q in main_q),
           "mean_per_query": sum(len(pool[q]) for q in main_q) / max(len(main_q), 1),
           "assignment": assign, "annotators": {}}
for i, ann in enumerate(a.annotators):
    mine = [q for q in main_q if ann in assign[q]]
    items = judging_items(pool, topics, docs, mine, seed=a.seed * 100 + i)
    write_judging_page(out / f"judge_{ann}.html", ann, items, a.round)
    if practice_q:
        p_items = judging_items(pool, topics, docs, practice_q, seed=a.seed * 1000 + i)
        write_judging_page(out / f"practice_{ann}.html", ann, p_items, "practice")
    summary["annotators"][ann] = {"queries": len(mine), "documents": len(items)}

# the pool itself (with the systems that retrieved each doc) is kept separately, never shown to judges
with open(out / "pool_internal.json", "w") as f:
    json.dump({q: [d for d, _ in pool[q]] for q in pool}, f)
with open(out / "pool_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print(json.dumps({k: v for k, v in summary.items() if k != "assignment"}, indent=2))
