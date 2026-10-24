"""RQ5b: tokenisation ablation for BM25 on the frozen cs.CR qrels (EXPLORATORY).

Only the analyzer changes; k1 = 1.2 and b = 0.75 throughout (the main setting). Variants
(src/irproj/tokenize.py, unchanged):
  id            main: identifier-aware + Lucene stopwords + Porter
  plain         Lucene-like: no identifier handling (no protocol-version normalisation, identifiers
                split into pieces, tokens with digits stemmed); same stopwords and stemmer
  id-nostem     as id, without stemming
  plain-nostem  as plain, without stemming (completes a 2x2: identifier handling x stemming)
  id-nostop     as id, without stopword removal (keeps "not", "no", ...)
Each variant is compared with `id` (paired randomisation test, Holm over the 4 comparisons).
Only the `id` run was in the judging pool, so Hole@10 and condensed nDCG@10 are reported; the
pool favours `id`, so "worse than id" is weaker evidence than "better than id".

    python scripts/tokenizer_ablation.py --corpus data/corpus/cscr.jsonl
Outputs: deliverables/rq5/tokenisation/ (CSV, JSON, metadata, top-100 runs), report/tables/rq5_tok.tex
"""
import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np

from irproj import report as R
from irproj import rq5
from irproj.bm25 import BM25Index
from irproj.io import doc_text, load_corpus, load_topics, require_qrels, write_run
from irproj.metrics import per_query
from irproj.stats import bootstrap_ci, holm_bonferroni, paired_randomization_test
from irproj.tokenize import ANALYZERS

ROOT = rq5.ROOT
ap = argparse.ArgumentParser()
ap.add_argument("--corpus", required=True)
ap.add_argument("--topics", default=str(ROOT / "data/queries/topics.jsonl"))
ap.add_argument("--qrels", default=str(ROOT / "data/qrels/qrels.txt"))
ap.add_argument("--expected-qrels-sha", default=None, help="default: data/qrels/qrels.sha256")
ap.add_argument("--expected-corpus", default=str(ROOT / "data/corpus/EXPECTED.json"))
ap.add_argument("--reference-run", default=str(ROOT / "runs/bm25.run"))
ap.add_argument("--allow-corpus-mismatch", action="store_true")
ap.add_argument("--variants", nargs="+", default=["id", "plain", "id-nostem", "plain-nostem", "id-nostop"])
ap.add_argument("--depth", type=int, default=1000)
ap.add_argument("--save-depth", type=int, default=100, help="depth of the run files written")
ap.add_argument("--out", default=str(ROOT / "deliverables/rq5/tokenisation"))
ap.add_argument("--tables", default=str(ROOT / "report/tables"))
a = ap.parse_args()

MAIN = "id"
if a.variants[0] != MAIN:
    raise SystemExit("the first variant must be the main analyzer 'id'")
OUT = rq5.guard_output(a.out)
TAB = rq5.guard_output(Path(a.tables) / "rq5_tok.tex")
K1, B = rq5.DEFAULT
METRICS = ("ndcg@10", "ndcgc@10", "hole@10", "mrr@10", "p@5")
CATS = ["identifier", "homonym", "negation", "time", "paraphrase"]
NAMES = {"id": "Identifier-aware + Porter (main)", "plain": "Lucene-like + Porter",
         "id-nostem": "Identifier-aware, no stemming", "plain-nostem": "Lucene-like, no stemming",
         "id-nostop": "Identifier-aware, no stopword removal"}

qrels_sha = rq5.verify_qrels(a.qrels, a.expected_qrels_sha or rq5.frozen_qrels_sha())
qrels = require_qrels(a.qrels)
topics = [t for t in load_topics(a.topics) if t["qid"] in qrels]
qids = [t["qid"] for t in topics]
cat = {t["qid"]: t["category"] for t in topics}
queries = {t["qid"]: t["query"] for t in topics}
CATS = [c for c in CATS if any(cat[q] == c for q in qids)]     # categories that have judged queries
ids, docs = load_corpus(a.corpus)
corpus_check = rq5.verify_corpus(a.corpus, len(ids), a.expected_corpus)
texts = [doc_text(d) for d in docs]

res, pq_all, repro = {}, {}, {"ok": None}
for v in a.variants:
    t0 = time.perf_counter()
    an = ANALYZERS[v]
    idx = BM25Index(an).build(ids, texts)
    t_index = time.perf_counter() - t0
    run, _ = idx.batch_search(queries, k=a.depth, k1=K1, b=B)
    if v == MAIN:
        repro = rq5.reproduction_check(run, a.reference_run) if a.reference_run else {"ok": None}
        print("reproduction of the committed default run:",
              json.dumps({k: x for k, x in repro.items() if k != "mismatched_queries"}))
        comparable = bool(corpus_check["match"] is not False and repro["ok"] is not False)
        if not comparable and not a.allow_corpus_mismatch:
            raise SystemExit("ERROR: the corpus is not the one behind the frozen runs. Attach the arXiv "
                             "dataset version used on 19 Oct 2026, or use --allow-corpus-mismatch.")
    write_run(OUT / "runs" / f"bm25-{v}.run", run, f"bm25-{v}", a.save_depth)
    pq = per_query(run, qrels, METRICS, qids=qids)
    pq_all[v] = pq
    res[v] = {"description": NAMES.get(v, v), "mode": an.mode, "stem": an.stem, "stopwords": an.stopwords,
              "vocab": len(idx.vocab), "avgdl": idx.avgdl, "index_mb": round(idx.index_bytes() / 2**20, 2),
              "index_seconds": round(t_index, 2),
              **{m: float(np.mean(list(pq[m].values()))) for m in METRICS},
              **{f"ndcg@10_{c}": float(np.mean([pq["ndcg@10"][q] for q in qids if cat[q] == c])) for c in CATS}}
    print(v, json.dumps({k: res[v][k] for k in ("vocab", "ndcg@10", "ndcgc@10", "hole@10")}))
status = "EXPLORATORY" if comparable else "NOT COMPARABLE (corpus differs from the frozen runs)"

for metric, suffix in (("ndcg@10", ""), ("ndcgc@10", "_condensed")):
    raw = {}
    for v in a.variants[1:]:
        x = np.array([pq_all[v][metric][q] for q in qids])
        y = np.array([pq_all[MAIN][metric][q] for q in qids])
        d, p = paired_randomization_test(x, y)
        _, lo, hi = bootstrap_ci(x - y)
        res[v].update({f"diff_vs_id{suffix}": d, f"diff_ci95_vs_id{suffix}": [lo, hi], f"p_vs_id{suffix}": p,
                       f"wins_ties_losses_vs_id{suffix}": [int(np.sum(x - y > 1e-12)), int(np.sum(np.abs(x - y) <= 1e-12)),
                                                          int(np.sum(x - y < -1e-12))]})
        raw[v] = p
    for v, (ph, sig) in holm_bonferroni(raw).items():
        res[v][f"p_holm_vs_id{suffix}"], res[v][f"significant{suffix}"] = ph, bool(sig)

OUT.mkdir(parents=True, exist_ok=True)
out = {"status": status,
       "design": {"k1": K1, "b": B, "variants": a.variants, "reference": MAIN, "primary_metric": "ndcg@10",
                  "test": "paired randomisation (100k), Holm over the comparisons with id", "depth": a.depth},
       "checks": {"qrels_sha256": qrels_sha, "corpus": corpus_check, "reproduction": repro},
       "variants": res}
(OUT / "tokenizer_ablation.json").write_text(json.dumps(out, indent=2))
cols = ["description", "vocab", "avgdl", "index_mb"] + list(METRICS) + [f"ndcg@10_{c}" for c in CATS] + \
       ["diff_vs_id", "p_vs_id", "p_holm_vs_id", "significant", "diff_vs_id_condensed", "p_holm_vs_id_condensed"]
with open(OUT / "tokenizer_ablation.csv", "w", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["variant"] + cols)
    for v, r in res.items():
        w.writerow([v] + [f"{r[c]:.6f}" if isinstance(r.get(c), float) else r.get(c, "") for c in cols])
with open(OUT / "tokenizer_ablation_per_query.csv", "w", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["variant", "qid", "category"] + list(METRICS))
    for v in a.variants:
        for q in qids:
            w.writerow([v, q, cat[q]] + [f"{pq_all[v][m][q]:.6f}" for m in METRICS])
(OUT / "metadata.json").write_text(json.dumps(rq5.metadata(
    vars(a), {"corpus": a.corpus, "topics": a.topics, "qrels": a.qrels},
    {"script": "scripts/tokenizer_ablation.py", "status": status}), indent=2))

f3 = lambda v: R.fmt(v).replace("-", "$-$")
rows = []
for v, r in res.items():
    if v == MAIN:
        dtxt, ptxt = "--", "--"
    else:
        dtxt = f"{r['diff_vs_id']:+.3f}".replace("-", "$-$").replace("+", "$+$")
        ptxt = R.fmt(r["p_holm_vs_id"], 3)
    rows.append([NAMES.get(v, v), f"{r['vocab']:,}", f3(r["ndcg@10"]), dtxt, ptxt, f3(r["ndcgc@10"]),
                 R.fmt(100 * r["hole@10"], 1) + r"\%", f3(r["ndcg@10_identifier"])])
cap = (f"{'' if comparable else 'NOT COMPARABLE: corpus differs. '}Tokenisation ablation for BM25 "
       "($k_1$=1.2, $b$=0.75; exploratory). $\\Delta$ and $p_{\\text{Holm}}$: nDCG@10 against the main analyzer "
       "(paired randomisation, Holm over 4 comparisons). Only the main run was in the judging pool, which "
       "favours it; condensed nDCG@10 removes unjudged documents.")
R.write(TAB, R.latex_table(rows, ["Analyzer", "Vocab.", "nDCG@10", "$\\Delta$", "$p_{\\text{Holm}}$",
                                  "nDCG@10 (cond.)", "Hole@10", "nDCG@10 (ident.)"], "lccccccc", cap, "tab:rq5tok"))
print("wrote", OUT, TAB)
