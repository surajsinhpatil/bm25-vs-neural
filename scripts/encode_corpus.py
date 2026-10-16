"""Step 2b: encode the corpus once with a dense model and cache the embeddings (GPU recommended).

    python scripts/encode_corpus.py --model e5 --corpus data/corpus/cscr.jsonl --out indexes/e5
    python scripts/encode_corpus.py --model specter2 --corpus data/corpus/cscr.jsonl --out indexes/specter2
"""
import argparse
import json

from irproj.dense import DenseIndex, EncodeStats, encoder_from_args
from irproj.efficiency import peak_rss_mb
from irproj.io import load_corpus

ap = argparse.ArgumentParser()
ap.add_argument("--model", choices=["e5", "specter2"], required=True)
ap.add_argument("--corpus", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--batch-size", type=int, default=64)
ap.add_argument("--device", default=None)
ap.add_argument("--model-name", default=None, help="override the HF id / local path (E5 model or SPECTER2 base)")
ap.add_argument("--adapters", nargs=2, default=None, metavar=("DOC", "QUERY"), help="SPECTER2 adapters")
a = ap.parse_args()

enc = encoder_from_args(a.model, a.model_name, a.adapters, a.device)
ids, docs = load_corpus(a.corpus)
stats = EncodeStats()
emb = enc.encode_docs(docs, batch_size=a.batch_size, stats=stats)
index = DenseIndex(ids, emb)
index.save(a.out)
info = {"model": a.model, "device": str(enc.device), "dim": int(emb.shape[1]),
        "index_mb": round(index.index_bytes() / 2**20, 2), "peak_rss_mb": round(peak_rss_mb(), 1),
        **stats.as_dict()}
try:
    import torch
    if torch.cuda.is_available():
        info["gpu"] = torch.cuda.get_device_name(0)
        info["peak_gpu_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
except Exception:
    pass
info.pop("lengths", None)
with open(a.out + ".encode.json", "w") as f:
    json.dump(info, f, indent=2)
print(json.dumps(info, indent=2))
