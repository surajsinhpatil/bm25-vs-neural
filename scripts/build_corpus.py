"""Step 1: build and freeze the cs.CR corpus from the Kaggle arXiv snapshot.

    python scripts/build_corpus.py --snapshot /kaggle/input/arxiv/arxiv-metadata-oai-snapshot.json \
        --out data/corpus/cscr.jsonl
"""
import argparse
import json

from irproj.corpus import build_corpus

ap = argparse.ArgumentParser()
ap.add_argument("--snapshot", required=True)
ap.add_argument("--out", default="data/corpus/cscr.jsonl")
ap.add_argument("--category", default="cs.CR")
ap.add_argument("--year-from", type=int, default=2016)
ap.add_argument("--year-to", type=int, default=2025)
ap.add_argument("--max-docs", type=int, default=50_000)
ap.add_argument("--seed", type=int, default=13)
a = ap.parse_args()

m = build_corpus(a.snapshot, a.out, a.category, a.year_from, a.year_to, a.max_docs, a.seed)
print(json.dumps(m, indent=2))
