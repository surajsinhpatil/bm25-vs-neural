"""Turn NLTK's Reuters-21578 into a small BEIR-format collection for offline testing.
Queries are the headlines of 100 random test documents; a document is relevant (grade 1)
if it shares the query document's rarest topic category. The query document itself gets 2."""
import json, random, sys
from collections import Counter
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
cats = {}
for line in open(src / "cats.txt"):
    parts = line.split()
    cats[parts[0]] = parts[1:]
freq = Counter(c for cs in cats.values() for c in cs)
docs = {}
for key in cats:
    raw = (src / key).read_text(encoding="latin-1").strip().split("\n")
    title, text = raw[0].strip(), " ".join(l.strip() for l in raw[1:])
    if text:
        docs[key.replace("/", "_")] = (title, text, cats[key])
dst.mkdir(parents=True, exist_ok=True); (dst / "qrels").mkdir(exist_ok=True)
with open(dst / "corpus.jsonl", "w") as f:
    for d, (t, x, _) in docs.items():
        f.write(json.dumps({"_id": d, "title": t, "text": x}) + "\n")
rng = random.Random(0)
cands = sorted(d for d in docs if d.startswith("test") and len(docs[d][0].split()) >= 4)
qs = rng.sample(cands, 100)
by_cat = {}
for d, (_, _, cs) in docs.items():
    for c in cs: by_cat.setdefault(c, set()).add(d)
with open(dst / "queries.jsonl", "w") as fq, open(dst / "qrels" / "test.tsv", "w") as fr:
    fr.write("query-id\tcorpus-id\tscore\n")
    for i, d in enumerate(qs):
        qid = f"q{i}"
        fq.write(json.dumps({"_id": qid, "text": docs[d][0].lower()}) + "\n")
        rare = min(docs[d][2], key=lambda c: freq[c])
        for r in sorted(by_cat[rare])[:200]:
            fr.write(f"{qid}\t{r}\t{2 if r == d else 1}\n")
        if d not in by_cat[rare]: fr.write(f"{qid}\t{d}\t2\n")
print(len(docs), "docs")
