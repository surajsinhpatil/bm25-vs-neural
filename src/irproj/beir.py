"""Loading a BEIR-format dataset (used only to validate our code on SciFact)."""
from __future__ import annotations

import csv
import gzip
import io
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, Tuple

from .io import Qrels

UKP_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/{name}.zip"


def download(name: str, root: str | Path) -> Path:
    """Download a BEIR dataset into root/name (BEIR zip, falling back to the HF hub copy)."""
    root = Path(root)
    target = root / name
    if (target / "corpus.jsonl").exists():
        return target
    root.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(UKP_URL.format(name=name), timeout=120) as r:
            data = r.read()
        zipfile.ZipFile(io.BytesIO(data)).extractall(root)
        return target
    except Exception as e:  # pragma: no cover - network dependent
        print(f"BEIR zip download failed ({e}); trying the Hugging Face hub")
    from huggingface_hub import hf_hub_download
    target.mkdir(parents=True, exist_ok=True)
    for fn in ("corpus.jsonl.gz", "queries.jsonl.gz"):
        p = hf_hub_download(f"BeIR/{name}", fn, repo_type="dataset")
        with gzip.open(p, "rb") as src, open(target / fn[:-3], "wb") as dst:
            shutil.copyfileobj(src, dst)
    (target / "qrels").mkdir(exist_ok=True)
    p = hf_hub_download(f"BeIR/{name}-qrels", "test.tsv", repo_type="dataset")
    shutil.copy(p, target / "qrels" / "test.tsv")
    return target


def load(path: str | Path, split: str = "test") -> Tuple[Dict[str, dict], Dict[str, str], Qrels]:
    """Returns (docs id -> {title, abstract}, queries id -> text, qrels)."""
    path = Path(path)
    docs = {}
    with open(path / "corpus.jsonl", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            docs[str(d["_id"])] = {"id": str(d["_id"]), "title": d.get("title", "") or "",
                                   "abstract": d.get("text", "") or ""}
    queries = {}
    with open(path / "queries.jsonl", encoding="utf-8") as f:
        for line in f:
            q = json.loads(line)
            queries[str(q["_id"])] = q["text"]
    qrels: Qrels = {}
    with open(path / "qrels" / f"{split}.tsv", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader)
        for qid, did, score in reader:
            qrels.setdefault(qid, {})[did] = int(score)
    queries = {q: t for q, t in queries.items() if q in qrels}
    return docs, queries, qrels


def remove_identical(run, ):
    """BEIR convention: a document with the same id as the query is not counted."""
    return {q: {d: s for d, s in r.items() if d != q} for q, r in run.items()}
