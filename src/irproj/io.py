"""Reading and writing the file formats used throughout the project.

Everything on disk is in a standard format so it can be checked with other tools:
  * corpus / topics: JSON Lines
  * runs: TREC run format   (qid Q0 docid rank score tag)
  * qrels: TREC qrels format (qid 0 docid grade)
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Tuple

Run = Dict[str, Dict[str, float]]      # qid -> {docid: score}
Qrels = Dict[str, Dict[str, int]]      # qid -> {docid: grade}


# --------------------------------------------------------------------------- jsonl
def read_jsonl(path: str | Path) -> Iterator[dict]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: str | Path, rows: Iterable[dict]) -> int:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
            n += 1
    return n


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_corpus(path: str | Path) -> Tuple[List[str], List[dict]]:
    """Return (doc_ids, docs) in file order. Each doc has at least id/title/abstract."""
    docs = list(read_jsonl(path))
    return [d["id"] for d in docs], docs


def doc_text(doc: dict, sep: str = " ") -> str:
    """Title + abstract, the unit indexed by every system."""
    return (doc.get("title") or "").strip() + sep + (doc.get("abstract") or "").strip()


# --------------------------------------------------------------------------- topics
def load_topics(path: str | Path, include_practice: bool = False) -> List[dict]:
    topics = [t for t in read_jsonl(path)]
    if not include_practice:
        topics = [t for t in topics if t.get("category") != "practice"]
    return topics


def write_trec_topics(path: str | Path, topics: List[dict]) -> None:
    """Classic TREC topic format (<top><num><title><desc><narr>)."""
    with open(path, "w", encoding="utf-8") as f:
        for t in topics:
            f.write("<top>\n")
            f.write(f"<num> Number: {t['qid']}\n")
            f.write(f"<title> {t['query']}\n\n")
            f.write(f"<desc> Description:\n{t['description']}\n\n")
            f.write(f"<narr> Narrative:\n{t['narrative']}\n\n")
            f.write("</top>\n\n")


# --------------------------------------------------------------------------- runs
def write_run(path: str | Path, run: Run, tag: str, depth: int = 1000) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for qid in sorted(run, key=_qid_key):
            ranked = rank_docs(run[qid])[:depth]
            for rank, (docid, score) in enumerate(ranked, start=1):
                f.write(f"{qid} Q0 {docid} {rank} {score:.6f} {tag}\n")


def read_run(path: str | Path) -> Run:
    run: Run = defaultdict(dict)
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 6:
                continue
            qid, _, docid, _, score = parts[:5]
            run[qid][docid] = float(score)
    return dict(run)


def rank_docs(scores: Dict[str, float]) -> List[Tuple[str, float]]:
    """Order documents the way trec_eval / pytrec_eval do:
    by score descending, ties broken by docid in *descending* lexicographic order."""
    return sorted(scores.items(), key=lambda x: (x[1], x[0]), reverse=True)


# --------------------------------------------------------------------------- qrels
def write_qrels(path: str | Path, qrels: Qrels) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for qid in sorted(qrels, key=_qid_key):
            for docid in sorted(qrels[qid]):
                f.write(f"{qid} 0 {docid} {int(qrels[qid][docid])}\n")


def read_qrels(path: str | Path) -> Qrels:
    qrels: Qrels = defaultdict(dict)
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 4:
                continue
            qid, _, docid, grade = parts[:4]
            qrels[qid][docid] = int(grade)
    return dict(qrels)


def _qid_key(q: str):
    return (len(q), q)
