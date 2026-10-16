"""Build the frozen cs.CR test corpus from the Kaggle arXiv metadata snapshot.

Filters (Section 6.1 of the proposal):
  * cs.CR listed as primary or cross-listed category
  * first version (v1) created in [year_from, year_to]
  * withdrawn papers removed
  * LaTeX markup stripped, Unicode NFKC-normalised, whitespace collapsed
  * duplicates by normalised title removed (the earliest arXiv id is kept)
  * random sample of `max_docs` with a fixed seed if the collection is larger
The output JSONL is written sorted by id together with a manifest holding its SHA-256.
"""
from __future__ import annotations

import json
import random
import re
import unicodedata
from collections import Counter
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, Iterator, Optional

from .io import sha256_file, write_jsonl

_WITHDRAWN_RE = re.compile(
    r"(this (paper|article|manuscript|submission|work) (has been|is being|was) withdrawn"
    r"|withdrawn by the (author|authors|submitter|arxiv)|^\s*withdrawn\b|paper (is )?withdrawn)",
    re.I,
)

# LaTeX clean-up rules, applied in order
_LATEX_RULES = [
    (re.compile(r"\\(cite|ref|label|eqref|footnote)\*?\{[^{}]*\}"), " "),
    (re.compile(r"\\(textbf|textit|emph|texttt|textsc|mathrm|mathbf|mathit|mathcal|mathsf|mathbb|text|textrm|url|href|underline|operatorname)\*?\{([^{}]*)\}"), r" \2 "),
    (re.compile(r"\\[\"'`^~=.]\{?([A-Za-z])\}?"), r"\1"),          # accents: \"o -> o
    (re.compile(r"\\[uvHcdbtk]\{([A-Za-z])\}"), r"\1"),             # accents: \v{s} -> s
    (re.compile(r"\\(%|&|_|#|\$)"), r"\1"),
    (re.compile(r"\\\\"), " "),
    (re.compile(r"\\[A-Za-z]+\*?"), " "),                          # remaining commands
    (re.compile(r"[{}$~^]"), " "),
    (re.compile(r"\s+"), " "),
]


def clean_text(s: Optional[str]) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    for pat, rep in _LATEX_RULES:
        s = pat.sub(rep, s)
    return s.strip()


def norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", t.lower())


def first_version_date(rec: dict):
    versions = rec.get("versions") or []
    created = None
    for v in versions:
        if v.get("version") == "v1":
            created = v.get("created")
            break
    if created is None and versions:
        created = versions[0].get("created")
    if not created:
        return None
    try:
        return parsedate_to_datetime(created).date()
    except (TypeError, ValueError):
        return None


def is_withdrawn(rec: dict) -> bool:
    return bool(_WITHDRAWN_RE.search(rec.get("comments") or "")
                or _WITHDRAWN_RE.search((rec.get("abstract") or "")[:300]))


def iter_snapshot(path: str | Path, category: str) -> Iterator[dict]:
    needle = category
    with open(path, encoding="utf-8") as f:
        for line in f:
            if needle not in line:          # cheap pre-filter before JSON parsing
                continue
            yield json.loads(line)


def build_corpus(snapshot: str | Path, out_path: str | Path, category: str = "cs.CR",
                 year_from: int = 2016, year_to: int = 2025, max_docs: int = 50_000,
                 seed: int = 13) -> Dict:
    stats = Counter()
    by_title: Dict[str, dict] = {}
    for rec in iter_snapshot(snapshot, category):
        cats = (rec.get("categories") or "").split()
        if category not in cats:
            continue
        stats["in_category"] += 1
        d = first_version_date(rec)
        if d is None or not (year_from <= d.year <= year_to):
            stats["out_of_date_range"] += 1
            continue
        if is_withdrawn(rec):
            stats["withdrawn"] += 1
            continue
        title, abstract = clean_text(rec.get("title")), clean_text(rec.get("abstract"))
        if not title or not abstract:
            stats["empty"] += 1
            continue
        doc = {
            "id": str(rec["id"]),
            "title": title,
            "abstract": abstract,
            "categories": cats,
            "primary": cats[0],
            "date": d.isoformat(),
            "year": d.year,
        }
        key = norm_title(title)
        prev = by_title.get(key)
        if prev is not None:
            stats["duplicate_title"] += 1
            if (prev["date"], prev["id"]) <= (doc["date"], doc["id"]):
                continue
        by_title[key] = doc

    docs = sorted(by_title.values(), key=lambda x: x["id"])
    stats["after_filtering"] = len(docs)
    if len(docs) > max_docs:
        rng = random.Random(seed)
        docs = sorted(rng.sample(docs, max_docs), key=lambda x: x["id"])
        stats["sampled"] = max_docs
    n = write_jsonl(out_path, docs)
    # the list of arXiv ids is small enough to commit; with the snapshot it rebuilds the corpus
    Path(str(out_path).replace(".jsonl", "") + ".ids.txt").write_text("\n".join(d["id"] for d in docs) + "\n")
    manifest = {
        "source": str(snapshot),
        "category": category,
        "years": [year_from, year_to],
        "max_docs": max_docs,
        "seed": seed,
        "n_docs": n,
        "n_primary_cr": sum(d["primary"] == category for d in docs),
        "year_histogram": dict(sorted(Counter(d["year"] for d in docs).items())),
        "filter_counts": dict(stats),
        "sha256": sha256_file(out_path),
    }
    Path(str(out_path) + ".manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest
