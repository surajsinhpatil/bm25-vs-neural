"""Dense plumbing tests with a tiny local model (see make_tiny_models.py).
Skipped unless IRPROJ_TINY points at the folder created by that script."""
import os
from pathlib import Path

import numpy as np
import pytest

TINY = os.environ.get("IRPROJ_TINY")
pytestmark = pytest.mark.skipif(not TINY, reason="set IRPROJ_TINY to run")

DOCS = [{"id": str(i), "title": t, "abstract": a} for i, (t, a) in enumerate([
    ("Padding oracle attacks", "We attack CBC mode in TLS 1.2 and show a padding oracle."),
    ("Membership inference", "Machine learning models leak whether a record was in the training set. " * 30),
    ("DNS cache poisoning", "Off-path attackers poison resolver caches."),
    ("Short", "x"),
])]


def test_e5_pooling_order_and_search():
    import torch
    from irproj.dense import DenseIndex, E5Encoder, EncodeStats
    enc = E5Encoder(model_name=str(Path(TINY) / "base"), device="cpu", max_length=64)
    st = EncodeStats()
    batch = enc.encode_docs(DOCS, batch_size=3, stats=st)
    single = np.stack([enc.encode_docs([d], batch_size=1)[0] for d in DOCS])
    np.testing.assert_allclose(batch, single, atol=1e-4)           # length sorting is undone correctly
    np.testing.assert_allclose(np.linalg.norm(batch, axis=1), 1, atol=1e-5)
    assert st.truncated == 1 and st.n == 4                          # the long abstract exceeds 64 tokens
    # manual mean pooling with the prefix
    text = "passage: " + DOCS[0]["title"] + ". " + DOCS[0]["abstract"]
    e = enc.tokenizer([text], return_tensors="pt")
    with torch.no_grad():
        h = enc.model(**e).last_hidden_state[0].mean(0)
    np.testing.assert_allclose(batch[0], (h / h.norm()).numpy(), atol=1e-4)
    idx = DenseIndex([d["id"] for d in DOCS], batch)
    run, lat = idx.search(batch[:2], ["q0", "q1"], k=3)
    assert list(run["q0"])[0] == "0" and len(run["q1"]) == 3 and len(lat) == 2


def test_specter2_adapters_switch(tmp_path):
    from irproj.dense import DenseIndex, Specter2Encoder
    enc = Specter2Encoder(base=str(Path(TINY) / "base"), doc_adapter=str(Path(TINY) / "proximity"),
                          query_adapter=str(Path(TINY) / "adhoc_query"), device="cpu", max_length=64)
    d = enc.encode_docs(DOCS)
    assert "proximity" in str(enc.model.active_adapters)
    q = enc.encode_queries(["padding oracle"])
    assert "adhoc_query" in str(enc.model.active_adapters)
    assert d.shape == (4, enc.dim) and q.shape == (1, enc.dim)
    idx = DenseIndex([x["id"] for x in DOCS], d)
    idx.save(tmp_path / "spec")
    idx2 = DenseIndex.load(tmp_path / "spec")
    np.testing.assert_array_equal(idx.emb, idx2.emb)
    assert idx2.doc_ids == idx.doc_ids
