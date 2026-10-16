"""S1: re-rank the top-100 of a run with an MS MARCO MiniLM cross-encoder [Nogueira & Cho 2019].

    python scripts/stretch_rerank.py --run runs/bm25+e5.run --corpus data/corpus/cscr.jsonl \
        --topics data/queries/topics.jsonl --out runs/ce.run
"""
import argparse
import time

import numpy as np

from irproj.efficiency import latency_summary, save_efficiency
from irproj.io import doc_text, load_corpus, load_topics, rank_docs, read_run, write_run

ap = argparse.ArgumentParser()
ap.add_argument("--run", required=True)
ap.add_argument("--corpus", required=True)
ap.add_argument("--topics", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--model", default="cross-encoder/ms-marco-MiniLM-L-6-v2")
ap.add_argument("--depth", type=int, default=100)
ap.add_argument("--batch-size", type=int, default=32)
ap.add_argument("--tag", default="ce")
a = ap.parse_args()

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
tok = AutoTokenizer.from_pretrained(a.model)
model = AutoModelForSequenceClassification.from_pretrained(a.model).to(dev).eval()
_, docs = load_corpus(a.corpus)
docs = {d["id"]: d for d in docs}
topics = {t["qid"]: t for t in load_topics(a.topics)}
base = read_run(a.run)
out, lat = {}, []
for qid, scores in base.items():
    if qid not in topics:
        continue
    cand = [d for d, _ in rank_docs(scores)[:a.depth]]
    t0 = time.perf_counter()
    s = []
    with torch.inference_mode():
        for i in range(0, len(cand), a.batch_size):
            chunk = cand[i:i + a.batch_size]
            enc = tok([topics[qid]["query"]] * len(chunk), [doc_text(docs[d]) for d in chunk],
                      padding=True, truncation="only_second", max_length=512, return_tensors="pt").to(dev)
            lg = model(**enc).logits.float()
            # MS MARCO cross-encoders have one output; a 2-class head uses the 'relevant' logit
            s.append((lg[:, 0] if lg.shape[-1] == 1 else lg[:, -1]).cpu().numpy())
    s = np.concatenate(s) if s else np.zeros(0)
    lat.append(time.perf_counter() - t0)
    out[qid] = {d: float(v) for d, v in zip(cand, s)}
write_run(a.out, out, a.tag, a.depth)
save_efficiency(a.out + ".eff.json", {"system": a.tag, "base_run": a.run, "hardware": str(dev),
                                      "note": "latency = re-ranking only (add the base run's latency)",
                                      **latency_summary(lat)})
print(f"re-ranked {len(out)} queries -> {a.out}")
