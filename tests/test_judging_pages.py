"""Tests for the judging pages. They use the real frozen pool (judging/round1/pool.json) and
the real topics, with a STAND-IN corpus: placeholder titles/abstracts for the pooled ids,
written to a temporary folder only. Run:  python -m pytest -q tests/test_judging_pages.py"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from irproj.io import load_topics, write_jsonl
from irproj.judging import (JudgingError, build_items, check_page, expected_pairs, load_pool, parse_page,
                            pool_as_pairs, write_page)

ROOT = Path(__file__).resolve().parents[1]
POOL = ROOT / "judging" / "round1" / "pool.json"
TOPICS = ROOT / "data" / "queries" / "topics.jsonl"
TRICKY = 'Uses n<10 & "quotes", <b>not bold</b> </script><script>window.HACKED=1</script> é中'


def stand_in_corpus(path, pool_obj, drop=None, blank=None):
    ids = sorted({x["docid"] for xs in pool_obj["pool"].values() for x in xs})
    rows = []
    for i, d in enumerate(ids):
        rows.append({"id": d, "title": f"Stand-in title {d}" if d != blank else "",
                     "abstract": f"Stand-in abstract for {d}. {TRICKY}",
                     "date": f"20{d[:2]}-{d[2:4]}-15", "year": 2000 + int(d[:2]),
                     "categories": ["cs.CR"], "primary": "cs.CR"})
    # a few extra documents so the practice queries retrieve something
    for j, t in enumerate(["password strength meters estimate guessability",
                           "reentrancy vulnerabilities in ethereum smart contracts",
                           "differential privacy for location data traces",
                           "breaking captchas with machine learning",
                           "private set intersection protocols efficiency"]):
        rows.append({"id": f"2001.{90000 + j}", "title": t, "abstract": t + " " + TRICKY,
                     "date": "2020-01-15", "year": 2020, "categories": ["cs.CR"], "primary": "cs.CR"})
    rows = [r for r in rows if r["id"] != drop]
    write_jsonl(path, rows)
    return {r["id"]: r for r in rows}


@pytest.fixture(scope="module")
def pool_obj():
    return load_pool(POOL)


@pytest.fixture(scope="module")
def topics():
    return {t["qid"]: t for t in load_topics(TOPICS, include_practice=True)}


@pytest.fixture(scope="module")
def pages(tmp_path_factory, pool_obj):
    """Run the real generation script on the stand-in corpus."""
    d = tmp_path_factory.mktemp("pages")
    stand_in_corpus(d / "corpus.jsonl", pool_obj)
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_judging_pages.py"),
                        "--pool", str(POOL), "--topics", str(TOPICS), "--corpus", str(d / "corpus.jsonl"),
                        "--out", str(d / "round1"), "--allow-sha-mismatch", "--zip", str(d / "out.zip")],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
    return d / "round1"


# ----------------------------------------------------------------------------- frozen pool
def test_frozen_pool_matches_recorded_counts(pool_obj):
    assert pool_obj["counts"] == {"queries": 50, "pairs": 1339, "priority": 722}
    assert sorted(pool_obj["annotators"]) == ["Saksham", "Suraj", "Swayam", "Tejas"]
    assert all(len(set(v)) == 2 for v in pool_obj["assignment"].values())
    per = {a: sum(a in v for v in pool_obj["assignment"].values()) for a in pool_obj["annotators"]}
    assert set(per.values()) == {25}


def test_pool_matches_committed_runs(pool_obj):
    from irproj.io import read_run
    from irproj.pool import build_pool
    runs = {s: read_run(ROOT / "runs" / f"{s}.run") for s in pool_obj["runs"]}
    rebuilt = build_pool(runs, list(pool_obj["assignment"]), pool_obj["depth"], pool_obj["priority_depth"])
    assert rebuilt == pool_as_pairs(pool_obj)


# ----------------------------------------------------------------------------- generated pages
def test_every_page_has_full_content_and_correct_assignment(pages, pool_obj, topics):
    for ann in pool_obj["annotators"]:
        page = pages / f"judge_{ann}.html"
        assert check_page(page, pool_obj, topics, ann) == []
        meta, items = parse_page(page)
        assert meta["annotator"] == ann and meta["pool-id"] == pool_obj["pool_id"]
        assert len(items) == len(expected_pairs(pool_obj, ann))
        for it in items:
            for f in ("query", "desc", "narr", "title", "abstract"):
                assert it[f].strip(), (ann, it["qid"], it["docid"], f)
            assert it["query"] == " ".join(topics[it["qid"]]["query"].split())
            assert bool(it["date"]) == (topics[it["qid"]]["category"] == "time")
        # phase 1 items come first
        phases = [int(it["phase"]) for it in items]
        assert phases == sorted(phases)


def test_practice_pages_are_not_empty(pages, topics):
    for ann in ("Suraj", "Tejas", "Swayam", "Saksham"):
        meta, items = parse_page(pages / f"practice_{ann}.html")
        assert items and {it["qid"] for it in items} <= {q for q, t in topics.items() if t["category"] == "practice"}
        assert check_page(pages / f"practice_{ann}.html", None, topics, ann) == []


def test_text_is_escaped_not_executed(pages):
    html = (pages / "judge_Suraj.html").read_text()
    assert "<script>window.HACKED" not in html and "&lt;/script&gt;" in html
    _, items = parse_page(pages / "judge_Suraj.html")
    assert TRICKY in items[0]["abstract"]


def test_pages_contain_no_grades_and_no_system_names(pages, pool_obj):
    import re
    html = (pages / "judge_Tejas.html").read_text()
    assert not re.search(r"\b(bm25|e5|specter2?|rrf)\b", html, re.I)
    body = html.split("<main>")[1].split("<script>")[0]
    assert not re.search(r'class="[^"]*\bsel\b', body)          # no pre-selected grade
    assert "Saved grade" not in body


def test_check_report_and_zip(pages):
    rep = json.loads((pages / "check_report.json").read_text())
    assert rep["ok"] and len(rep["pages"]) == 8
    import zipfile
    names = zipfile.ZipFile(pages.parent / "out.zip").namelist()
    assert "round1/judge_Suraj.html" in names and "round1/HOW_TO_JUDGE.md" in names


# ----------------------------------------------------------------------------- failures are caught
def test_blank_paper_is_refused(tmp_path, pool_obj, topics):
    blank = pool_obj["pool"]["1"][0]["docid"]
    docs = stand_in_corpus(tmp_path / "c.jsonl", pool_obj, blank=blank)
    with pytest.raises(JudgingError, match="empty title"):
        build_items(pool_as_pairs(pool_obj), topics, docs, ["1"], seed=1)


def test_blank_query_is_refused(tmp_path, pool_obj, topics):
    docs = stand_in_corpus(tmp_path / "c.jsonl", pool_obj)
    bad = dict(topics)
    bad["1"] = {**topics["1"], "narrative": "  "}
    with pytest.raises(JudgingError, match="empty narr"):
        build_items(pool_as_pairs(pool_obj), bad, docs, ["1"], seed=1)


def test_missing_document_is_refused(tmp_path, pool_obj, topics):
    gone = pool_obj["pool"]["2"][0]["docid"]
    docs = stand_in_corpus(tmp_path / "c.jsonl", pool_obj, drop=gone)
    with pytest.raises(JudgingError, match="not in the corpus"):
        build_items(pool_as_pairs(pool_obj), topics, docs, ["2"], seed=1)


def test_script_fails_on_missing_document(tmp_path, pool_obj):
    gone = pool_obj["pool"]["3"][0]["docid"]
    stand_in_corpus(tmp_path / "c.jsonl", pool_obj, drop=gone)
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_judging_pages.py"), "--pool", str(POOL),
                        "--corpus", str(tmp_path / "c.jsonl"), "--out", str(tmp_path / "o"), "--allow-sha-mismatch"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode != 0 and "not in this corpus" in (r.stdout + r.stderr)


def test_script_refuses_different_corpus_without_flag(tmp_path, pool_obj):
    stand_in_corpus(tmp_path / "c.jsonl", pool_obj)
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_judging_pages.py"), "--pool", str(POOL),
                        "--corpus", str(tmp_path / "c.jsonl"), "--out", str(tmp_path / "o")],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode != 0 and "not byte-identical" in (r.stdout + r.stderr)


def test_checker_flags_blank_fields(pages, tmp_path, pool_obj, topics):
    html = (pages / "judge_Swayam.html").read_text()
    i = html.index('<h2 class="title">') + len('<h2 class="title">')
    j = html.index("</h2>", i)
    (tmp_path / "bad.html").write_text(html[:i] + html[j:])
    probs = check_page(tmp_path / "bad.html", pool_obj, topics, "Swayam")
    assert any("blank title" in p for p in probs)


def test_checker_flags_missing_date_and_wrong_assignment(pages, tmp_path, pool_obj, topics):
    html = (pages / "judge_Saksham.html").read_text()
    k = html.index('<span class="date">') + len('<span class="date">')
    html2 = html[:k] + html[html.index("</span>", k):]
    (tmp_path / "nodate.html").write_text(html2)
    assert any("without the paper date" in p for p in check_page(tmp_path / "nodate.html", pool_obj, topics, "Saksham"))
    assert any("not assigned" in p or "missing" in p
               for p in check_page(pages / "judge_Saksham.html", pool_obj, topics, "Suraj"))


def test_checker_flags_old_script_only_page(tmp_path, pool_obj, topics):
    """The first version kept all text in a script; such a page must fail the check."""
    old = ('<div id="page-meta" data-annotator="Suraj"></div><aside><p class="q" id="query"></p>'
           '<p id="desc"></p><p id="narr"></p></aside><h2 class="doc-title" id="title"></h2>'
           '<script>const DATA = {"items": [{"qid": "1", "query": "x"}]};</script>')
    (tmp_path / "old.html").write_text(old)
    probs = check_page(tmp_path / "old.html", pool_obj, topics, "Suraj")
    assert any("no items" in p for p in probs)


def test_merge_refuses_exports_from_another_pool(tmp_path, pool_obj):
    q, d = expected_pairs(pool_obj, "Suraj")[0]
    good = {"annotator": "Suraj", "round": "main", "pool_id": pool_obj["pool_id"],
            "judgments": [{"qid": q, "docid": d, "grade": None}]}
    for name, body, ok in [("stale", {**good, "pool_id": "0000000000000000"}, False),
                           ("old_page", {k: v for k, v in good.items() if k != "pool_id"}, False),
                           ("not_assigned", {**good, "annotator": "Tejas"} if (q, d) not in
                            set(expected_pairs(pool_obj, "Tejas")) else None, False)]:
        if body is None:
            continue
        ex = tmp_path / name
        ex.mkdir()
        (ex / "judgments_x_main.json").write_text(json.dumps(body))
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "merge_judgments.py"), "--exports",
                            str(ex / "*.json"), "--out", str(tmp_path / "q"), "--pool", str(POOL)],
                           capture_output=True, text=True, cwd=ROOT)
        assert r.returncode != 0, name
        assert "ERROR" in r.stdout + r.stderr
