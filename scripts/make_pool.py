"""Step 3a: pool the top-10 of every run, assign queries to annotators and FREEZE the result
in <out>/pool.json. No corpus is needed; the pages are generated from this file by
scripts/make_judging_pages.py (step 3b).

    python scripts/make_pool.py --runs runs/bm25.run runs/e5.run runs/specter2.run \
        runs/bm25+e5.run runs/bm25+specter2.run --topics data/queries/topics.jsonl \
        --annotators Suraj Tejas Swayam Saksham --out judging/round1

For a later round (e.g. stretch-goal runs) pass --already-judged data/qrels/qrels.txt so only
new documents are pooled. That file must contain the frozen judgments of the earlier round:
an empty or missing file is refused.
"""
import argparse
import json
from pathlib import Path

from irproj.io import load_topics, read_run, require_qrels
from irproj.judging import freeze_pool
from irproj.pool import assign_queries, build_pool

ap = argparse.ArgumentParser()
ap.add_argument("--runs", nargs="+", required=True)
ap.add_argument("--topics", required=True)
ap.add_argument("--annotators", nargs="+", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--depth", type=int, default=10)
ap.add_argument("--priority-depth", type=int, default=5)
ap.add_argument("--per-query", type=int, default=2)
ap.add_argument("--already-judged", default=None)
ap.add_argument("--round", default="main")
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--force", action="store_true", help="overwrite an existing pool.json")
a = ap.parse_args()

out = Path(a.out) / "pool.json"
if out.exists() and not a.force:
    raise SystemExit(f"{out} already exists. Pools are frozen; pass --force only if you really mean to replace it.")
topics_all = load_topics(a.topics)                 # main queries only; practice is handled at render time
main_q = [t["qid"] for t in topics_all]
runs = {Path(p).stem: read_run(p) for p in a.runs}
for name, run in runs.items():
    missing = [q for q in main_q if not run.get(q)]
    if missing:
        raise SystemExit(f"run {name} has no results for queries {missing[:10]}")
judged = require_qrels(a.already_judged) if a.already_judged else None

pool = build_pool(runs, main_q, a.depth, a.priority_depth, judged)
assign = assign_queries(main_q, a.annotators, a.per_query, a.seed)
obj = freeze_pool(out, pool, assign, a.annotators, a.runs, a.round, a.depth, a.priority_depth, a.seed)
per_ann = {ann: sum(len(pool[q]) for q in main_q if ann in assign[q]) for ann in a.annotators}
print(json.dumps({"pool": str(out), "pool_id": obj["pool_id"], **obj["counts"],
                  "pairs_per_annotator": per_ann}, indent=2))
