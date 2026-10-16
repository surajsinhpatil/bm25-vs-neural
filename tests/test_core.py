"""Unit tests: run with  python -m pytest -q tests"""
import math
import random

import numpy as np
import pytest

from irproj.bm25 import BM25Index
from irproj.fusion import convex_combination, rrf
from irproj.metrics import per_query
from irproj.pool import agreement, assign_queries, build_pool, merge
from irproj.stats import bootstrap_ci, holm_bonferroni, paired_randomization_test, weighted_kappa
from irproj.tokenize import Analyzer, get_analyzer


# ----------------------------------------------------------------------------- tokeniser
def test_identifier_tokens_kept_and_split():
    toks, n = get_analyzer("id").analyze("Exploiting CVE-2021-44228 (Log4Shell) via SHA-256.")
    assert "cve-2021-44228" in toks and "2021" in toks and "44228" in toks and "cve" in toks
    assert "sha-256" in toks and "256" in toks
    assert "log4shell" in toks
    # parts do not count towards the document length: exploit, cve-..., log4shell, via, sha-256
    assert n == 5


def test_protocol_versions_normalised():
    a = get_analyzer("id")
    for s in ("TLS 1.3", "TLSv1.3", "TLS v1.3", "tls1.3"):
        assert "tls1.3" in a.tokens(s), s
    assert "http2" in a.tokens("HTTP/2 servers")


def test_plain_is_lucene_like():
    toks = get_analyzer("plain").tokens("The attacker's side-channel on TLS 1.3 isn't new")
    assert toks == ["attack", "side", "channel", "tl", "1.3", "isn't", "new"]


def test_stopwords_and_stemming():
    a = get_analyzer("id")
    assert a.tokens("attacks on the networks") == ["attack", "network"]
    assert get_analyzer("id-nostem").tokens("attacks on networks") == ["attacks", "networks"]
    assert "not" in get_analyzer("id-nostop").tokens("does not use")


def test_hyphenated_words_without_digits_split():
    assert get_analyzer("id").tokens("man-in-the-middle") == ["man", "middl"]


# ----------------------------------------------------------------------------- BM25
def _bm25_bruteforce(docs, query, an, k1, b):
    toks = [an.analyze(d) for d in docs]
    N = len(docs)
    avgdl = np.mean([l for _, l in toks])
    q = an.tokens(query)
    out = []
    for t, l in toks:
        s = 0.0
        for term in q:
            n_t = sum(term in tt for tt, _ in toks)
            if n_t == 0:
                continue
            f = t.count(term)
            idf = math.log(1 + (N - n_t + 0.5) / (n_t + 0.5))
            s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * l / avgdl))
        out.append(s)
    return np.array(out)


@pytest.mark.parametrize("k1,b", [(1.2, 0.75), (0.9, 0.4), (2.0, 0.0), (0.4, 1.0)])
def test_bm25_matches_formula(k1, b):
    docs = ["padding oracle attack on TLS 1.3 and CBC mode",
            "random oracle model proofs for signature schemes",
            "oracle oracle oracle in smart contracts and blockchain",
            "membership inference attack against machine learning models",
            "a survey of side-channel attacks on AES-128 implementations"]
    an = get_analyzer("id")
    idx = BM25Index(an).build([str(i) for i in range(len(docs))], docs)
    for q in ("oracle attack", "TLS 1.3 padding oracle", "AES-128 side channel", "nothing matches xyz"):
        np.testing.assert_allclose(idx.score(q, k1, b), _bm25_bruteforce(docs, q, an, k1, b), rtol=1e-5, atol=1e-6)


def test_bm25_search_ranks_and_drops_zero():
    idx = BM25Index(get_analyzer("id")).build(["a", "b", "c"], ["dns cache poisoning", "data poisoning", "web"])
    res = idx.search("dns cache poisoning", k=10)
    assert list(res)[0] == "a" and "c" not in res


def test_bm25_save_load(tmp_path):
    idx = BM25Index(get_analyzer("id")).build(["a", "b"], ["tls 1.3 attack", "quic"])
    idx.save(tmp_path / "i.pkl")
    idx2 = BM25Index.load(tmp_path / "i.pkl")
    assert idx2.search("tls 1.3") == idx.search("tls 1.3")


# ----------------------------------------------------------------------------- metrics
def test_metrics_match_pytrec_eval():
    pytrec_eval = pytest.importorskip("pytrec_eval")
    rng = random.Random(1)
    qrels, run = {}, {}
    for q in range(30):
        qid = f"q{q}"
        docs = [f"d{i}" for i in range(40)]
        qrels[qid] = {d: rng.choice([0, 0, 1, 2, 3]) for d in rng.sample(docs, 20)}
        # many ties on purpose: scores drawn from a few values
        run[qid] = {d: float(rng.choice([1, 2, 3, 4, 5])) for d in rng.sample(docs, 25)}
    qrels["q0"] = {d: 0 for d in qrels["q0"]}           # a query without relevant documents
    ours = per_query(run, qrels, ("ndcg@10", "ndcg@5", "p@5", "map@10", "recall@10", "mrr@10"), rel_level=2)
    ev = pytrec_eval.RelevanceEvaluator(qrels, {"ndcg_cut.5,10", "P.5", "map_cut.10", "recall.10"}, relevance_level=2)
    ref = ev.evaluate(run)
    top10 = {q: dict(sorted(r.items(), key=lambda x: (x[1], x[0]), reverse=True)[:10]) for q, r in run.items()}
    rr = pytrec_eval.RelevanceEvaluator(qrels, {"recip_rank"}, relevance_level=2).evaluate(top10)
    for q in qrels:
        assert ours["ndcg@10"][q] == pytest.approx(ref[q]["ndcg_cut_10"], abs=1e-9)
        assert ours["ndcg@5"][q] == pytest.approx(ref[q]["ndcg_cut_5"], abs=1e-9)
        assert ours["p@5"][q] == pytest.approx(ref[q]["P_5"], abs=1e-9)
        assert ours["map@10"][q] == pytest.approx(ref[q]["map_cut_10"], abs=1e-9)
        assert ours["recall@10"][q] == pytest.approx(ref[q]["recall_10"], abs=1e-9)
        assert ours["mrr@10"][q] == pytest.approx(rr[q]["recip_rank"], abs=1e-9)


def test_hole():
    pq = per_query({"q": {"a": 3, "b": 2, "c": 1}}, {"q": {"a": 1}}, ("hole@10",))
    assert pq["hole@10"]["q"] == pytest.approx(2 / 10)


# ----------------------------------------------------------------------------- stats
def test_permutation_test_behaviour():
    rng = np.random.default_rng(0)
    a = rng.uniform(size=50)
    _, p_same = paired_randomization_test(a, a + rng.normal(0, 1e-3, 50), n_perm=20000)
    _, p_diff = paired_randomization_test(a + 0.2, a, n_perm=20000)
    assert p_same > 0.05 and p_diff < 0.001
    d, p_exact = paired_randomization_test([1, 1, 1, 1, 1], [0, 0, 0, 0, 0])
    assert d == 1 and p_exact == pytest.approx(2 / 32)      # exact enumeration for small n


def test_holm():
    adj = holm_bonferroni({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj["a"][0] == pytest.approx(0.03) and adj["c"][0] == pytest.approx(0.06)
    assert adj["b"][0] == pytest.approx(0.06) and adj["a"][1] and not adj["b"][1]


def test_kappa_matches_sklearn():
    sk = pytest.importorskip("sklearn.metrics")
    rng = random.Random(3)
    y1 = [rng.randint(0, 3) for _ in range(300)]
    y2 = [min(3, max(0, y + rng.choice([-1, 0, 0, 1]))) for y in y1]
    for w in ("linear", "quadratic"):
        assert weighted_kappa(y1, y2, weights=w) == pytest.approx(
            sk.cohen_kappa_score(y1, y2, weights=w, labels=[0, 1, 2, 3]), abs=1e-9)


def test_bootstrap_ci_contains_mean():
    m, lo, hi = bootstrap_ci([0.1, 0.5, 0.9, 0.3, 0.7])
    assert lo <= m <= hi


# ----------------------------------------------------------------------------- fusion
def test_rrf():
    r1 = {"q": {"a": 3.0, "b": 2.0, "c": 1.0}}
    r2 = {"q": {"c": 0.9, "a": 0.8, "d": 0.1}}
    f = rrf([r1, r2], k=60)["q"]
    assert f["a"] == pytest.approx(1 / 61 + 1 / 62)
    assert f["c"] == pytest.approx(1 / 63 + 1 / 61)
    assert f["d"] == pytest.approx(1 / 63)
    assert max(f, key=f.get) == "a"


def test_cc():
    f = convex_combination({"q": {"a": 10, "b": 0}}, {"q": {"b": 1.0, "a": 0.0}}, alpha=0.7)["q"]
    assert f["a"] == pytest.approx(0.7) and f["b"] == pytest.approx(0.3)


# ----------------------------------------------------------------------------- pooling
def test_pool_and_assignment():
    runs = {"x": {"q1": {f"d{i}": 10 - i for i in range(10)}},
            "y": {"q1": {f"d{i}": i for i in range(5, 15)}}}
    pool = build_pool(runs, ["q1"], depth=10, priority_depth=5)
    docs = [d for d, _ in pool["q1"]]
    assert len(docs) == 15 and len(set(docs)) == 15
    prio = {d for d, p in pool["q1"] if p}
    assert prio == {"d0", "d1", "d2", "d3", "d4", "d10", "d11", "d12", "d13", "d14"}
    assign = assign_queries([f"q{i}" for i in range(50)], ["A", "B", "C", "D"])
    load = {a: sum(a in v for v in assign.values()) for a in "ABCD"}
    assert all(len(set(v)) == 2 for v in assign.values())
    assert set(load.values()) == {25}


def test_merge_and_agreement():
    j = {"A": {("q", "d1"): 2, ("q", "d2"): 0, ("q", "d3"): 3},
         "B": {("q", "d1"): 2, ("q", "d2"): 1, ("q", "d3"): 3}}
    qrels, unresolved = merge(j)
    assert qrels["q"] == {"d1": 2, "d3": 3} and len(unresolved) == 1
    qrels, _ = merge(j, adjudicated={("q", "d2"): 1})
    assert qrels["q"]["d2"] == 1
    assert merge(j, fallback="lower")[0]["q"]["d2"] == 0
    assert agreement(j)["n"] == 3
