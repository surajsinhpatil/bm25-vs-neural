"""Audit judgment exports against the frozen pool BEFORE anything is merged.

Checks, per file: valid JSON and schema, annotator/round/pool_id, grade values, duplicates,
missing / unexpected (qid, docid) pairs, null grades, practice-query contamination.
Across files: pairs judged by two annotators, single-judged pairs, agreement and conflicts,
weighted Cohen's kappa (linear and quadratic, 0-3 ordinal scale) on genuinely overlapping
ratings only, and a few diagnostics (grade distributions, identical-grade runs, export times).

Nothing is modified. Writes <out>/audit.json and <out>/audit_report.md.

    python scripts/audit_judgments.py --exports judging/exports/judgments_*_main.json \
        --pool judging/round1/pool.json --topics data/queries/topics.jsonl --out deliverables/judging
"""
import argparse
import glob
import hashlib
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

from irproj.io import load_topics
from irproj.judging import expected_pairs, load_pool
from irproj.stats import weighted_kappa

ap = argparse.ArgumentParser()
ap.add_argument("--exports", nargs="+", required=True)
ap.add_argument("--pool", default="judging/round1/pool.json")
ap.add_argument("--topics", default="data/queries/topics.jsonl")
ap.add_argument("--out", default="deliverables/judging")
a = ap.parse_args()

paths = sorted({p for pat in a.exports for p in glob.glob(pat)})
pool = load_pool(a.pool)
topics_all = {t["qid"]: t for t in load_topics(a.topics, include_practice=True)}
practice = {q for q, t in topics_all.items() if t.get("category") == "practice"}
cat = {q: t["category"] for q, t in topics_all.items()}
pool_pairs = {(q, x["docid"]) for q, xs in pool["pool"].items() for x in xs}
priority = {(q, x["docid"]) for q, xs in pool["pool"].items() for x in xs if x["priority"]}

files, grades, problems = {}, {}, []
for p in paths:
    raw = Path(p).read_bytes()
    rec = {"file": Path(p).name, "sha256": hashlib.sha256(raw).hexdigest()}
    try:
        d = json.loads(raw)
    except json.JSONDecodeError as e:
        rec["error"] = f"malformed JSON: {e}"
        problems.append(rec["error"])
        files[p] = rec
        continue
    ann = d.get("annotator")
    rec.update({k: d.get(k) for k in ("annotator", "round", "pool_id", "exported")})
    rec["schema_ok"] = set(d) >= {"annotator", "round", "pool_id", "judgments"} and all(
        set(j) >= {"qid", "docid", "grade"} for j in d.get("judgments", []))
    rec["pool_ok"] = d.get("pool_id") == pool["pool_id"]
    rec["round_ok"] = d.get("round") == pool["round"]
    js = d.get("judgments", [])
    keys = [(str(j.get("qid")), str(j.get("docid"))) for j in js]
    cnt = Counter(keys)
    rec["records"] = len(js)
    rec["duplicates"] = sorted([k for k, c in cnt.items() if c > 1])
    vals = [j.get("grade") for j in js]
    rec["null_grades"] = sum(v is None for v in vals)
    rec["invalid_grades"] = sorted({repr(v) for v in vals if v is not None and v not in (0, 1, 2, 3)})
    rec["missing_ids"] = sum(1 for q, dd in keys if q in ("", "None") or dd in ("", "None"))
    exp = set(expected_pairs(pool, ann)) if ann in pool["annotators"] else set()
    got = set(keys)
    rec["expected_pairs"] = len(exp)
    rec["missing_expected"] = sorted(exp - got)
    rec["unexpected"] = sorted(got - exp)
    rec["not_in_pool_at_all"] = sorted(got - pool_pairs)
    rec["practice_records"] = sum(q in practice for q, _ in keys)
    rec["queries"] = len({q for q, _ in keys})
    rec["expected_queries"] = sorted({q for q, v in pool["assignment"].items() if ann in v}, key=int)
    rec["grade_distribution"] = dict(sorted(Counter(v for v in vals if v is not None).items()))
    # longest run of identical consecutive grades (possible click-through) within the file order
    longest, cur = 0, 0
    for i, v in enumerate(vals):
        cur = cur + 1 if i and v == vals[i - 1] else 1
        longest = max(longest, cur)
    rec["longest_identical_run"] = longest
    # queries where every judged document got the same grade
    by_q = defaultdict(list)
    for (q, _), v in zip(keys, vals):
        by_q[q].append(v)
    rec["queries_all_same_grade"] = sorted([f"{q}:{set(v).pop()}" for q, v in by_q.items() if len(set(v)) == 1 and len(v) >= 5],
                                           key=lambda s: int(s.split(":")[0]))
    for k in ("duplicates", "missing_expected", "unexpected", "invalid_grades"):
        if rec[k]:
            problems.append(f"{rec['file']}: {len(rec[k])} {k}")
    if rec["null_grades"]:
        problems.append(f"{rec['file']}: {rec['null_grades']} records without a grade (not judged)")
    if not (rec["schema_ok"] and rec["pool_ok"] and rec["round_ok"]):
        problems.append(f"{rec['file']}: schema/pool/round mismatch")
    files[p] = rec
    # only valid grades for expected pairs enter the overlap / kappa computation (problems are reported above)
    grades[ann] = {k: v for k, v in zip(keys, vals) if v in (0, 1, 2, 3) and k in exp}

# ---------------------------------------------------------------- overlap
by_pair = defaultdict(dict)
for ann, gs in grades.items():
    for k, v in gs.items():
        by_pair[k][ann] = v
two = {k: v for k, v in by_pair.items() if len(v) == 2}
one = {k: v for k, v in by_pair.items() if len(v) == 1}
more = {k: v for k, v in by_pair.items() if len(v) > 2}
conf = {k: v for k, v in two.items() if len(set(v.values())) > 1}
y1, y2 = [], []
for k, v in sorted(two.items()):
    g = [v[x] for x in sorted(v)]
    y1.append(g[0]); y2.append(g[1])
diffs = Counter(abs(a_ - b_) for a_, b_ in zip(y1, y2))
pairwise = {}
for x, y in combinations(sorted(grades), 2):
    common = sorted(set(grades[x]) & set(grades[y]))
    if not common:
        continue
    g1 = [grades[x][k] for k in common]; g2 = [grades[y][k] for k in common]
    pairwise[f"{x}-{y}"] = {"n": len(common), "queries": len({q for q, _ in common}),
                            "kappa_linear": weighted_kappa(g1, g2, weights="linear"),
                            "kappa_quadratic": weighted_kappa(g1, g2, weights="quadratic"),
                            "kappa_unweighted": weighted_kappa(g1, g2, weights="none"),
                            "exact": float(np.mean([p == q for p, q in zip(g1, g2)])),
                            "binary_ge2_agreement": float(np.mean([(p >= 2) == (q >= 2) for p, q in zip(g1, g2)])),
                            "mean_grade": [float(np.mean(g1)), float(np.mean(g2))]}
b1 = [int(v >= 2) for v in y1]; b2 = [int(v >= 2) for v in y2]
per_q = {}
for q in sorted(pool["assignment"], key=int):
    ks = [k for k in two if k[0] == q]
    if ks:
        g = [[two[k][x] for x in sorted(two[k])] for k in ks]
        per_q[q] = {"category": cat[q], "pairs": len(ks), "exact": float(np.mean([u == v for u, v in g])),
                    "max_gap": max(abs(u - v) for u, v in g),
                    "gap_ge2": sum(abs(u - v) >= 2 for u, v in g),
                    "binary_disagree": sum((u >= 2) != (v >= 2) for u, v in g)}
summary = {
    "pool_id": pool["pool_id"], "pool_pairs": len(pool_pairs), "pool_priority_pairs": len(priority),
    "files": len(paths), "records_total": sum(f.get("records", 0) for f in files.values()),
    "unique_pairs_judged": len(by_pair), "pairs_with_two_judgments": len(two),
    "pairs_with_one_judgment": len(one), "pairs_with_more_than_two": len(more),
    "pool_pairs_with_no_judgment": len(pool_pairs - set(by_pair)),
    "agreeing_pairs": len(two) - len(conf), "conflicting_pairs": len(conf),
    "gap_distribution": {str(k): v for k, v in sorted(diffs.items())},
    "zero_vs_three": sum(1 for v in conf.values() if set(v.values()) == {0, 3}),
    "binary_relevance_disagreements": sum(u != v for u, v in zip(b1, b2)),
    "kappa_linear": weighted_kappa(y1, y2, weights="linear"),
    "kappa_quadratic": weighted_kappa(y1, y2, weights="quadratic"),
    "kappa_unweighted": weighted_kappa(y1, y2, weights="none"),
    "kappa_binary_ge2": weighted_kappa(b1, b2, labels=(0, 1), weights="none"),
    "exact_agreement": float(np.mean([u == v for u, v in zip(y1, y2)])) if y1 else None,
    "kappa_note": "Cohen's kappa over all double-judged pairs, annotators ordered alphabetically within each pair; "
                  "weights: linear |i-j|/3, quadratic ((i-j)/3)^2 on the 0-3 scale. Only pairs graded by both "
                  "assigned annotators are used; no missing rating is counted as 0.",
}
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
res = {"summary": summary, "files": {Path(p).name: f for p, f in files.items()}, "pairwise": pairwise,
       "per_query": per_q, "problems": problems,
       "single_judged_pairs": sorted([[q, d, list(v)[0]] for (q, d), v in one.items()]),
       "unjudged_pool_pairs": sorted([list(k) for k in pool_pairs - set(by_pair)])}
(out / "audit.json").write_text(json.dumps(res, indent=1))

# ---------------------------------------------------------------- markdown
L = ["# Judgment audit", "",
     f"Pool `{pool['pool_id']}` ({len(pool_pairs)} query-document pairs, {len(priority)} phase 1, "
     f"{len(pool['assignment'])} queries, 2 annotators per query). Files audited: {len(paths)}.", "",
     "## Per file", "",
     "| File | Annotator | Exported (UTC) | Records | Expected | Missing | Unexpected | Duplicates | Null grades | Invalid grades | Practice | Queries | Grade 0/1/2/3 |",
     "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for f in files.values():
    gd = f.get("grade_distribution", {})
    L.append(f"| {f['file']} | {f.get('annotator')} | {f.get('exported')} | {f.get('records')} | {f.get('expected_pairs')} | "
             f"{len(f.get('missing_expected', []))} | {len(f.get('unexpected', []))} | {len(f.get('duplicates', []))} | "
             f"{f.get('null_grades')} | {len(f.get('invalid_grades', []))} | {f.get('practice_records')} | "
             f"{f.get('queries')}/{len(f.get('expected_queries', []))} | "
             f"{gd.get(0, 0)}/{gd.get(1, 0)}/{gd.get(2, 0)}/{gd.get(3, 0)} |")
L += ["", "SHA-256 of each export:", ""] + [f"- `{f['file']}`: `{f['sha256']}`" for f in files.values()]
s = summary
L += ["", "## Across files", "",
      f"- Records in all files: {s['records_total']}",
      f"- Unique (query, document) pairs judged: {s['unique_pairs_judged']} of {s['pool_pairs']} pool pairs",
      f"- Pairs with two judgments: {s['pairs_with_two_judgments']}; with one: {s['pairs_with_one_judgment']}; "
      f"with more than two: {s['pairs_with_more_than_two']}; with none: {s['pool_pairs_with_no_judgment']}",
      f"- Agreeing pairs: {s['agreeing_pairs']}; conflicting pairs: {s['conflicting_pairs']}",
      f"- Grade gap distribution (|g1-g2|: count): {s['gap_distribution']}; 0-vs-3 conflicts: {s['zero_vs_three']}",
      f"- Disagreements on binary relevance (grade >= 2): {s['binary_relevance_disagreements']}",
      f"- Weighted Cohen's kappa: linear {s['kappa_linear']:.3f}, quadratic {s['kappa_quadratic']:.3f}; "
      f"unweighted {s['kappa_unweighted']:.3f}; binary (>=2) {s['kappa_binary_ge2']:.3f}; exact agreement {s['exact_agreement']:.3f}",
      f"- Method: {s['kappa_note']}", "",
      "## Per annotator pair", "",
      "| Pair | Shared pairs | Queries | κ linear | κ quadratic | Exact | Binary agreement | Mean grade (first, second) |",
      "|---|---|---|---|---|---|---|---|"]
for k, v in pairwise.items():
    L.append(f"| {k} | {v['n']} | {v['queries']} | {v['kappa_linear']:.3f} | {v['kappa_quadratic']:.3f} | {v['exact']:.3f} | "
             f"{v['binary_ge2_agreement']:.3f} | {v['mean_grade'][0]:.2f}, {v['mean_grade'][1]:.2f} |")
L += ["", "## Diagnostics (for the team, not evidence of a problem by themselves)", ""]
for f in files.values():
    L.append(f"- {f['annotator']}: longest run of identical consecutive grades {f['longest_identical_run']}; "
             f"queries (≥5 docs) where every document got one grade: {', '.join(f['queries_all_same_grade']) or 'none'}")
worst = sorted(per_q.items(), key=lambda kv: (kv[1]["exact"], -kv[1]["gap_ge2"]))[:10]
L += ["", "Queries with the lowest exact agreement:", "",
      "| Query | Category | Pairs | Exact | Gaps ≥ 2 | Binary disagreements |", "|---|---|---|---|---|---|"]
L += [f"| {q} | {v['category']} | {v['pairs']} | {v['exact']:.2f} | {v['gap_ge2']} | {v['binary_disagree']} |" for q, v in worst]
L += ["", "## Problems", ""] + ([f"- {p}" for p in problems] or ["- none found"])
(out / "audit_report.md").write_text("\n".join(L) + "\n")
print("\n".join(L))
