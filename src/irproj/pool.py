"""Depth-k pooling, annotator assignment and merging of judgments (pages: see judging.py)."""
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


# --------------------------------------------------------------------------- merging
def load_exports(paths: Iterable[str | Path]) -> Dict[str, Dict[Tuple[str, str], int]]:
    """annotator -> {(qid, docid): grade} from the JSON files exported by the judging page."""
    out: Dict[str, Dict[Tuple[str, str], int]] = defaultdict(dict)
    for p in paths:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        ann = data["annotator"]
        for j in data["judgments"]:
            g = j.get("grade")
            if g is None:
                continue
            if g not in (0, 1, 2, 3):
                raise ValueError(f"{p}: invalid grade {g!r} for query {j.get('qid')}, document {j.get('docid')}")
            key = (str(j["qid"]), str(j["docid"]))
            if key in out[ann] and out[ann][key] != g:
                raise ValueError(f"{p}: {key} appears twice with different grades")
            out[ann][key] = int(g)
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
          fallback: str | None = None, provenance: List[dict] | None = None) -> Tuple[Qrels, List[dict]]:
    """Combine annotators into final qrels. Agreements are taken as is; disagreements need an
    adjudicated grade. `fallback` ('lower', 'upper' or 'mean') resolves missing adjudications
    automatically and is meant ONLY for preliminary / sensitivity numbers, never for final qrels.
    An adjudicated grade is accepted only for a pair the annotators disagreed on.
    If `provenance` is a list, one row per pair is appended with the original grades, the final
    grade and its source ('agreed', 'adjudicated', 'fallback-<rule>').
    Returns (qrels, unresolved disagreements)."""
    adjudicated = adjudicated or {}
    grades: Dict[Tuple[str, str], List[Tuple[str, int]]] = defaultdict(list)
    for ann, js in judg.items():
        for k, g in js.items():
            grades[k].append((ann, g))
    bad = [k for k in adjudicated if k not in grades or len({g for _, g in grades[k]}) == 1]
    if bad:
        raise ValueError(f"{len(bad)} adjudicated pairs are not disagreements (or were never judged), e.g. {bad[:3]}")
    for k, g in adjudicated.items():
        if g not in (0, 1, 2, 3):
            raise ValueError(f"adjudicated grade {g!r} for {k} is not in 0-3")
    if fallback not in (None, "lower", "upper", "mean"):
        raise ValueError(f"unknown fallback {fallback!r}")
    qrels: Qrels = defaultdict(dict)
    unresolved = []
    for (qid, docid), gs in sorted(grades.items()):
        vals = [g for _, g in gs]
        if len(set(vals)) == 1:
            final, source = vals[0], "agreed"
        elif (qid, docid) in adjudicated:
            final, source = adjudicated[(qid, docid)], "adjudicated"
        else:
            unresolved.append({"qid": qid, "docid": docid, **{f"{a}": g for a, g in gs}})
            if fallback == "lower":
                final = min(vals)
            elif fallback == "upper":
                final = max(vals)
            elif fallback == "mean":
                final = int(round(sum(vals) / len(vals) + 1e-9))
            else:
                continue
            source = f"fallback-{fallback}"
        qrels[qid][docid] = final
        if provenance is not None:
            provenance.append({"qid": qid, "docid": docid, "grades": dict(gs), "final": final, "source": source})
    return dict(qrels), unresolved


def read_adjudication(path: str | Path) -> Dict[Tuple[str, str], int]:
    """Read the `final` column of an adjudication sheet (blank = not adjudicated yet)."""
    out = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            v = (row.get("final") or "").strip()
            if v == "":
                continue
            try:
                g = int(float(v))
            except ValueError:
                raise ValueError(f"{path}, line {i}: final grade {v!r} is not a number")
            if g not in (0, 1, 2, 3) or float(v) != g:
                raise ValueError(f"{path}, line {i}: final grade {v!r} must be 0, 1, 2 or 3")
            key = (row["qid"].strip(), row["docid"].strip())
            if key in out and out[key] != g:
                raise ValueError(f"{path}: two different final grades for {key}")
            out[key] = g
    return out
