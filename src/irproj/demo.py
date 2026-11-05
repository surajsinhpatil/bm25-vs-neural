"""Interactive search demo: BM25, E5 and BM25+E5 (RRF) side by side for any query.

Uses exactly the systems of the main experiment (identifier-aware BM25 with k1=1.2, b=0.75;
E5-base-v2 with exact cosine search; RRF k=60 over the top 100 of each). When the query is one of
the 50 test queries, the team's adjudicated relevance grades from the frozen qrels are shown next
to each result, with nDCG@10 per system; documents nobody judged are marked as unjudged.

    from irproj.demo import Searcher
    s = Searcher.from_files("data/corpus/cscr.jsonl", topics="data/queries/topics.jsonl",
                            qrels="data/qrels/qrels.txt")
    s.add_dense("E5", encoder, DenseIndex.load("indexes/e5"))
    html = s.render(s.search("exploitation of Log4Shell (CVE-2021-44228)"))
"""
from __future__ import annotations

import html
import time
from typing import Dict, List, Optional, Sequence

from .bm25 import BM25Index
from .fusion import rrf
from .io import doc_text, load_corpus, load_topics, rank_docs, read_qrels
from .metrics import ndcg_at_k
from .tokenize import get_analyzer

GRADE_TEXT = {0: "0 not relevant", 1: "1 on topic, does not answer", 2: "2 relevant", 3: "3 highly relevant"}
GRADE_COLOR = {0: "#adb5bd", 1: "#f59f00", 2: "#37b24d", 3: "#1971c2"}


def _norm(q: str) -> str:
    return " ".join(q.lower().split())


class Searcher:
    def __init__(self, ids: Sequence[str], docs: Sequence[dict], topics: Optional[List[dict]] = None,
                 qrels: Optional[Dict[str, Dict[str, int]]] = None, analyzer: str = "id",
                 k1: float = 1.2, b: float = 0.75):
        self.ids = list(ids)
        self.docs = {i: d for i, d in zip(self.ids, docs)}
        self.k1, self.b = k1, b
        t0 = time.perf_counter()
        self.bm25 = BM25Index(get_analyzer(analyzer)).build(self.ids, (doc_text(d) for d in docs))
        self.bm25.weighted(k1, b)
        self.bm25_build_s = time.perf_counter() - t0
        self.dense = {}                      # name -> (encoder, DenseIndex)
        self.topics = topics or []
        self.qrels = qrels or {}
        self.by_text = {_norm(t["query"]): t for t in self.topics}

    @classmethod
    def from_files(cls, corpus: str, topics: Optional[str] = None, qrels: Optional[str] = None, **kw):
        ids, docs = load_corpus(corpus)
        return cls(ids, docs, load_topics(topics) if topics else None, read_qrels(qrels) if qrels else None, **kw)

    def add_dense(self, name: str, encoder, index) -> None:
        if list(index.doc_ids) != self.ids:
            raise ValueError(f"{name} index does not cover the same documents in the same order as the corpus")
        self.dense[name] = (encoder, index)

    # ------------------------------------------------------------------ search
    def search(self, query: str, k: int = 10) -> dict:
        query = query.strip()
        topic = self.by_text.get(_norm(query))
        # the evaluated runs were stored with 6-decimal scores (inputs and fused output): round the same
        # way, so near-ties are ordered exactly as in the experiment (by document id, like trec_eval)
        r6 = lambda x: {d: round(v, 6) for d, v in x.items()}
        out = {"query": query, "topic": topic, "systems": {}}
        t0 = time.perf_counter()
        bm = r6(self.bm25.search(query, 100, self.k1, self.b))
        t_bm = time.perf_counter() - t0
        out["systems"]["BM25"] = (bm, t_bm)
        for name, (enc, index) in self.dense.items():
            t0 = time.perf_counter()
            q = enc.encode_queries([query])
            run, _ = index.search(q, ["q"], k=100)
            t_d = time.perf_counter() - t0
            out["systems"][name] = (r6(run["q"]), t_d)
            t0 = time.perf_counter()
            fused = r6(rrf([{"q": bm}, {"q": r6(run["q"])}], k=60, depth=100, out_depth=100)["q"])
            out["systems"][f"BM25+{name}"] = (fused, t_bm + t_d + time.perf_counter() - t0)
        res = {}
        for name, (scores, secs) in out["systems"].items():
            ranked = rank_docs(scores)[:k]
            judged = self.qrels.get(topic["qid"], {}) if topic else {}
            items = [{"rank": r, "docid": d, "score": s, "title": self.docs[d].get("title", ""),
                      "year": self.docs[d].get("year"), "grade": judged.get(d) if topic else None,
                      "judged": (d in judged) if topic else None} for r, (d, s) in enumerate(ranked, 1)]
            ndcg = ndcg_at_k([d for d, _ in rank_docs(scores)], judged, 10) if topic and judged else None
            res[name] = {"items": items, "ms": 1000 * secs, "ndcg@10": ndcg}
        out["systems"] = res
        return out

    # ------------------------------------------------------------------ rendering
    def render(self, result: dict) -> str:
        t = result["topic"]
        head = f"<div style='font:14px sans-serif;margin:4px 0 8px'><b>Query:</b> {html.escape(result['query'])}"
        if t:
            head += (f" &nbsp;<span style='background:#e7f5ff;padding:1px 6px;border-radius:4px'>test query {t['qid']}, "
                     f"category: {html.escape(t['category'])}</span><br><span style='color:#555'>Relevance criteria: "
                     f"{html.escape(t.get('narrative', ''))}</span>")
        else:
            head += " &nbsp;<span style='color:#777'>(free query: no human judgments)</span>"
        head += "</div>"
        cols = []
        for name, r in result["systems"].items():
            sub = f"{r['ms']:.1f} ms" + (f" &nbsp;|&nbsp; nDCG@10 = {r['ndcg@10']:.3f}" if r["ndcg@10"] is not None else "")
            rows = []
            for it in r["items"]:
                if it["grade"] is not None:
                    badge = (f"<span title='{GRADE_TEXT[it['grade']]}' style='display:inline-block;min-width:16px;"
                             f"text-align:center;color:white;border-radius:3px;background:{GRADE_COLOR[it['grade']]}'>"
                             f"{it['grade']}</span>")
                elif it["judged"] is False:
                    badge = "<span title='never judged' style='color:#999'>?</span>"
                else:
                    badge = ""
                rows.append(f"<li style='margin:3px 0'>{badge} <a href='https://arxiv.org/abs/{it['docid']}' "
                            f"target='_blank'>{html.escape(it['title'])}</a> <span style='color:#888'>({it['year']})</span></li>")
            cols.append(f"<div style='flex:1;min-width:260px;font:13px sans-serif'><div style='font-weight:bold;"
                        f"font-size:15px'>{html.escape(name)}</div><div style='color:#555;margin-bottom:4px'>{sub}</div>"
                        f"<ol style='padding-left:22px;margin:0'>{''.join(rows)}</ol></div>")
        legend = ""
        if t:
            legend = ("<div style='font:12px sans-serif;color:#555;margin-top:6px'>Grades (team, adjudicated): "
                      + " ".join(f"<span style='color:{GRADE_COLOR[g]}'>&#9632;</span> {GRADE_TEXT[g]}" for g in GRADE_TEXT)
                      + " &nbsp; ? = never judged (counts as not relevant)</div>")
        return head + "<div style='display:flex;gap:18px;flex-wrap:wrap'>" + "".join(cols) + "</div>" + legend
