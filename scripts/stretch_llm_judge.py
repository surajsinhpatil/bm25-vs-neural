"""S3: LLM relevance judgments on the same pool [Thomas et al. 2024], compared with the human
qrels: weighted kappa on the grades and Kendall's tau between the system rankings.

Uses any OpenAI-compatible chat endpoint (OPENAI_BASE_URL, OPENAI_API_KEY). Answers are
cached in --cache so the run can be resumed and costs nothing the second time.

    python scripts/stretch_llm_judge.py --pool judging/round1/pool_internal.json \
        --corpus data/corpus/cscr.jsonl --topics data/queries/topics.jsonl --qrels data/qrels/qrels.txt \
        --runs runs/bm25.run runs/e5.run runs/specter2.run runs/bm25+e5.run runs/bm25+specter2.run \
        --model gpt-4o-mini --out results
"""
import argparse
import json
import os
import re
import time
import urllib.request
from pathlib import Path

import numpy as np

from irproj.io import load_corpus, load_topics, read_qrels, require_qrels, read_run, write_qrels
from irproj.metrics import per_query
from irproj.stats import kendall_tau, weighted_kappa

PROMPT = """You are a search quality rater judging scientific abstracts for a researcher.

Query: {query}
Description: {description}
What counts as relevant: {narrative}
{date_line}
Paper title: {title}
Paper abstract: {abstract}

Grade the paper on this scale:
3 = highly relevant: directly and substantially answers the query
2 = relevant: answers the query
1 = on the topic but does not answer the query, or violates a condition in it (for example an exclusion or a date limit)
0 = not relevant

First think about the query intent and each condition, then end your answer with one line: "Grade: <0-3>"."""


def ask(prompt, model):
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    body = json.dumps({"model": model, "temperature": 0, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(base + "/chat/completions", data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + os.environ.get("OPENAI_API_KEY", "")})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())["choices"][0]["message"]["content"]
        except Exception as e:  # rate limits etc.
            time.sleep(2 ** attempt)
            last = e
    raise last


def parse_grade(text):
    m = re.findall(r"grade\s*[:=]\s*([0-3])", text, re.I)
    return int(m[-1]) if m else None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--topics", required=True)
    ap.add_argument("--qrels", required=True)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--cache", default="results/llm_judgments.jsonl")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()

    pool = json.loads(Path(a.pool).read_text())
    _, docs = load_corpus(a.corpus)
    docs = {d["id"]: d for d in docs}
    topics = {t["qid"]: t for t in load_topics(a.topics)}
    human = require_qrels(a.qrels)
    cache = {}
    if Path(a.cache).exists():
        for line in open(a.cache):
            r = json.loads(line)
            cache[(r["qid"], r["docid"])] = r
    with open(a.cache, "a") as f:
        for qid, ds in pool.items():
            if qid not in topics:
                continue
            t = topics[qid]
            for d in ds:
                if (qid, d) in cache:
                    continue
                doc = docs[d]
                p = PROMPT.format(query=t["query"], description=t["description"], narrative=t["narrative"],
                                  date_line=f"Paper first published: {doc.get('date')}" if t["category"] == "time" else "",
                                  title=doc["title"], abstract=doc["abstract"])
                ans = ask(p, a.model)
                r = {"qid": qid, "docid": d, "grade": parse_grade(ans), "answer": ans, "model": a.model}
                cache[(qid, d)] = r
                f.write(json.dumps(r) + "\n")
                f.flush()

    llm = {}
    for (q, d), r in cache.items():
        if r["grade"] is not None:
            llm.setdefault(q, {})[d] = r["grade"]
    write_qrels(Path(a.out) / "qrels.llm.txt", llm)
    common = [(q, d) for q in human for d in human[q] if d in llm.get(q, {})]
    y1 = [human[q][d] for q, d in common]
    y2 = [llm[q][d] for q, d in common]
    qids = sorted(q for q in human if q in topics)
    means_h, means_l = {}, {}
    for p in a.runs:
        run = read_run(p)
        s = Path(p).stem
        means_h[s] = float(np.mean(list(per_query(run, human, ("ndcg@10",), qids=qids)["ndcg@10"].values())))
        means_l[s] = float(np.mean(list(per_query(run, llm, ("ndcg@10",), qids=qids)["ndcg@10"].values())))
    res = {"model": a.model, "n_pairs": len(common),
           "kappa_linear": weighted_kappa(y1, y2, weights="linear"),
           "kappa_quadratic": weighted_kappa(y1, y2, weights="quadratic"),
           "exact_agreement": float(np.mean([x == y for x, y in zip(y1, y2)])),
           "ndcg@10_human": means_h, "ndcg@10_llm": means_l,
           "kendall_tau_system_ranking": kendall_tau(means_h, means_l)}
    Path(a.out, "llm_judge.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
