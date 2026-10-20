"""Step 3b: generate the blind judging pages from a frozen pool and check them.

Inputs: the frozen pool (judging/round1/pool.json, committed), the topics (committed) and the
corpus JSONL. The corpus is not in the repository; if it is missing it is rebuilt from the
Kaggle arXiv snapshot with the same settings as before and its SHA-256 is compared with the
value recorded on 19 Oct 2026 (data/corpus/EXPECTED.json).

    # on Kaggle (arXiv dataset attached):
    python scripts/make_judging_pages.py --snapshot /kaggle/input/arxiv/arxiv-metadata-oai-snapshot.json \
        --zip /kaggle/working/judging_round1.zip

Nothing here uses qrels or earlier pages, and no grade is ever written into a page.
Practice pages: the 5 practice queries were not part of the runs, so their documents are the
BM25 top-6 from our own index (CPU, seconds). Practice grades are never used in evaluation.
Exit code 1 if any page has a blank field, a wrong assignment or a missing date.
"""
import argparse
import json
import sys
import zipfile
from pathlib import Path

from irproj.io import doc_text, load_corpus, load_topics, sha256_file
from irproj.judging import (JudgingError, build_items, check_page, expected_pairs, load_pool, pool_as_pairs,
                            write_page)

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--pool", default="judging/round1/pool.json")
ap.add_argument("--topics", default="data/queries/topics.jsonl")
ap.add_argument("--corpus", default="data/corpus/cscr.jsonl")
ap.add_argument("--snapshot", default=None, help="arXiv snapshot, used only if --corpus does not exist")
ap.add_argument("--expected", default="data/corpus/EXPECTED.json")
ap.add_argument("--allow-sha-mismatch", action="store_true",
                help="accept a corpus whose SHA-256 differs (e.g. newer snapshot); every pooled document must still exist")
ap.add_argument("--out", default=None, help="output folder (default: folder of the pool file)")
ap.add_argument("--practice-k", type=int, default=6, help="documents per practice query (0 = no practice pages)")
ap.add_argument("--zip", default=None, help="also write the pages + check report into this zip file")
a = ap.parse_args()

pool_obj = load_pool(a.pool)
out = Path(a.out) if a.out else Path(a.pool).parent
annotators = pool_obj["annotators"]
print(f"pool {a.pool}: id {pool_obj['pool_id']}, {pool_obj['counts']['queries']} queries, "
      f"{pool_obj['counts']['pairs']} pairs ({pool_obj['counts']['priority']} phase 1), annotators {annotators}")

# ---------------------------------------------------------------- corpus
corpus = Path(a.corpus)
if not corpus.exists():
    if not a.snapshot:
        sys.exit(f"ERROR: {corpus} not found. Pass --snapshot <arxiv-metadata-oai-snapshot.json> to rebuild it.")
    from irproj.corpus import build_corpus
    exp = json.loads(Path(a.expected).read_text())
    p = exp["build"]
    print(f"rebuilding corpus from {a.snapshot} ({p}) ...")
    build_corpus(a.snapshot, corpus, p["category"], p["year_from"], p["year_to"], p["max_docs"], p["seed"])
sha = sha256_file(corpus)
exp = json.loads(Path(a.expected).read_text()) if Path(a.expected).exists() else {}
ids, docs_list = load_corpus(corpus)
docs = {d["id"]: d for d in docs_list}
sha_ok = sha.startswith(exp.get("sha256_prefix", sha))
print(f"corpus {corpus}: {len(docs)} documents, SHA-256 {sha[:12]}... "
      f"(expected {exp.get('sha256_prefix', '?')}..., {exp.get('n_docs', '?')} documents): {'OK' if sha_ok else 'DIFFERENT'}")
pooled = {x["docid"] for xs in pool_obj["pool"].values() for x in xs}
missing = sorted(pooled - set(docs))
if missing:
    sys.exit(f"ERROR: {len(missing)} pooled documents are not in this corpus, e.g. {missing[:5]}. "
             "Use the corpus the runs were made on (same arXiv snapshot version).")
if not sha_ok and not a.allow_sha_mismatch:
    sys.exit("ERROR: the corpus is not byte-identical to the one the runs were made on (probably a newer "
             "arXiv snapshot). All pooled documents exist, so you may continue with --allow-sha-mismatch; "
             "a few abstracts may then show their newest wording.")

# ---------------------------------------------------------------- pages
topics_all = load_topics(a.topics, include_practice=True)
topics = {t["qid"]: t for t in topics_all}
pool = pool_as_pairs(pool_obj)
seed = pool_obj["seed"]
out.mkdir(parents=True, exist_ok=True)
written, problems, report = [], [], {"pool_id": pool_obj["pool_id"], "corpus_sha256": sha,
                                     "corpus_matches_runs": sha_ok, "pages": {}}
try:
    for i, ann in enumerate(annotators):
        mine = [q for q in pool_obj["assignment"] if ann in pool_obj["assignment"][q]]
        items = build_items(pool, topics, docs, mine, seed=seed * 100 + i)
        path = out / f"judge_{ann}.html"
        write_page(path, ann, pool_obj["round"], pool_obj["pool_id"], items)
        written.append(path)
        probs = check_page(path, pool_obj, topics, ann)
        problems += probs
        report["pages"][path.name] = {"annotator": ann, "queries": len(mine), "items": len(items),
                                      "phase1": sum(it["phase"] == 1 for it in items),
                                      "time_items_with_date": sum(it["show_date"] for it in items),
                                      "problems": probs}

    practice_q = [t["qid"] for t in topics_all if t.get("category") == "practice"]
    if practice_q and a.practice_k > 0:
        from irproj.bm25 import BM25Index
        from irproj.tokenize import get_analyzer
        idx = BM25Index(get_analyzer("id")).build(ids, (doc_text(d) for d in docs_list))
        ppool = {q: [(d, True) for d in idx.search(topics[q]["query"], k=a.practice_k)] for q in practice_q}
        for i, ann in enumerate(annotators):
            items = build_items(ppool, topics, docs, practice_q, seed=seed * 1000 + i)
            path = out / f"practice_{ann}.html"
            write_page(path, ann, "practice", pool_obj["pool_id"], items)
            written.append(path)
            probs = check_page(path, None, topics, ann)
            problems += probs
            report["pages"][path.name] = {"annotator": ann, "items": len(items), "problems": probs}
except JudgingError as e:
    sys.exit(f"ERROR: {e}")

report["ok"] = not problems
(out / "check_report.json").write_text(json.dumps(report, indent=2))
for name, r in report["pages"].items():
    print(f"  {name:22s} items={r['items']:4d}  problems={len(r['problems'])}")
if problems:
    print("\n".join(problems[:30]))
    sys.exit(f"ERROR: {len(problems)} problems found; see {out / 'check_report.json'}")

if a.zip:
    Path(a.zip).parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(a.zip, "w", zipfile.ZIP_DEFLATED) as z:
        for p in written + [out / "check_report.json"]:
            z.write(p, arcname=f"{out.name}/{p.name}")
        howto = ROOT / "judging" / "HOW_TO_JUDGE.md"
        if howto.exists():
            z.write(howto, arcname=f"{out.name}/HOW_TO_JUDGE.md")
    print(f"wrote {a.zip}")
print("all pages checked: every item has query, description, relevance criteria, title and abstract; "
      "dates on time queries; assignments match the frozen pool.")
