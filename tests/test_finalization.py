"""Tests for merging, adjudication, freezing, auditing and evaluation guards.
All grades here are synthetic and live only in temporary folders."""
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from irproj.judging import expected_pairs, load_pool
from irproj.pool import merge, read_adjudication

ROOT = Path(__file__).resolve().parents[1]
POOL = ROOT / "judging" / "round1" / "pool.json"
TOPICS = ROOT / "data" / "queries" / "topics.jsonl"
RUNS = [str(ROOT / "runs" / f"{s}.run") for s in ("bm25", "e5", "specter2", "bm25+e5", "bm25+specter2")]


def J(**kw):
    return {"A": {("q", d): g for d, g in kw.items() if d.startswith("a_")} | {("q", "x"): 1, ("q", "y"): 3},
            "B": {("q", "x"): 2, ("q", "y"): 3}}


# ----------------------------------------------------------------------------- merge
def test_merge_rules_and_provenance():
    j = {"A": {("q", "x"): 1, ("q", "y"): 3, ("q", "z"): 0}, "B": {("q", "x"): 2, ("q", "y"): 3, ("q", "z"): 3}}
    prov = []
    qrels, unresolved = merge(j, {("q", "x"): 2}, provenance=prov)
    assert qrels["q"] == {"x": 2, "y": 3} and [u["docid"] for u in unresolved] == ["z"]
    assert {r["docid"]: r["source"] for r in prov} == {"x": "adjudicated", "y": "agreed"}
    assert merge(j, fallback="lower")[0]["q"] == {"x": 1, "y": 3, "z": 0}
    assert merge(j, fallback="upper")[0]["q"] == {"x": 2, "y": 3, "z": 3}


def test_adjudication_cannot_override_agreement_or_add_pairs():
    j = {"A": {("q", "x"): 1, ("q", "y"): 3}, "B": {("q", "x"): 2, ("q", "y"): 3}}
    with pytest.raises(ValueError, match="not disagreements"):
        merge(j, {("q", "y"): 0})
    with pytest.raises(ValueError, match="not disagreements"):
        merge(j, {("q", "new"): 2})
    with pytest.raises(ValueError, match="not in 0-3"):
        merge(j, {("q", "x"): 5})


def test_read_adjudication_validates(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("qid,docid,final\n1,a,2\n1,b,\n")
    assert read_adjudication(p) == {("1", "a"): 2}
    p.write_text("qid,docid,final\n1,a,2.5\n")
    with pytest.raises(ValueError, match="must be 0, 1, 2 or 3"):
        read_adjudication(p)
    p.write_text("qid,docid,final\n1,a,high\n")
    with pytest.raises(ValueError, match="not a number"):
        read_adjudication(p)
    p.write_text("qid,docid,final\n1,a,2\n1,a,3\n")
    with pytest.raises(ValueError, match="two different final grades"):
        read_adjudication(p)


# ----------------------------------------------------------------------------- end-to-end with synthetic exports
def _exports(tmp_path, pool, conflict_every=7, drop=None, dup=None, bad=None):
    """Synthetic exports for the real pool: annotator grades equal except on every n-th pair."""
    d = tmp_path / "exports"
    d.mkdir(exist_ok=True)
    for ann in pool["annotators"]:
        js = []
        for i, (q, doc) in enumerate(expected_pairs(pool, ann)):
            g = (int(doc[-1]) % 4)
            if i % conflict_every == 0 and ann in ("Tejas", "Saksham"):
                g = (g + 1) % 4
            js.append({"qid": q, "docid": doc, "grade": g})
        if ann == drop:
            js = js[1:]
        if ann == dup:
            js.append(dict(js[0]))
        if ann == bad:
            js[0]["grade"] = 7
        (d / f"judgments_{ann}_main.json").write_text(json.dumps(
            {"annotator": ann, "round": "main", "pool_id": pool["pool_id"], "judgments": js}))
    return d


def run(*args):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, cwd=ROOT)


def test_audit_reports_problems(tmp_path):
    pool = load_pool(POOL)
    d = _exports(tmp_path, pool, drop="Suraj", dup="Tejas", bad="Swayam")
    r = run(ROOT / "scripts/audit_judgments.py", "--exports", d / "*.json", "--out", tmp_path / "audit")
    assert r.returncode == 0, r.stderr
    res = json.loads((tmp_path / "audit" / "audit.json").read_text())
    f = res["files"]
    assert len(f["judgments_Suraj_main.json"]["missing_expected"]) == 1
    assert len(f["judgments_Tejas_main.json"]["duplicates"]) == 1
    assert f["judgments_Swayam_main.json"]["invalid_grades"] == ["7"]
    assert res["summary"]["pairs_with_one_judgment"] == 2      # the dropped pair + the pair with an invalid grade
    assert res["problems"]


def test_freeze_requires_complete_adjudication(tmp_path):
    pool = load_pool(POOL)
    d = _exports(tmp_path, pool)
    out = tmp_path / "qrels"
    r = run(ROOT / "scripts/merge_judgments.py", "--exports", d / "*.json", "--out", out, "--pool", POOL)
    assert r.returncode == 2 and not (out / "qrels.txt").exists()
    sheet = tmp_path / "sheet.csv"
    r = run(ROOT / "scripts/make_adjudication_sheet.py", "--exports", d / "*.json", "--out", sheet)
    assert r.returncode == 0, r.stderr
    rows = list(csv.DictReader(open(sheet)))
    assert rows and all(row["grade_a"] != row["grade_b"] for row in rows)
    # fill only half: still refused
    for i, row in enumerate(rows):
        row["final"] = row["grade_a"] if i % 2 == 0 else ""
    with open(sheet, "w", newline="") as f:
        w = csv.DictWriter(f, lineterminator="\n", fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    r = run(ROOT / "scripts/merge_judgments.py", "--exports", d / "*.json", "--out", out, "--pool", POOL,
            "--adjudication", sheet, "--freeze")
    assert r.returncode == 2 and not (out / "qrels.txt").exists()
    # fill all: frozen with provenance
    for row in rows:
        row["final"] = row["grade_b"]
    with open(sheet, "w", newline="") as f:
        w = csv.DictWriter(f, lineterminator="\n", fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    r = run(ROOT / "scripts/merge_judgments.py", "--exports", d / "*.json", "--out", out, "--pool", POOL,
            "--adjudication", sheet, "--freeze")
    assert r.returncode == 0, r.stdout + r.stderr
    prov = json.loads((out / "provenance.json").read_text())
    assert prov["adjudicated"] == len(rows) and prov["agreed"] + prov["adjudicated"] == pool["counts"]["pairs"]
    assert (out / "qrels.sha256").read_text().split()[0] == prov["qrels_sha256"]
    lines = (out / "qrels.provenance.csv").read_text().splitlines()
    assert len(lines) == pool["counts"]["pairs"] + 1
    # a fallback can never be frozen
    r = run(ROOT / "scripts/merge_judgments.py", "--exports", d / "*.json", "--out", tmp_path / "q2", "--pool", POOL,
            "--fallback", "lower", "--freeze")
    assert r.returncode != 0 and "cannot be combined" in r.stdout + r.stderr


# ----------------------------------------------------------------------------- evaluation guards
def test_evaluate_refuses_empty_and_incompatible_qrels(tmp_path):
    empty = tmp_path / "empty.txt"
    empty.write_text("")
    r = run(ROOT / "scripts/evaluate.py", "--qrels", empty, "--topics", TOPICS, "--runs", *RUNS, "--out", tmp_path / "o",
            "--tables", tmp_path / "t", "--figures", tmp_path / "f")
    assert r.returncode != 0 and "no judgments" in r.stdout + r.stderr
    wrong = tmp_path / "wrong.txt"
    wrong.write_text("".join(f"{q} 0 9999.99999 2\n" for q in range(1, 51)))
    r = run(ROOT / "scripts/evaluate.py", "--qrels", wrong, "--topics", TOPICS, "--runs", *RUNS, "--out", tmp_path / "o",
            "--tables", tmp_path / "t", "--figures", tmp_path / "f", "--n-perm", "100")
    assert r.returncode != 0 and "retrieves no judged document" in r.stdout + r.stderr


def test_load_exports_rejects_invalid_grades(tmp_path):
    from irproj.pool import load_exports
    p = tmp_path / "e.json"
    p.write_text(json.dumps({"annotator": "A", "judgments": [{"qid": "1", "docid": "d", "grade": 4}]}))
    with pytest.raises(ValueError, match="invalid grade"):
        load_exports([p])
