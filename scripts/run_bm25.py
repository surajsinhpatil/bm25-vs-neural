"""Step 2a: BM25 run (our implementation).

    python scripts/run_bm25.py --corpus data/corpus/cscr.jsonl --topics data/queries/topics.jsonl \
        --analyzer id --k1 1.2 --b 0.75 --out runs/bm25.run
"""
import argparse
import time

from irproj.bm25 import BM25Index
from irproj.efficiency import latency_summary, save_efficiency
from irproj.io import doc_text, load_corpus, load_topics, write_run
from irproj.tokenize import get_analyzer

ap = argparse.ArgumentParser()
ap.add_argument("--corpus", required=True)
ap.add_argument("--topics", required=True)
ap.add_argument("--analyzer", default="id")
ap.add_argument("--k1", type=float, default=1.2)
ap.add_argument("--b", type=float, default=0.75)
ap.add_argument("--depth", type=int, default=1000)
ap.add_argument("--tag", default=None)
ap.add_argument("--out", required=True)
ap.add_argument("--index-out", default=None, help="optional path to pickle the index")
ap.add_argument("--include-practice", action="store_true")
a = ap.parse_args()

tag = a.tag or f"bm25-{a.analyzer}"
ids, docs = load_corpus(a.corpus)
t0 = time.perf_counter()
index = BM25Index(get_analyzer(a.analyzer)).build(ids, (doc_text(d) for d in docs))
t_index = time.perf_counter() - t0
topics = load_topics(a.topics, include_practice=a.include_practice)
queries = {t["qid"]: t["query"] for t in topics}
run, lat = index.batch_search(queries, k=a.depth, k1=a.k1, b=a.b)
write_run(a.out, run, tag, a.depth)
if a.index_out:
    index.save(a.index_out)
save_efficiency(a.out + ".eff.json", {
    "system": tag, "n_docs": index.n_docs, "vocab": len(index.vocab), "avgdl": index.avgdl,
    "index_seconds": round(t_index, 2), "index_mb": round(index.index_bytes() / 2**20, 2),
    "k1": a.k1, "b": a.b, "analyzer": a.analyzer, "hardware": "cpu",
    **latency_summary(lat)})
print(f"{tag}: {index.n_docs} docs, vocab {len(index.vocab)}, indexed in {t_index:.1f}s, "
      f"{len(run)} queries -> {a.out}")
