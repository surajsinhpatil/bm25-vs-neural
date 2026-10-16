"""S2: handle time constraints by extracting a date range from the query and filtering on the
paper's first-version date. Two extractors:

  * rules (default): regular expressions for "after 2018", "since 2020", "before 2019",
    "between 2017 and 2020", "in 2021", "published after its 2018 standardisation", ...
  * llm: any OpenAI-compatible chat endpoint (set OPENAI_BASE_URL, OPENAI_API_KEY, --llm-model),
    e.g. a free Groq/Gemini key or a local Ollama server.

Only queries where a range is found are filtered; others are copied unchanged. The filter is
applied to an existing run (post-filtering), so it can only remove documents, never add any.

    python scripts/stretch_time_filter.py --run runs/bm25+e5.run --corpus data/corpus/cscr.jsonl \
        --topics data/queries/topics.jsonl --out runs/bm25+e5+time.run
"""
import argparse
import json
import os
import re
from pathlib import Path

from irproj.io import load_corpus, load_topics, rank_docs, read_run, write_run

YEAR = r"(19|20)\d{2}"
RULES = [
    (re.compile(rf"\bbetween\s+({YEAR})\s+and\s+({YEAR})"), lambda m: (int(m.group(1)), int(m.group(3)))),
    (re.compile(rf"\bfrom\s+({YEAR})\s+(?:to|until|through)\s+({YEAR})"), lambda m: (int(m.group(1)), int(m.group(3)))),
    (re.compile(rf"\b(?:after|since|post)\b[^.]*?\b({YEAR})"), lambda m: (int(m.group(1)) + (0 if "since" in m.group(0) else 1), None)),
    (re.compile(rf"\b(?:before|prior to|pre)\b[^.]*?\b({YEAR})"), lambda m: (None, int(m.group(1)) - 1)),
    (re.compile(rf"\b(?:in|during|published in)\s+({YEAR})\b"), lambda m: (int(m.group(1)), int(m.group(1)))),
    (re.compile(r"\b(?:last|past)\s+(\d+)\s+years"), lambda m: (2025 - int(m.group(1)) + 1, 2025)),
]


def extract_rules(text: str):
    t = text.lower()
    for pat, fn in RULES:
        m = pat.search(t)
        if m:
            return fn(m)
    return None


def extract_llm(text: str, model: str):
    import urllib.request
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    prompt = ("Extract the publication-year range required by this search query. Answer with JSON only: "
              '{"from": <year or null>, "to": <year or null>}. If the query has no time condition answer '
              '{"from": null, "to": null}. "After 2018" means from 2019. Query: ' + text)
    body = json.dumps({"model": model, "temperature": 0,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(base + "/chat/completions", data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + os.environ.get("OPENAI_API_KEY", "")})
    with urllib.request.urlopen(req, timeout=60) as r:
        content = json.loads(r.read())["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", content, re.S)
    d = json.loads(m.group(0)) if m else {}
    if d.get("from") is None and d.get("to") is None:
        return None
    return d.get("from"), d.get("to")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--topics", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--extractor", choices=["rules", "llm"], default="rules")
    ap.add_argument("--llm-model", default="gpt-4o-mini")
    ap.add_argument("--only-category", default="time", help="apply only to this category ('' = all)")
    a = ap.parse_args()

    _, docs = load_corpus(a.corpus)
    year = {d["id"]: int(d["year"]) for d in docs}
    topics = load_topics(a.topics)
    run = read_run(a.run)
    ranges, out = {}, {}
    for t in topics:
        q = t["qid"]
        rng = None
        if not a.only_category or t["category"] == a.only_category:
            rng = extract_rules(t["query"]) if a.extractor == "rules" else extract_llm(t["query"], a.llm_model)
        ranges[q] = rng
        if rng is None:
            out[q] = run.get(q, {})
            continue
        lo, hi = rng
        out[q] = {d: s for d, s in rank_docs(run.get(q, {})) if (lo is None or year.get(d, 0) >= lo)
                  and (hi is None or year.get(d, 9999) <= hi)}
    write_run(a.out, out, Path(a.out).stem)
    Path(a.out + ".ranges.json").write_text(json.dumps(ranges, indent=2))
    print(f"date ranges found for {sum(r is not None for r in ranges.values())} queries -> {a.out}")
