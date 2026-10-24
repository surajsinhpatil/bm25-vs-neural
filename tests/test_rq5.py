"""Tests for RQ5 (BM25 sweep + tokenisation ablation): run with  python -m pytest -q tests"""
import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from irproj import rq5
from irproj.bm25 import BM25Index
from irproj.io import load_topics, read_qrels, sha256_file, write_jsonl, write_qrels, write_run
from irproj.metrics import condensed_ndcg_at_k, ndcg_at_k, per_query
from irproj.tokenize import get_analyzer

ROOT = Path(__file__).resolve().parents[1]
CATS = ["identifier", "homonym", "negation", "time", "paraphrase"]


# ----------------------------------------------------------------------------- frozen-path guard
@pytest.mark.parametrize("rel", ["data/qrels/qrels.txt", "data/qrels/new.txt", "judging/exports/x.json",
                                 "judging/adjudication/x.csv", "runs/bm25-plain.run", "deliverables/final/rq5/x.json",
                                 "deliverables/preliminary/x", "data/qrels"])
def test_guard_refuses_frozen_locations(rel):
    with pytest.raises(SystemExit):
        rq5.guard_output(ROOT / rel)


@pytest.mark.parametrize("rel", ["deliverables/rq5/sweep/x.json", "report/tables/rq5_sweep.tex", "deliverables/rq5"])
def test_guard_allows_rq5_locations(rel):
    assert rq5.guard_output(ROOT / rel) == (ROOT / rel).resolve()


def test_guard_allows_paths_outside_repo(tmp_path):
    assert rq5.guard_output(tmp_path / "x") == (tmp_path / "x").resolve()


# ----------------------------------------------------------------------------- input checks
def test_frozen_qrels_verify():
    q = ROOT / "data/qrels/qrels.txt"
    assert rq5.verify_qrels(q, rq5.frozen_qrels_sha()) == sha256_file(q)
    with pytest.raises(SystemExit):
        rq5.verify_qrels(q, "0" * 64)


def test_verify_corpus(tmp_path):
    c = tmp_path / "c.jsonl"
    write_jsonl(c, [{"id": "1", "title": "a", "abstract": "b"}])
    sha = sha256_file(c)
    e = tmp_path / "e.json"
    e.write_text(json.dumps({"n_docs": 1, "sha256_prefix": sha[:12]}))
    assert rq5.verify_corpus(c, 1, e)["match"] is True
    assert rq5.verify_corpus(c, 2, e)["match"] is False
    e.write_text(json.dumps({"n_docs": 1, "sha256_prefix": "000000000000"}))
    assert rq5.verify_corpus(c, 1, e)["match"] is False
    # skipping must be explicit; a missing file is an error, never a silent skip
    assert rq5.verify_corpus(c, 1, "none")["match"] is None and rq5.verify_corpus(c, 1, "none")["skipped"]
    with pytest.raises(SystemExit):
        rq5.verify_corpus(c, 1, tmp_path / "missing.json")


def test_reproduction_check(tmp_path):
    run = {"1": {"a": 3.0, "b": 2.0, "c": 1.0}, "2": {"x": 1.5}}
    write_run(tmp_path / "r.run", run, "t")
    assert rq5.reproduction_check(run, tmp_path / "r.run")["ok"]
    swapped = {"1": {"a": 2.0, "b": 3.0, "c": 1.0}, "2": {"x": 1.5}}
    r = rq5.reproduction_check(swapped, tmp_path / "r.run")
    assert not r["ok"] and r["mismatched_queries"] == ["1"]
    shifted = {"1": {"a": 3.01, "b": 2.0, "c": 1.0}, "2": {"x": 1.5}}
    assert not rq5.reproduction_check(shifted, tmp_path / "r.run")["ok"]


# ----------------------------------------------------------------------------- condensed nDCG
def test_condensed_ndcg():
    judged = {"a": 2, "b": 0, "c": 3}
    ranked = ["u1", "a", "u2", "b", "c"]
    assert condensed_ndcg_at_k(ranked, judged, 3) == pytest.approx(ndcg_at_k(["a", "b", "c"], judged, 3))
    # with no unjudged documents it is plain nDCG
    assert condensed_ndcg_at_k(["c", "a", "b"], judged, 2) == ndcg_at_k(["c", "a", "b"], judged, 2)
    # unjudged documents lower nDCG but not condensed nDCG
    assert ndcg_at_k(ranked, judged, 3) < condensed_ndcg_at_k(ranked, judged, 3)


def test_condensed_ndcg_matches_pytrec_eval_on_filtered_run():
    pytrec_eval = pytest.importorskip("pytrec_eval")
    rng = random.Random(3)
    qrels = {str(q): {f"d{i}": rng.randint(0, 3) for i in range(0, 30, 2)} for q in range(5)}
    run = {q: {f"d{i}": rng.random() for i in range(30)} for q in qrels}
    ours = per_query(run, qrels, ("ndcgc@10",))["ndcgc@10"]
    filtered = {q: {d: s for d, s in r.items() if d in qrels[q]} for q, r in run.items()}
    ref = pytrec_eval.RelevanceEvaluator(qrels, {"ndcg_cut.10"}).evaluate(filtered)
    for q in qrels:
        assert ours[q] == pytest.approx(ref[q]["ndcg_cut_10"], abs=1e-12)


# ----------------------------------------------------------------------------- grid and CV
def test_grid_contains_reference_settings():
    grid = {(k, b) for k in rq5.K1_GRID for b in rq5.B_GRID}
    assert rq5.DEFAULT in grid and (0.9, 0.4) in grid and len(grid) == 132
    assert min(rq5.B_GRID) == 0.0 and max(rq5.B_GRID) == 1.0


def test_folds_on_real_topics_are_stratified_and_deterministic():
    topics = load_topics(ROOT / "data/queries/topics.jsonl")
    f1 = rq5.stratified_folds(topics, 5, rq5.CV_SEED)
    assert f1 == rq5.stratified_folds(topics, 5, rq5.CV_SEED)
    assert len(f1) == 50
    for f in range(5):
        for c in CATS:
            assert sum(1 for t in topics if t["category"] == c and f1[t["qid"]] == f) == 2
    assert f1 != rq5.stratified_folds(topics, 5, 101)


def test_cv_never_uses_held_out_queries():
    qids = [str(i) for i in range(10)]
    fold_of = {q: i % 2 for i, q in enumerate(qids)}
    # setting A is best on fold-0 queries only, B on fold-1 queries only
    A, B = (0.4, 0.3), (2.0, 1.0)
    scores = {A: {q: (1.0 if fold_of[q] == 0 else 0.0) for q in qids},
              B: {q: (1.0 if fold_of[q] == 1 else 0.0) for q in qids}}
    used, chosen = rq5.cv_select(scores, fold_of, 2)
    # fold 0 is held out -> chosen on fold 1 -> B, which scores 0 on fold 0
    assert all(used[q] == B for q in qids if fold_of[q] == 0)
    assert all(used[q] == A for q in qids if fold_of[q] == 1)
    assert np.mean([scores[used[q]][q] for q in qids]) == 0.0


def test_cv_ties_go_to_default():
    qids = ["1", "2", "3", "4"]
    fold_of = {"1": 0, "2": 0, "3": 1, "4": 1}
    scores = {(0.4, 0.3): {q: 0.5 for q in qids}, rq5.DEFAULT: {q: 0.5 for q in qids},
              (2.0, 1.0): {q: 0.5 for q in qids}}
    used, _ = rq5.cv_select(scores, fold_of, 2)
    assert set(used.values()) == {rq5.DEFAULT}
    assert rq5.best_setting(scores, qids) == rq5.DEFAULT


# ----------------------------------------------------------------------------- end to end (synthetic data)
@pytest.fixture(scope="module")
def synthetic(tmp_path_factory):
    """Small corpus, 10 queries (2 per category), qrels and a committed-style default run."""
    d = tmp_path_factory.mktemp("rq5")
    rng = random.Random(0)
    vocab = [f"w{i}" for i in range(80)]
    special = ["CVE-2021-44228", "TLS 1.3", "SHA-256", "attacks", "attacking", "not", "Tor"]
    docs = []
    for i in range(120):
        words = rng.choices(vocab, k=rng.randint(15, 60)) + rng.sample(special, 2)
        docs.append({"id": f"{2100 + i}.{i:05d}", "title": " ".join(words[:5]), "abstract": " ".join(words[5:])})
    write_jsonl(d / "corpus.jsonl", docs)
    topics = []
    for j in range(10):
        topics.append({"qid": str(j + 1), "category": CATS[j % 5], "query": " ".join(rng.sample(vocab, 3) + rng.sample(special, 1)),
                       "description": "", "narrative": ""})
    write_jsonl(d / "topics.jsonl", topics)
    index = BM25Index(get_analyzer("id")).build([x["id"] for x in docs], [x["title"] + " " + x["abstract"] for x in docs])
    run, _ = index.batch_search({t["qid"]: t["query"] for t in topics}, k=1000)
    write_run(d / "bm25.run", run, "bm25-id")
    qrels = {}
    for t in topics:     # judge the default top 10 (as the real pool did) plus a few random documents
        top = list(run[t["qid"]])[:10] + rng.sample([x["id"] for x in docs], 5)
        qrels[t["qid"]] = {doc: rng.randint(0, 3) for doc in top}
    write_qrels(d / "qrels.txt", qrels)
    exp = d / "EXPECTED.json"
    exp.write_text(json.dumps({"n_docs": len(docs), "sha256_prefix": sha256_file(d / "corpus.jsonl")[:12]}))
    return d


def _run(script, d, *extra):
    cmd = [sys.executable, str(ROOT / "scripts" / script), "--corpus", str(d / "corpus.jsonl"),
           "--topics", str(d / "topics.jsonl"), "--qrels", str(d / "qrels.txt"),
           "--expected-qrels-sha", sha256_file(d / "qrels.txt"), "--expected-corpus", str(d / "EXPECTED.json"),
           "--reference-run", str(d / "bm25.run"), *extra]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


def test_sweep_end_to_end(synthetic):
    d = synthetic
    r = _run("bm25_sweep.py", d, "--folds", "2", "--out", str(d / "out/sweep"), "--tables", str(d / "tab"))
    assert r.returncode == 0, r.stderr[-3000:]
    res = json.loads((d / "out/sweep/bm25_sweep.json").read_text())
    assert res["status"] == "EXPLORATORY"
    assert res["checks"]["reproduction"]["ok"] and res["checks"]["corpus"]["match"]
    assert res["checks"]["qrels_sha256"] == sha256_file(d / "qrels.txt")
    assert res["design"]["n_settings"] == 132
    # the default run is the pooled one: every top-10 document is judged
    assert res["default"]["hole@10"] == 0.0
    lo, hi = res["grid_range_ndcg@10"]
    assert lo <= res["default"]["ndcg@10"] <= hi and res["oracle_ndcg@10"]["ndcg@10"] == hi
    assert res["cv"]["ndcg@10"] <= hi
    grid_rows = (d / "out/sweep/bm25_sweep_grid.csv").read_text().strip().splitlines()
    assert len(grid_rows) == 133
    meta = json.loads((d / "out/sweep/metadata.json").read_text())
    assert meta["files_sha256"]["qrels"] == sha256_file(d / "qrels.txt") and meta["packages"]["numpy"]
    for f in ("bm25_sweep_ndcg10.pdf", "bm25_sweep_hole10.pdf", "bm25_sweep_cv_per_query.csv", "bm25_sweep_per_query.csv"):
        assert (d / "out/sweep" / f).exists()
    assert "tab:rq5sweep" in (d / "tab/rq5_sweep.tex").read_text()


def test_ablation_end_to_end(synthetic):
    d = synthetic
    r = _run("tokenizer_ablation.py", d, "--out", str(d / "out/tok"), "--tables", str(d / "tab"))
    assert r.returncode == 0, r.stderr[-3000:]
    res = json.loads((d / "out/tok/tokenizer_ablation.json").read_text())
    assert res["status"] == "EXPLORATORY" and res["checks"]["reproduction"]["ok"]
    v = res["variants"]
    assert list(v) == ["id", "plain", "id-nostem", "plain-nostem", "id-nostop"]
    assert v["id"]["hole@10"] == 0.0
    for name in list(v)[1:]:
        assert "p_holm_vs_id" in v[name] and v[name]["p_holm_vs_id"] >= v[name]["p_vs_id"] - 1e-12
    for name in v:
        assert (d / "out/tok/runs" / f"bm25-{name}.run").exists()
    assert "tab:rq5tok" in (d / "tab/rq5_tok.tex").read_text()


def test_scripts_stop_on_wrong_corpus(synthetic, tmp_path):
    d = synthetic
    bad = tmp_path / "EXPECTED.json"
    bad.write_text(json.dumps({"n_docs": 1, "sha256_prefix": "000000000000"}))
    for script in ("bm25_sweep.py", "tokenizer_ablation.py"):
        cmd = [sys.executable, str(ROOT / "scripts" / script), "--corpus", str(d / "corpus.jsonl"),
               "--topics", str(d / "topics.jsonl"), "--qrels", str(d / "qrels.txt"),
               "--expected-qrels-sha", sha256_file(d / "qrels.txt"), "--expected-corpus", str(bad),
               "--reference-run", str(d / "bm25.run"), "--out", str(tmp_path / script), "--tables", str(tmp_path / "t")]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        assert r.returncode != 0 and "not the one behind the frozen runs" in (r.stdout + r.stderr)


def test_scripts_stop_on_unfrozen_qrels(synthetic, tmp_path):
    d = synthetic
    r = subprocess.run([sys.executable, str(ROOT / "scripts/bm25_sweep.py"), "--corpus", str(d / "corpus.jsonl"),
                        "--topics", str(d / "topics.jsonl"), "--qrels", str(d / "qrels.txt"),
                        "--out", str(tmp_path / "o"), "--tables", str(tmp_path / "t")],
                       capture_output=True, text=True, cwd=ROOT)
    # without --expected-qrels-sha the frozen checksum is required, which the synthetic qrels do not have
    assert r.returncode != 0 and "frozen" in (r.stdout + r.stderr)
    assert not (tmp_path / "o").exists()


def test_scripts_refuse_frozen_output(synthetic):
    d = synthetic
    before = sha256_file(ROOT / "data/qrels/qrels.txt")
    r = _run("bm25_sweep.py", d, "--out", str(ROOT / "deliverables/final/rq5"), "--tables", str(d / "tab"))
    assert r.returncode != 0 and "frozen" in (r.stdout + r.stderr)
    assert not (ROOT / "deliverables/final/rq5").exists()
    r = _run("tokenizer_ablation.py", d, "--out", str(ROOT / "runs/ablation"), "--tables", str(d / "tab"))
    assert r.returncode != 0 and not (ROOT / "runs/ablation").exists()
    assert sha256_file(ROOT / "data/qrels/qrels.txt") == before


# ----------------------------------------------------------------------------- committed Kaggle outputs (24 Oct 2026)
RQ5 = ROOT / "deliverables/rq5"
REMAP = {"report/tables/rq5_sweep.tex": "deliverables/rq5/sweep/rq5_sweep.tex",
         "report/tables/rq5_tok.tex": "deliverables/rq5/tokenisation/rq5_tok.tex",
         "data/corpus/cscr.jsonl.manifest.json": "deliverables/rq5/kaggle_run/cscr.jsonl.manifest.json",
         "data/corpus/cscr.ids.txt": "deliverables/rq5/kaggle_run/cscr.ids.txt"}
needs_outputs = pytest.mark.skipif(not (RQ5 / "sweep/bm25_sweep.json").exists(), reason="RQ5 not run yet")


@needs_outputs
def test_committed_outputs_match_kaggle_checksums():
    n = 0
    for line in (RQ5 / "kaggle_run/rq5_outputs.sha256").read_text().splitlines():
        if line.startswith("#"):
            continue
        h, path = line.split(maxsplit=1)
        if path == "deliverables/rq5/README.md":      # documentation, edited after the run (noted in the file)
            continue
        assert sha256_file(ROOT / REMAP.get(path, path)) == h, path
        n += 1
    assert n >= 20


@needs_outputs
def test_committed_outputs_passed_every_check():
    exp = json.loads((ROOT / "data/corpus/EXPECTED.json").read_text())
    for sub, name in (("sweep", "bm25_sweep.json"), ("tokenisation", "tokenizer_ablation.json")):
        r = json.loads((RQ5 / sub / name).read_text())
        m = json.loads((RQ5 / sub / "metadata.json").read_text())
        assert r["status"] == "EXPLORATORY"
        assert r["checks"]["qrels_sha256"] == rq5.frozen_qrels_sha() == m["files_sha256"]["qrels"]
        assert r["checks"]["corpus"]["match"] is True and r["checks"]["corpus"]["sha256"].startswith(exp["sha256_prefix"])
        assert r["checks"]["corpus"]["n_docs"] == exp["n_docs"]
        assert r["checks"]["reproduction"]["ok"] and r["checks"]["reproduction"]["identical_topk"] == 50
        assert m["git"]["commit"] and m["git"]["dirty"] is False
        assert m["files_sha256"]["topics"] == sha256_file(ROOT / "data/queries/topics.jsonl")


@needs_outputs
def test_committed_default_equals_frozen_bm25_run():
    from irproj.io import read_run
    qrels = read_qrels(ROOT / "data/qrels/qrels.txt")
    frozen = per_query(read_run(ROOT / "runs/bm25.run"), qrels, ("ndcg@10",))["ndcg@10"]
    rebuilt = per_query(read_run(RQ5 / "tokenisation/runs/bm25-id.run"), qrels, ("ndcg@10",))["ndcg@10"]
    assert max(abs(frozen[q] - rebuilt[q]) for q in frozen) < 1e-5


@needs_outputs
def test_report_tables_are_reproducible(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "scripts/make_rq5_report.py"), "--tables", str(tmp_path / "t"),
                        "--figures", str(tmp_path / "f")], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr[-2000:]
    for f in ("rq5_sweep.tex", "rq5_tok.tex", "rq5_macros.tex"):
        assert (tmp_path / "t" / f).read_text() == (ROOT / "report/tables" / f).read_text(), f
    assert (tmp_path / "f/rq5_sweep.pdf").exists()


@needs_outputs
def test_report_script_rejects_unchecked_outputs(tmp_path):
    import shutil
    d = tmp_path / "rq5"
    shutil.copytree(RQ5, d)
    j = json.loads((d / "sweep/bm25_sweep.json").read_text())
    j["checks"]["corpus"]["skipped"], j["checks"]["corpus"]["match"] = True, None
    (d / "sweep/bm25_sweep.json").write_text(json.dumps(j))
    r = subprocess.run([sys.executable, str(ROOT / "scripts/make_rq5_report.py"), "--rq5", str(d),
                        "--tables", str(tmp_path / "t"), "--figures", str(tmp_path / "f")],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode != 0 and "corpus check failed or skipped" in (r.stdout + r.stderr)
    assert not (tmp_path / "t" / "rq5_sweep.tex").exists()


def test_heatmap_merges_labels_of_the_same_cell(tmp_path):
    grid = np.arange(4.0).reshape(2, 2)
    rq5.heatmap(tmp_path / "h.pdf", [1.0, 1.2], [0.5, 0.75], grid, "x", {"default": (1.2, 0.75), "best": (1.2, 0.75)})
    assert (tmp_path / "h.pdf").exists() and (tmp_path / "h.png").exists()
