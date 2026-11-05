"""The live demo must show exactly the evaluated systems; the offline explorer must show the committed runs."""
import json
import random
import re
import subprocess
import sys
from pathlib import Path

from irproj.bm25 import BM25Index
from irproj.demo import Searcher
from irproj.fusion import rrf
from irproj.io import load_topics, rank_docs, read_qrels, read_run, write_jsonl, write_run
from irproj.tokenize import get_analyzer

ROOT = Path(__file__).resolve().parents[1]


def _corpus(n=400, seed=0):
    rng = random.Random(seed)
    topics = load_topics(ROOT / "data/queries/topics.jsonl")
    words = " ".join(t["query"] + " " + t["description"] for t in topics).split()
    return [{"id": f"{2100 + i // 1000}.{i:05d}", "title": " ".join(rng.sample(words, 6)),
             "abstract": " ".join(rng.choices(words, k=40)), "year": 2016 + i % 10} for i in range(n)], topics


class _FakeEncoder:
    """Deterministic stand-in for E5 (bag of hashed words), enough to test the plumbing."""
    def encode_queries(self, qs):
        import numpy as np
        v = np.zeros((len(qs), 64), dtype=np.float32)
        for i, q in enumerate(qs):
            for w in q.lower().split():
                v[i, hash(w) % 64] += 1
        return v


def test_demo_matches_batch_pipeline(tmp_path):
    import numpy as np
    from irproj.dense import DenseIndex
    docs, topics = _corpus()
    ids = [d["id"] for d in docs]
    enc = _FakeEncoder()
    emb = np.stack([enc.encode_queries([d["title"] + " " + d["abstract"]])[0] for d in docs])
    index = DenseIndex(ids, emb)
    # batch pipeline: run files with 6-decimal scores, fused from the files
    bm = BM25Index(get_analyzer("id")).build(ids, [d["title"] + " " + d["abstract"] for d in docs])
    queries = {t["qid"]: t["query"] for t in topics}
    run_bm, _ = bm.batch_search(queries, k=1000)
    run_e5, _ = index.search(enc.encode_queries(list(queries.values())), list(queries), k=1000)
    for name, run in (("bm25", run_bm), ("e5", run_e5)):
        write_run(tmp_path / f"{name}.run", run, name)
    write_run(tmp_path / "hyb.run", rrf([read_run(tmp_path / "bm25.run"), read_run(tmp_path / "e5.run")], k=60, depth=100), "h")
    ref = {"BM25": read_run(tmp_path / "bm25.run"), "E5": read_run(tmp_path / "e5.run"), "BM25+E5": read_run(tmp_path / "hyb.run")}
    s = Searcher(ids, docs, topics, {})
    s.add_dense("E5", enc, index)
    for t in topics:
        r = s.search(t["query"])
        for name, run in ref.items():
            assert [x["docid"] for x in r["systems"][name]["items"]] == [d for d, _ in rank_docs(run[t["qid"]])[:10]], (name, t["qid"])


def test_demo_marks_grades_and_unjudged():
    docs, topics = _corpus()
    s = Searcher([d["id"] for d in docs], docs, topics, {})
    t = topics[0]
    top = [x["docid"] for x in s.search(t["query"])["systems"]["BM25"]["items"]]
    s.qrels = {t["qid"]: {top[0]: 3, top[1]: 0}}
    r = s.search("  " + t["query"].upper() + " ")          # matched to the test query despite case/spaces
    items = r["systems"]["BM25"]["items"]
    assert r["topic"]["qid"] == t["qid"]
    assert [x["grade"] for x in items[:3]] == [3, 0, None] and items[2]["judged"] is False
    assert r["systems"]["BM25"]["ndcg@10"] is not None
    page = s.render(r)
    assert "never judged" in page and "test query" in page
    free = s.search("a query that is not a test query")
    assert free["topic"] is None and all(x["grade"] is None for x in free["systems"]["BM25"]["items"])
    assert "no human judgments" in s.render(free)


def test_explorer_shows_committed_runs_and_grades(tmp_path):
    out = tmp_path / "x.html"
    r = subprocess.run([sys.executable, str(ROOT / "scripts/make_results_explorer.py"), "--out", str(out)],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr[-2000:]
    data = json.loads(re.search(r"const D=(\{.*?\});\nconst CAT", out.read_text(encoding="utf-8"), re.S).group(1).replace("<\\/", "</"))
    qrels = read_qrels(ROOT / "data/qrels/qrels.txt")
    assert len(data["queries"]) == 50
    for q in data["queries"]:
        for name, f in [("BM25", "bm25"), ("E5", "e5"), ("BM25+E5", "bm25+e5"), ("SPECTER2", "specter2"), ("BM25+SPECTER2", "bm25+specter2")]:
            ref = [d for d, _ in rank_docs(read_run(ROOT / f"runs/{f}.run")[q["qid"]])[:10]]
            assert [d for d, _ in q["runs"][name]["docs"]] == ref
            assert all(g == qrels[q["qid"]][d] for d, g in q["runs"][name]["docs"])
            assert all(d in data["docs"] and data["docs"][d][0] for d in ref)
