"""Print random abstracts from the frozen corpus to write or confirm queries around them
(Section 6.2 of the proposal: queries start from a randomly picked abstract, not from a search).
An optional --pattern (regular expression) restricts the sample, e.g. to abstracts containing
a CVE number for the identifier category. Use a new --seed for each batch you look at.

    python scripts/sample_anchors.py --corpus data/corpus/cscr.jsonl --n 5 --pattern "CVE-\\d{4}-\\d+"
"""
import argparse
import random
import re
import textwrap

from irproj.io import read_jsonl

ap = argparse.ArgumentParser()
ap.add_argument("--corpus", required=True)
ap.add_argument("--n", type=int, default=5)
ap.add_argument("--pattern", default=None)
ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args()

docs = list(read_jsonl(a.corpus))
if a.pattern:
    pat = re.compile(a.pattern, re.I)
    docs = [d for d in docs if pat.search(d["title"] + " " + d["abstract"])]
print(f"{len(docs)} candidate abstracts")
for d in random.Random(a.seed).sample(docs, min(a.n, len(docs))):
    print(f"\n{d['id']}  ({d['date']}, {' '.join(d['categories'])})\n{d['title']}")
    print(textwrap.fill(d["abstract"], 100))
