"""Depth-k pooling, annotator assignment, blind judging pages and merging of judgments."""
from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from .io import Qrels, Run, rank_docs
from .stats import weighted_kappa

TEMPLATE = Path(__file__).resolve().parents[2] / "judging" / "judge_template.html"


def build_pool(runs: Dict[str, Run], qids: Sequence[str], depth: int = 10, priority_depth: int = 5,
               already_judged: Qrels | None = None) -> Dict[str, List[Tuple[str, bool]]]:
    """qid -> [(docid, is_priority)]. A document is 'priority' if it appears in the top
    `priority_depth` of any run; those are judged first so @5 metrics are complete early.
    Documents already in `already_judged` are skipped (for later incremental rounds)."""
    pool: Dict[str, List[Tuple[str, bool]]] = {}
    for qid in qids:
        prio, rest = set(), set()
        for run in runs.values():
            for rank, (d, _) in enumerate(rank_docs(run.get(qid, {}))[:depth], start=1):
                (prio if rank <= priority_depth else rest).add(d)
        rest -= prio
        done = set((already_judged or {}).get(qid, {}))
        pool[qid] = [(d, True) for d in sorted(prio - done)] + [(d, False) for d in sorted(rest - done)]
    return pool


def assign_queries(qids: Sequence[str], annotators: Sequence[str], per_query: int = 2,
                   seed: int = 7) -> Dict[str, List[str]]:
    """Give every query to `per_query` different annotators, balancing load and spreading
    the annotator pairs evenly (so kappa is estimated across all pairs)."""
    pairs = list(combinations(annotators, per_query))
    rng = random.Random(seed)
    order = list(qids)
    rng.shuffle(order)
    load = defaultdict(int)
    out: Dict[str, List[str]] = {}
    for i, qid in enumerate(order):
        # choose the least-loaded pair, rotating through pairs to break ties
        cand = sorted(range(len(pairs)), key=lambda j: (sum(load[a] for a in pairs[j]),
                                                         (j - i) % len(pairs)))
        pair = pairs[cand[0]]
        for a in pair:
            load[a] += 1
        out[qid] = list(pair)
    return out


def judging_items(pool: Dict[str, List[Tuple[str, bool]]], topics: Dict[str, dict],
                  docs: Dict[str, dict], qids: Iterable[str], seed: int) -> List[dict]:
    """Items for one annotator, blind: no system names, no ranks, random order inside
    each phase. Phase 1 = priority documents of every query, phase 2 = the rest."""
    rng = random.Random(seed)
    items = []
    for phase in (1, 2):
        for qid in qids:
            t = topics[qid]
            ds = [d for d, pr in pool[qid] if pr == (phase == 1)]
            rng.shuffle(ds)
            for d in ds:
                doc = docs[d]
                items.append({
                    "qid": qid, "docid": d, "phase": phase,
                    "query": t["query"], "description": t["description"], "narrative": t["narrative"],
                    "show_date": t.get("category") == "time",
                    "title": doc["title"], "abstract": doc["abstract"], "date": doc.get("date", ""),
                })
    return items


def write_judging_page(out_html: str | Path, annotator: str, items: List[dict],
                       round_name: str = "main", template: str | Path = TEMPLATE) -> None:
    html = Path(template).read_text(encoding="utf-8")
    payload = json.dumps({"annotator": annotator, "round": round_name, "items": items},
                         ensure_ascii=False).replace("</", "<\\/")
    html = html.replace("/*__DATA__*/null", payload)
    Path(out_html).parent.mkdir(parents=True, exist_ok=True)
    Path(out_html).write_text(html, encoding="utf-8")


# --------------------------------------------------------------------------- merging
def load_exports(paths: Iterable[str | Path]) -> Dict[str, Dict[Tuple[str, str], int]]:
    """annotator -> {(qid, docid): grade} from the JSON files exported by the judging page."""
    out: Dict[str, Dict[Tuple[str, str], int]] = defaultdict(dict)
    for p in paths:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        ann = data["annotator"]
        for j in data["judgments"]:
            if j.get("grade") is None:
                continue
            out[ann][(j["qid"], j["docid"])] = int(j["grade"])
    return dict(out)


def agreement(judg: Dict[str, Dict[Tuple[str, str], int]]) -> dict:
    """Weighted kappa over all double-judged pairs and per annotator pair."""
    anns = sorted(judg)
    all1, all2, per_pair = [], [], {}
    for a, b in combinations(anns, 2):
        common = sorted(set(judg[a]) & set(judg[b]))
        if not common:
            continue
        y1 = [judg[a][k] for k in common]
        y2 = [judg[b][k] for k in common]
        all1 += y1
        all2 += y2
        per_pair[f"{a}-{b}"] = {"n": len(common), "kappa_linear": weighted_kappa(y1, y2, weights="linear"),
                                "kappa_quadratic": weighted_kappa(y1, y2, weights="quadratic"),
                                "exact_agreement": sum(x == y for x, y in zip(y1, y2)) / len(common)}
    return {"n": len(all1),
            "kappa_linear": weighted_kappa(all1, all2, weights="linear") if all1 else float("nan"),
            "kappa_quadratic": weighted_kappa(all1, all2, weights="quadratic") if all1 else float("nan"),
            "exact_agreement": (sum(x == y for x, y in zip(all1, all2)) / len(all1)) if all1 else float("nan"),
            "pairs": per_pair}


def merge(judg: Dict[str, Dict[Tuple[str, str], int]], adjudicated: Dict[Tuple[str, str], int] | None = None,
          fallback: str | None = None) -> Tuple[Qrels, List[dict]]:
    """Combine annotators into final qrels. Agreements are taken as is; disagreements need an
    adjudicated grade. `fallback` ('lower' or 'mean') resolves missing adjudications
    automatically and is meant only for preliminary numbers.
    Returns (qrels, unresolved disagreements)."""
    adjudicated = adjudicated or {}
    grades: Dict[Tuple[str, str], List[Tuple[str, int]]] = defaultdict(list)
    for ann, js in judg.items():
        for k, g in js.items():
            grades[k].append((ann, g))
    qrels: Qrels = defaultdict(dict)
    unresolved = []
    for (qid, docid), gs in grades.items():
        vals = [g for _, g in gs]
        if (qid, docid) in adjudicated:
            final = adjudicated[(qid, docid)]
        elif len(set(vals)) == 1:
            final = vals[0]
        else:
            unresolved.append({"qid": qid, "docid": docid, **{f"{a}": g for a, g in gs}})
            if fallback == "lower":
                final = min(vals)
            elif fallback == "mean":
                final = int(round(sum(vals) / len(vals) + 1e-9))
            else:
                continue
        qrels[qid][docid] = final
    return dict(qrels), unresolved


def read_adjudication(path: str | Path) -> Dict[Tuple[str, str], int]:
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("final", "").strip() != "":
                out[(row["qid"], row["docid"])] = int(row["final"])
    return out
