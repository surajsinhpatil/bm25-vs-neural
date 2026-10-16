"""Check the query set against the frozen corpus before any system is run.

  * every anchor title is looked up (exact normalised match, then close match) and its arXiv id,
    date and categories are printed, so the team can confirm each query has a relevant document
  * queries without an anchor are listed: the team must find one by reading random abstracts
    (scripts/sample_anchors.py), NOT by running our retrieval systems
  * the time-constraint parser of stretch goal S2 is shown for the time queries

    python scripts/check_queries.py --corpus data/corpus/cscr.jsonl --topics data/queries/topics.jsonl
"""
import argparse
import difflib
import sys
from pathlib import Path

from irproj.corpus import norm_title
from irproj.io import load_topics, read_jsonl

sys.path.insert(0, str(Path(__file__).parent))
from stretch_time_filter import extract_rules  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--corpus", required=True)
ap.add_argument("--topics", required=True)
ap.add_argument("--out", default="results/query_check.json")
a = ap.parse_args()

docs = list(read_jsonl(a.corpus))
by_norm = {norm_title(d["title"]): d for d in docs}
norms = list(by_norm)
topics = load_topics(a.topics)
missing, found = [], 0
for t in topics:
    anchor = t.get("anchor_title")
    rng = extract_rules(t["query"]) if t["category"] == "time" else None
    extra = f"  date range parsed: {rng}" if t["category"] == "time" else ""
    if not anchor:
        missing.append(t["qid"])
        print(f"[{t['qid']:>2}] {t['category']:10s} NO ANCHOR  {t['query']}{extra}")
        continue
    n = norm_title(anchor)
    d = by_norm.get(n)
    how = "exact"
    if d is None:
        close = difflib.get_close_matches(n, norms, n=1, cutoff=0.9)
        d = by_norm[close[0]] if close else None
        how = "close"
    if d is None:
        missing.append(t["qid"])
        print(f"[{t['qid']:>2}] {t['category']:10s} ANCHOR NOT IN CORPUS: {anchor!r}{extra}")
    else:
        found += 1
        print(f"[{t['qid']:>2}] {t['category']:10s} anchor {how}: {d['id']} ({d['date']}) {d['title'][:70]}{extra}")
print(f"\n{found} anchors found; {len(missing)} queries still need a confirmed relevant document: {missing}")
import json
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text(json.dumps({"anchors_found": found, "missing": missing, "n_topics": len(topics)}, indent=2))
