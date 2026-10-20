"""Blind relevance-judging pages: frozen pool files, page rendering and page checking.

Design rules (they fix the blank-page bug of the first version):
  * Every query field and every paper field is written into the HTML as plain text when the
    page is generated. JavaScript is used only to show one item at a time, record grades,
    save them in the browser and export them. A viewer that does not run scripts (file
    previews, editors, Kaggle/GitHub viewers) still shows all content, plus a warning that
    grading needs a browser.
  * Items are built only from the frozen pool, the topics and the corpus. Nothing is taken
    from qrels or from other pages, and pages never contain grades.
  * Generation refuses to write a page if any item would have an empty query, description,
    narrative, title or abstract, or a time query without a date, and every page is checked
    again after it is written (check_page).
"""
from __future__ import annotations

import hashlib
import html
import json
import random
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from .io import sha256_file

TEMPLATE = Path(__file__).resolve().parents[2] / "judging" / "judge_template.html"
REQUIRED_TEXT = ("query", "desc", "narr", "title", "abstract")


class JudgingError(ValueError):
    pass


# --------------------------------------------------------------------------- frozen pool
def freeze_pool(path: str | Path, pool: Dict[str, List[Tuple[str, bool]]], assignment: Dict[str, List[str]],
                annotators: Sequence[str], run_paths: Sequence[str | Path], round_name: str,
                depth: int, priority_depth: int, seed: int) -> dict:
    """Write the pool + assignment that every judging page of a round is generated from."""
    qids = list(assignment)
    obj = {
        "round": round_name,
        "depth": depth, "priority_depth": priority_depth, "seed": seed,
        "annotators": list(annotators),
        "runs": {Path(p).stem: sha256_file(p) for p in run_paths},
        "counts": {"queries": len(qids),
                   "pairs": sum(len(pool[q]) for q in qids),
                   "priority": sum(sum(1 for _, pr in pool[q] if pr) for q in qids)},
        "assignment": {q: list(assignment[q]) for q in qids},
        "pool": {q: [{"docid": d, "priority": bool(pr)} for d, pr in pool[q]] for q in qids},
    }
    body = json.dumps({k: obj[k] for k in ("round", "assignment", "pool")}, sort_keys=True)
    obj["pool_id"] = hashlib.sha256(body.encode()).hexdigest()[:16]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1), encoding="utf-8")
    return obj


def load_pool(path: str | Path) -> dict:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    body = json.dumps({k: obj[k] for k in ("round", "assignment", "pool")}, sort_keys=True)
    if hashlib.sha256(body.encode()).hexdigest()[:16] != obj.get("pool_id"):
        raise JudgingError(f"{path}: pool_id does not match its content (file was edited?)")
    return obj


def pool_as_pairs(pool_obj: dict) -> Dict[str, List[Tuple[str, bool]]]:
    return {q: [(x["docid"], x["priority"]) for x in xs] for q, xs in pool_obj["pool"].items()}


def expected_pairs(pool_obj: dict, annotator: str) -> List[Tuple[str, str]]:
    return [(q, x["docid"]) for q, xs in pool_obj["pool"].items()
            if annotator in pool_obj["assignment"][q] for x in xs]


# --------------------------------------------------------------------------- items
def _clean(s) -> str:
    return " ".join(str(s or "").split())


def build_items(pool: Dict[str, List[Tuple[str, bool]]], topics: Dict[str, dict], docs: Dict[str, dict],
                qids: Iterable[str], seed: int) -> List[dict]:
    """Items for one annotator, blind: no system names, no ranks, random order inside each
    phase (phase 1 = documents in any run's top-5, phase 2 = the rest).
    Raises JudgingError if any text needed by the annotator is missing."""
    rng = random.Random(seed)
    items, problems = [], []
    qids = list(qids)
    for phase in (1, 2):
        for qid in qids:
            t = topics.get(qid)
            if t is None:
                problems.append(f"query {qid} is not in the topics file")
                continue
            ds = [d for d, pr in pool[qid] if pr == (phase == 1)]
            rng.shuffle(ds)
            for d in ds:
                doc = docs.get(d)
                if doc is None:
                    problems.append(f"query {qid}: document {d} is not in the corpus")
                    continue
                it = {"qid": qid, "docid": d, "phase": phase, "category": t.get("category", ""),
                      "query": _clean(t.get("query")), "desc": _clean(t.get("description")),
                      "narr": _clean(t.get("narrative")),
                      "title": _clean(doc.get("title")), "abstract": _clean(doc.get("abstract")),
                      "show_date": t.get("category") == "time", "date": _clean(doc.get("date"))}
                for f in REQUIRED_TEXT:
                    if not it[f]:
                        problems.append(f"query {qid}, document {d}: empty {f}")
                if it["show_date"] and not it["date"]:
                    problems.append(f"query {qid}, document {d}: time query but the paper has no date")
                items.append(it)
    if problems:
        raise JudgingError(f"{len(problems)} problem(s), no page written:\n  " + "\n  ".join(problems[:20]))
    return items


# --------------------------------------------------------------------------- rendering
def _e(s) -> str:
    return html.escape(str(s), quote=True)


def render_item(i: int, n: int, it: dict) -> str:
    date = (f'<p class="doc-date"><b>First version (arXiv v1):</b> <span class="date">{_e(it["date"])}</span></p>'
            if it["show_date"] else "")
    phase = "Phase 1 (judge first)" if it["phase"] == 1 else "Phase 2"
    return f"""<article class="item" id="item-{i}" data-i="{i}" data-qid="{_e(it['qid'])}" data-docid="{_e(it['docid'])}" data-phase="{it['phase']}">
<div class="item-meta"><span class="phase">{phase}</span> Item {i + 1} of {n} &middot; query {_e(it['qid'])}</div>
<section class="qpanel">
<h3>Query</h3><p class="query">{_e(it['query'])}</p>
<h3>Description</h3><p class="desc">{_e(it['desc'])}</p>
<h3>What counts as relevant</h3><p class="narr">{_e(it['narr'])}</p>
</section>
<section class="dpanel">
<h2 class="title">{_e(it['title'])}</h2>
{date}
<p class="abstract">{_e(it['abstract'])}</p>
<div class="grades js-only" role="group" aria-label="Grade">
<button type="button" data-g="0"><b>0</b> Not relevant</button>
<button type="button" data-g="1"><b>1</b> On topic, but does not answer the query or breaks a condition</button>
<button type="button" data-g="2"><b>2</b> Relevant</button>
<button type="button" data-g="3"><b>3</b> Highly relevant</button>
</div>
<p class="saved-grade js-only" aria-live="polite"></p>
</section>
</article>"""


def render_page(annotator: str, round_name: str, pool_id: str, items: List[dict],
                template: str | Path = TEMPLATE) -> str:
    tpl = Path(template).read_text(encoding="utf-8")
    body = "\n".join(render_item(i, len(items), it) for i, it in enumerate(items))
    if not items:
        body = '<p class="empty">This page has no items.</p>'
    repl = {"{{ANNOTATOR}}": _e(annotator), "{{ROUND}}": _e(round_name), "{{POOL_ID}}": _e(pool_id),
            "{{N_ITEMS}}": str(len(items)), "{{ITEMS}}": body}
    for k, v in repl.items():
        if k not in tpl:
            raise JudgingError(f"template is missing {k}")
        tpl = tpl.replace(k, v)
    return tpl


def write_page(path: str | Path, annotator: str, round_name: str, pool_id: str, items: List[dict]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(render_page(annotator, round_name, pool_id, items), encoding="utf-8")


# --------------------------------------------------------------------------- checking
class _PageParser(HTMLParser):
    """Collects the meta attributes and, for every <article class="item">, the text of its
    elements with class query / desc / narr / title / abstract / date."""

    FIELDS = set(REQUIRED_TEXT) | {"date"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict = {}
        self.items: List[dict] = []
        self._cur: dict | None = None
        self._field: str | None = None
        self._depth = 0
        self._fdepth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = set((a.get("class") or "").split())
        if a.get("id") == "page-meta":
            self.meta = {k[5:]: v for k, v in a.items() if k.startswith("data-")}
        if tag == "article" and "item" in cls:
            self._cur = {"qid": a.get("data-qid"), "docid": a.get("data-docid"), "phase": a.get("data-phase"),
                         **{f: "" for f in self.FIELDS}, "has_date": False}
            self._depth = 0
        if self._cur is not None:
            self._depth += 1
            hit = cls & self.FIELDS
            if hit and self._field is None:
                self._field = hit.pop()
                self._fdepth = self._depth
                if self._field == "date":
                    self._cur["has_date"] = True

    def handle_endtag(self, tag):
        if self._cur is None:
            return
        if self._field is not None and self._depth == self._fdepth:
            self._field = None
        self._depth -= 1
        if tag == "article" and self._depth == 0:
            self.items.append(self._cur)
            self._cur = None

    def handle_data(self, data):
        if self._cur is not None and self._field is not None:
            self._cur[self._field] += data


def parse_page(path: str | Path) -> Tuple[dict, List[dict]]:
    p = _PageParser()
    p.feed(Path(path).read_text(encoding="utf-8"))
    for it in p.items:
        for f in _PageParser.FIELDS:
            it[f] = " ".join(it[f].split())
    return p.meta, p.items


def check_page(path: str | Path, pool_obj: dict | None = None, topics: Dict[str, dict] | None = None,
               annotator: str | None = None, allow_empty: bool = False) -> List[str]:
    """Return a list of problems (empty list = page is fine)."""
    meta, items = parse_page(path)
    probs = []
    name = Path(path).name
    if not meta.get("annotator"):
        probs.append(f"{name}: no annotator in page metadata")
    if not items and not allow_empty:
        probs.append(f"{name}: page has no items")
    if meta.get("n-items") and int(meta["n-items"]) != len(items):
        probs.append(f"{name}: header says {meta['n-items']} items, page has {len(items)}")
    seen = set()
    for it in items:
        key = (it["qid"], it["docid"])
        where = f"{name}: query {it['qid']}, document {it['docid']}"
        if key in seen:
            probs.append(f"{where}: appears twice")
        seen.add(key)
        for f in REQUIRED_TEXT:
            if not it[f]:
                probs.append(f"{where}: blank {f}")
        if topics is not None:
            t = topics.get(it["qid"])
            if t is None:
                probs.append(f"{where}: query not in topics")
            else:
                if it["query"] != _clean(t["query"]):
                    probs.append(f"{where}: query text differs from topics file")
                if it["narr"] != _clean(t["narrative"]):
                    probs.append(f"{where}: narrative differs from topics file")
                is_time = t.get("category") == "time"
                if is_time and not it["date"]:
                    probs.append(f"{where}: time query without the paper date")
                if not is_time and it["has_date"]:
                    probs.append(f"{where}: date shown for a non-time query")
    if pool_obj is not None:
        ann = annotator or meta.get("annotator")
        if meta.get("pool-id") != pool_obj["pool_id"]:
            probs.append(f"{name}: generated from pool {meta.get('pool-id')}, expected {pool_obj['pool_id']}")
        exp = set(expected_pairs(pool_obj, ann))
        missing, extra = exp - seen, seen - exp
        if missing:
            probs.append(f"{name}: {len(missing)} assigned pairs missing, e.g. {sorted(missing)[:3]}")
        if extra:
            probs.append(f"{name}: {len(extra)} pairs not assigned to {ann}, e.g. {sorted(extra)[:3]}")
    return probs
