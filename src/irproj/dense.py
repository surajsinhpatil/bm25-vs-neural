"""Dense (bi-encoder) retrieval with E5-base-v2 and SPECTER2, used without fine-tuning.

* E5-base-v2 [Wang et al. 2022]: mean pooling, L2-normalised, inputs prefixed with
  "query: " / "passage: " as the model card requires.
* SPECTER2 [Singh et al. 2023]: specter2_base + adapters. Documents (title [SEP] abstract)
  are encoded with the *proximity* adapter, queries with the *ad-hoc query* adapter, as the
  authors recommend for search. The [CLS] vector is the embedding.

Search is exact (brute-force) cosine similarity, so no approximation error can affect
the comparison with BM25.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np


def _device(device: str | None):
    import torch
    if device:
        return torch.device(device)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


@dataclass
class EncodeStats:
    n: int = 0
    truncated: int = 0
    seconds: float = 0.0
    max_tokens: int = 0
    lengths: List[int] = field(default_factory=list)

    def as_dict(self) -> dict:
        arr = np.asarray(self.lengths) if self.lengths else np.zeros(1)
        return {"n": self.n, "truncated": self.truncated,
                "truncated_pct": 100.0 * self.truncated / max(self.n, 1),
                "seconds": round(self.seconds, 2), "max_tokens": self.max_tokens,
                "median_tokens": float(np.median(arr)), "p95_tokens": float(np.percentile(arr, 95))}


class _BaseEncoder:
    name = "base"
    max_length = 512

    def __init__(self, device: str | None = None, fp16: bool = True):
        self.device = _device(device)
        self.fp16 = fp16 and self.device.type == "cuda"

    # subclasses implement _forward(batch_texts) -> np.ndarray, and set self.tokenizer
    def _encode(self, texts: Sequence[str], batch_size: int, stats: EncodeStats | None) -> np.ndarray:
        import torch
        t0 = time.perf_counter()
        lengths = [len(x) for x in self.tokenizer(list(texts), add_special_tokens=True,
                                                   truncation=False)["input_ids"]]
        if stats is not None:
            stats.n += len(texts)
            stats.truncated += sum(l > self.max_length for l in lengths)
            stats.max_tokens = max([stats.max_tokens] + lengths)
            stats.lengths.extend(lengths)
        order = np.argsort(lengths)[::-1]               # longest first, fewer pad tokens
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        with torch.inference_mode():
            for s in range(0, len(texts), batch_size):
                idx = order[s:s + batch_size]
                batch = [texts[i] for i in idx]
                with torch.autocast(self.device.type, dtype=torch.float16, enabled=self.fp16):
                    emb = self._forward(batch)
                out[idx] = emb
        if stats is not None:
            stats.seconds += time.perf_counter() - t0
        return out

    @staticmethod
    def _normalize(x):
        import torch
        return torch.nn.functional.normalize(x.float(), p=2, dim=-1)


class E5Encoder(_BaseEncoder):
    name = "e5"

    def __init__(self, model_name: str = "intfloat/e5-base-v2", device: str | None = None,
                 fp16: bool = True, max_length: int = 512):
        super().__init__(device, fp16)
        from transformers import AutoModel, AutoTokenizer
        self.model_name = model_name
        self.max_length = max_length
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(self.device).eval()
        self.dim = self.model.config.hidden_size

    def _forward(self, batch: List[str]) -> np.ndarray:
        enc = self.tokenizer(batch, padding=True, truncation=True, max_length=self.max_length,
                             return_tensors="pt").to(self.device)
        hidden = self.model(**enc).last_hidden_state
        mask = enc["attention_mask"].unsqueeze(-1).to(hidden.dtype)
        pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
        return self._normalize(pooled).cpu().numpy()

    def encode_docs(self, docs: Sequence[dict], batch_size: int = 64, stats: EncodeStats | None = None):
        texts = ["passage: " + (d.get("title") or "").strip() + ". " + (d.get("abstract") or "").strip()
                 for d in docs]
        return self._encode(texts, batch_size, stats)

    def encode_queries(self, queries: Sequence[str], batch_size: int = 64, stats=None):
        return self._encode(["query: " + q for q in queries], batch_size, stats)


class Specter2Encoder(_BaseEncoder):
    name = "specter2"

    def __init__(self, base: str = "allenai/specter2_base",
                 doc_adapter: str = "allenai/specter2",
                 query_adapter: str = "allenai/specter2_adhoc_query",
                 device: str | None = None, fp16: bool = True, max_length: int = 512):
        super().__init__(device, fp16)
        from adapters import AutoAdapterModel
        from transformers import AutoTokenizer
        self.max_length = max_length
        self.tokenizer = AutoTokenizer.from_pretrained(base)
        self.model = AutoAdapterModel.from_pretrained(base)
        for path, name in ((doc_adapter, "proximity"), (query_adapter, "adhoc_query")):
            kwargs = {} if Path(path).exists() else {"source": "hf"}
            self.model.load_adapter(path, load_as=name, set_active=False, **kwargs)
        self.model.to(self.device).eval()
        self.dim = self.model.config.hidden_size

    def _forward(self, batch: List[str]) -> np.ndarray:
        enc = self.tokenizer(batch, padding=True, truncation=True, max_length=self.max_length,
                             return_tensors="pt", return_token_type_ids=False).to(self.device)
        out = self.model(**enc)
        cls = out.last_hidden_state[:, 0, :]
        return self._normalize(cls).cpu().numpy()

    def encode_docs(self, docs: Sequence[dict], batch_size: int = 32, stats: EncodeStats | None = None):
        self.model.set_active_adapters("proximity")
        sep = self.tokenizer.sep_token
        texts = [(d.get("title") or "").strip() + sep + (d.get("abstract") or "").strip() for d in docs]
        return self._encode(texts, batch_size, stats)

    def encode_queries(self, queries: Sequence[str], batch_size: int = 32, stats=None):
        self.model.set_active_adapters("adhoc_query")
        return self._encode(list(queries), batch_size, stats)


ENCODERS = {"e5": E5Encoder, "specter2": Specter2Encoder}


def get_encoder(name: str, **kwargs) -> _BaseEncoder:
    return ENCODERS[name](**kwargs)


def encoder_from_args(model: str, model_name: str | None = None, adapters=None, device=None):
    """CLI helper: --model-name overrides the HF id (E5) or the base model (SPECTER2);
    --adapters DOC QUERY overrides the two SPECTER2 adapters (HF ids or local folders)."""
    kwargs = {"device": device}
    if model == "e5" and model_name:
        kwargs["model_name"] = model_name
    if model == "specter2":
        if model_name:
            kwargs["base"] = model_name
        if adapters:
            kwargs["doc_adapter"], kwargs["query_adapter"] = adapters
    return get_encoder(model, **kwargs)


# --------------------------------------------------------------------------- search
class DenseIndex:
    """Exact cosine search over L2-normalised document embeddings."""

    def __init__(self, doc_ids: Sequence[str], emb: np.ndarray):
        if len(doc_ids) != emb.shape[0]:
            raise ValueError("doc ids and embeddings differ in length")
        self.doc_ids = list(doc_ids)
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        self.emb = (emb / np.clip(norms, 1e-12, None)).astype(np.float32)

    def index_bytes(self) -> int:
        return int(self.emb.nbytes)

    def search(self, q_emb: np.ndarray, qids: Sequence[str], k: int = 1000
               ) -> Tuple[Dict[str, Dict[str, float]], List[float]]:
        """Returns (run, per-query latency in seconds for the similarity + top-k step)."""
        q = q_emb / np.clip(np.linalg.norm(q_emb, axis=1, keepdims=True), 1e-12, None)
        run, lat = {}, []
        k = min(k, len(self.doc_ids))
        for i, qid in enumerate(qids):
            t0 = time.perf_counter()
            s = self.emb @ q[i].astype(np.float32)
            idx = np.argpartition(-s, k - 1)[:k]
            idx = idx[np.argsort(-s[idx], kind="stable")]
            run[qid] = {self.doc_ids[j]: float(s[j]) for j in idx}
            lat.append(time.perf_counter() - t0)
        return run, lat

    def save(self, path_prefix: str | Path) -> None:
        p = Path(path_prefix)
        p.parent.mkdir(parents=True, exist_ok=True)
        np.save(str(p) + ".npy", self.emb)
        Path(str(p) + ".ids.txt").write_text("\n".join(self.doc_ids) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path_prefix: str | Path) -> "DenseIndex":
        emb = np.load(str(path_prefix) + ".npy")
        ids = Path(str(path_prefix) + ".ids.txt").read_text(encoding="utf-8").split()
        return cls(ids, emb)
