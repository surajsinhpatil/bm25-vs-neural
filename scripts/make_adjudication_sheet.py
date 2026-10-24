"""Write the adjudication sheet for every pair the two annotators graded differently.

Columns: priority, qid, category, query, description, what counts as relevant, docid, phase,
both annotators and grades, gap, whether the conflict crosses the relevance line (grade 2),
paper title / date / abstract (when --pages or --corpus is given), and empty `final`,
`rationale` and `adjudicated_by` columns for the team. Rows are ordered by priority:
  1 = 0 vs 3,  2 = gap of 2,  3 = gap of 1 that crosses relevant/non-relevant (1 vs 2),
  4 = gap of 1 on the same side (0 vs 1 or 2 vs 3).
The original grades are never changed; the sheet is the record of the adjudication.
Also writes an HTML copy for reading in the meeting.

    python scripts/make_adjudication_sheet.py --pages judging/round1      # text from the judging pages
    python scripts/make_adjudication_sheet.py --corpus data/corpus/cscr.jsonl
Fill `final` (0-3) in a copy, then:
    python scripts/finalize_qrels.py --adjudication <filled sheet>
"""
import argparse
import csv
import glob
import html
import json
from pathlib import Path

from irproj.io import load_topics
from irproj.judging import load_pool, parse_page
from irproj.pool import load_exports

ap = argparse.ArgumentParser()
ap.add_argument("--exports", nargs="+", default=["judging/exports/judgments_*_main.json"])
ap.add_argument("--pool", default="judging/round1/pool.json")
ap.add_argument("--topics", default="data/queries/topics.jsonl")
ap.add_argument("--pages", default=None, help="folder with the judge_*.html pages the annotators used")
ap.add_argument("--corpus", default=None, help="corpus JSONL (alternative source of the paper text)")
ap.add_argument("--out", default="deliverables/judging/adjudication_sheet.csv")
a = ap.parse_args()

paths = sorted({p for pat in a.exports for p in glob.glob(pat)})
pool = load_pool(a.pool)
judg = load_exports(paths)
topics = {t["qid"]: t for t in load_topics(a.topics)}
prio_pairs = {(q, x["docid"]) for q, xs in pool["pool"].items() for x in xs if x["priority"]}

text = {}
if a.pages:
    for p in sorted(Path(a.pages).glob("judge_*.html")):
        _, items = parse_page(p)
        for it in items:
            text[it["docid"]] = {"title": it["title"], "abstract": it["abstract"], "date": it["date"]}
if a.corpus:
    from irproj.io import read_jsonl
    for d in read_jsonl(a.corpus):
        text.setdefault(d["id"], {"title": d["title"], "abstract": d["abstract"], "date": d.get("date", "")})

rows = []
for q, assigned in pool["assignment"].items():
    x, y = sorted(assigned)
    for item in pool["pool"][q]:
        d = item["docid"]
        gx, gy = judg[x][(q, d)], judg[y][(q, d)]
        if gx == gy:
            continue
        gap = abs(gx - gy)
        cross = (gx >= 2) != (gy >= 2)
        priority = 1 if {gx, gy} == {0, 3} else 2 if gap == 2 else 3 if cross else 4
        t = topics[q]
        tx = text.get(d, {})
        rows.append({"priority": priority, "qid": q, "category": t["category"], "query": t["query"],
                     "description": t["description"], "relevance_criteria": t["narrative"], "docid": d,
                     "phase": 1 if (q, d) in prio_pairs else 2, "annotator_a": x, "grade_a": gx,
                     "annotator_b": y, "grade_b": gy, "gap": gap, "crosses_relevance_line": "yes" if cross else "no",
                     "title": tx.get("title", ""), "first_version_date": tx.get("date", "") if t["category"] == "time" else "",
                     "abstract": tx.get("abstract", ""), "final": "", "rationale": "", "adjudicated_by": ""})
rows.sort(key=lambda r: (r["priority"], int(r["qid"]), r["docid"]))
out = Path(a.out)
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, lineterminator="\n", fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

# HTML copy for the meeting (read-only; grades go into the CSV)
names = {1: "0 vs 3", 2: "gap of 2", 3: "1 vs 2 (crosses the relevance line)", 4: "gap of 1, same side"}
e = lambda s: html.escape(str(s))
parts = [f"<section><h2>{e(r['priority'])}. {names[r['priority']]} &middot; query {e(r['qid'])} ({e(r['category'])}) &middot; "
         f"{e(r['docid'])}</h2><p class='q'><b>Query:</b> {e(r['query'])}<br><b>Relevant if:</b> {e(r['relevance_criteria'])}</p>"
         f"<p><b>{e(r['annotator_a'])}: {r['grade_a']}</b> &nbsp; <b>{e(r['annotator_b'])}: {r['grade_b']}</b></p>"
         f"<h3>{e(r['title']) or '<i>title not available - run with --pages or --corpus</i>'}</h3>"
         + (f"<p class='d'>First version: {e(r['first_version_date'])}</p>" if r["first_version_date"] else "")
         + f"<p>{e(r['abstract'])}</p></section>" for r in rows]
(out.with_suffix(".html")).write_text(
    "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
    "<title>Adjudication</title><style>body{font:15px/1.5 system-ui,sans-serif;max-width:900px;margin:0 auto;padding:16px;"
    "background:#f7f7f5;color:#1d1d1b}section{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px 16px;margin:12px 0}"
    "h2{font-size:14px;color:#5f5e59;margin:0}.q{background:#fafaf8;padding:8px;border-radius:6px}h3{margin:8px 0 4px}"
    ".d{color:#5f5e59}</style></head><body>"
    f"<h1>Adjudication: {len(rows)} conflicting pairs</h1><p>Original grades are shown; record each final grade, "
    f"a one-line rationale and your names in the CSV (<code>{e(out.name)}</code>).</p>" + "".join(parts) + "</body></html>",
    encoding="utf-8")
counts = {names[k]: sum(r["priority"] == k for r in rows) for k in names}
missing_text = sum(1 for r in rows if not r["title"])
summary = {"conflicts": len(rows), "by_priority": counts, "rows_without_paper_text": missing_text,
           "sheet": str(out), "html": str(out.with_suffix(".html"))}
(out.parent / "adjudication_summary.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
