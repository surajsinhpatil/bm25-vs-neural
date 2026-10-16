"""BM25 implemented from scratch on a SciPy sparse term-document matrix.

    BM25(q, d) = sum_{t in q} idf(t) * f_td (k1 + 1) / (f_td + k1 (1 - b + b |d| / avgdl))
    idf(t)     = ln(1 + (N - n_t + 0.5) / (n_t + 0.5))        (Lucene form, never negative)

The index stores raw term frequencies once. For a given (k1, b) the whole weighted
matrix is computed in one vectorised step, so a k1/b sweep only re-weights the matrix
and never re-tokenises the corpus. Query scoring is a single sparse matrix-vector product.
"""
from __future__ import annotations

import pickle
import time
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import scipy.sparse as sp

from .tokenize import Analyzer


class BM25Index:
    def __init__(self, analyzer: Analyzer):
        self.analyzer = analyzer
        self.vocab: Dict[str, int] = {}
        self.doc_ids: List[str] = []
        self.tf: sp.csc_matrix | None = None          # docs x terms, raw counts
        self.doc_len: np.ndarray | None = None
        self.df: np.ndarray | None = None
        self._weighted: Tuple[float, float, sp.csc_matrix] | None = None
        self.build_seconds = 0.0
        self.truncated_terms = 0

    # ------------------------------------------------------------------ indexing
    def build(self, doc_ids: Sequence[str], texts: Iterable[str]) -> "BM25Index":
        t0 = time.perf_counter()
        rows, cols, vals = [], [], []
        lengths = []
        vocab = self.vocab
        for i, text in enumerate(texts):
            toks, length = self.analyzer.analyze(text)
            lengths.append(length)
            for term, c in Counter(toks).items():
                j = vocab.get(term)
                if j is None:
                    j = vocab[term] = len(vocab)
                rows.append(i)
                cols.append(j)
                vals.append(c)
        self.doc_ids = list(doc_ids)
        n_docs = len(lengths)
        if n_docs != len(self.doc_ids):
            raise ValueError("number of texts and doc ids differ")
        self.tf = sp.csc_matrix(
            (np.asarray(vals, dtype=np.float32), (np.asarray(rows), np.asarray(cols))),
            shape=(n_docs, len(vocab)),
        )
        self.doc_len = np.asarray(lengths, dtype=np.float32)
        self.df = np.diff(self.tf.indptr).astype(np.float32)   # docs per term (CSC)
        self._weighted = None
        self.build_seconds = time.perf_counter() - t0
        return self

    @property
    def n_docs(self) -> int:
        return len(self.doc_ids)

    @property
    def avgdl(self) -> float:
        return float(self.doc_len.mean())

    def idf(self) -> np.ndarray:
        n = self.n_docs
        return np.log1p((n - self.df + 0.5) / (self.df + 0.5)).astype(np.float32)

    def weighted(self, k1: float, b: float) -> sp.csc_matrix:
        """Docs x terms matrix holding the full BM25 contribution of each (doc, term)."""
        if self._weighted and self._weighted[:2] == (k1, b):
            return self._weighted[2]
        tf = self.tf
        # row index of every stored entry in CSC order
        row_idx = tf.indices
        norm = k1 * (1.0 - b + b * self.doc_len / self.avgdl)          # per document
        f = tf.data
        w = f * (k1 + 1.0) / (f + norm[row_idx])
        col_idx = np.repeat(np.arange(tf.shape[1]), np.diff(tf.indptr))
        w = w * self.idf()[col_idx]
        mat = sp.csc_matrix((w.astype(np.float32), tf.indices, tf.indptr), shape=tf.shape)
        self._weighted = (k1, b, mat)
        return mat

    # ------------------------------------------------------------------ search
    def query_vector(self, query: str) -> Tuple[np.ndarray, np.ndarray]:
        toks = self.analyzer.tokens(query)
        counts = Counter(t for t in toks if t in self.vocab)
        if not counts:
            return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.float32)
        cols = np.fromiter((self.vocab[t] for t in counts), dtype=np.int64)
        vals = np.fromiter(counts.values(), dtype=np.float32)
        return cols, vals

    def score(self, query: str, k1: float = 1.2, b: float = 0.75) -> np.ndarray:
        W = self.weighted(k1, b)
        cols, vals = self.query_vector(query)
        if len(cols) == 0:
            return np.zeros(self.n_docs, dtype=np.float32)
        return np.asarray(W[:, cols] @ vals).ravel()

    def search(self, query: str, k: int = 1000, k1: float = 1.2, b: float = 0.75) -> Dict[str, float]:
        scores = self.score(query, k1, b)
        return top_k(scores, self.doc_ids, k)

    def batch_search(self, queries: Dict[str, str], k: int = 1000, k1: float = 1.2,
                     b: float = 0.75) -> Tuple[Dict[str, Dict[str, float]], List[float]]:
        """Returns (run, per-query latencies in seconds)."""
        self.weighted(k1, b)                       # build weights outside the timing
        run, lat = {}, []
        for qid, text in queries.items():
            t0 = time.perf_counter()
            run[qid] = self.search(text, k, k1, b)
            lat.append(time.perf_counter() - t0)
        return run, lat

    # ------------------------------------------------------------------ persistence
    def index_bytes(self) -> int:
        """Size of the inverted index in memory (postings + doc lengths + vocabulary)."""
        tf = self.tf
        vocab_bytes = sum(len(t.encode()) + 8 for t in self.vocab)
        return int(tf.data.nbytes + tf.indices.nbytes + tf.indptr.nbytes
                   + self.doc_len.nbytes + vocab_bytes)

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        state = dict(self.__dict__)
        state["_weighted"] = None
        with open(path, "wb") as f:
            pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def load(cls, path: str | Path) -> "BM25Index":
        with open(path, "rb") as f:
            state = pickle.load(f)
        obj = cls.__new__(cls)
        obj.__dict__.update(state)
        return obj


def top_k(scores: np.ndarray, doc_ids: Sequence[str], k: int) -> Dict[str, float]:
    """Top-k documents by score. Exact zeros are dropped: for BM25 a zero means the
    document shares no term with the query, so it is not retrieved at all."""
    k = min(k, len(scores))
    if k <= 0:
        return {}
    idx = np.argpartition(-scores, k - 1)[:k]
    idx = idx[np.argsort(-scores[idx], kind="stable")]
    return {doc_ids[i]: float(scores[i]) for i in idx if scores[i] != 0}
