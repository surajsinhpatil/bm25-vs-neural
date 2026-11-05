"""Offline results explorer: one self-contained HTML file with every test query, the top 10 of each of the
five evaluated systems, the team's adjudicated grades and per-query nDCG@10. Needs no corpus, GPU or internet;
it is the fallback for the live demo.

    python scripts/make_results_explorer.py      # -> deliverables/demo/results_explorer.html
Sources: runs/*.run, data/qrels/qrels.txt (frozen), deliverables/final/results/{summary,per_query}.csv,
titles and abstracts from judging/round1/judge_*.html (every top-10 document of every run was judged).
"""
import argparse
import csv
import html
import json
import re
from pathlib import Path

from irproj.io import load_topics, rank_docs, read_qrels, read_run, sha256_file

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--out", default=str(ROOT / "deliverables/demo/results_explorer.html"))
a = ap.parse_args()

SYS = [("bm25", "BM25"), ("e5", "E5"), ("bm25+e5", "BM25+E5"), ("specter2", "SPECTER2"), ("bm25+specter2", "BM25+SPECTER2")]
qrels = read_qrels(ROOT / "data/qrels/qrels.txt")
topics = [t for t in load_topics(ROOT / "data/queries/topics.jsonl") if t["qid"] in qrels]
runs = {s: read_run(ROOT / f"runs/{s}.run") for s, _ in SYS}
pq = {(r["system"], r["qid"]): float(r["ndcg@10"]) for r in csv.DictReader(open(ROOT / "deliverables/final/results/per_query.csv"))}
summary = {r["system"]: r for r in csv.DictReader(open(ROOT / "deliverables/final/results/summary.csv"))}

docs = {}
item = re.compile(r'<article class="item"[^>]*data-docid="([^"]+)".*?<h2 class="title">(.*?)</h2>.*?<p class="abstract">(.*?)</p>', re.S)
for page in sorted((ROOT / "judging/round1").glob("judge_*.html")):
    for docid, title, abstract in item.findall(page.read_text(encoding="utf-8")):
        docs.setdefault(docid, (html.unescape(title), html.unescape(abstract)))

data = {"systems": [n for _, n in SYS], "queries": [], "docs": {}, "summary": {}}
missing = set()
for s, name in SYS:
    x = summary[s]
    data["summary"][name] = {k: round(float(x[k]), 3) for k in ("ndcg@10", "ndcg@10_ci_low", "ndcg@10_ci_high", "p@5", "mrr@10")}
for t in topics:
    q = {"qid": t["qid"], "category": t["category"], "query": t["query"], "desc": t.get("description", ""),
         "narr": t.get("narrative", ""), "runs": {}}
    for s, name in SYS:
        top = [d for d, _ in rank_docs(runs[s][t["qid"]])[:10]]
        q["runs"][name] = {"ndcg": round(pq[(s, t["qid"])], 3),
                           "docs": [[d, qrels[t["qid"]].get(d)] for d in top]}
        for d in top:
            if d in docs:
                data["docs"][d] = docs[d]
            else:
                missing.add(d)
    data["queries"].append(q)
if missing:
    raise SystemExit(f"ERROR: {len(missing)} top-10 documents have no title in the judging pages")
data["provenance"] = {"qrels_sha256": sha256_file(ROOT / "data/qrels/qrels.txt")}

PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Results Explorer - Group 10</title>
<style>
:root{--bg:#fbfbfa;--fg:#1f2328;--mut:#5f6670;--line:#e3e3df;--card:#fff;--acc:#1c64c8;
--g0:#9aa1a9;--g1:#e8890c;--g2:#2f9e44;--g3:#1c64c8;--sel:#eaf2fd}
@media (prefers-color-scheme:dark){:root{--bg:#16181b;--fg:#e6e6e3;--mut:#a0a6ad;--line:#2d3136;--card:#1d2024;--acc:#6ea8ff;--sel:#1e2a3b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{padding:14px 20px;border-bottom:1px solid var(--line)}h1{font-size:18px;margin:0 0 2px}header p{margin:0;color:var(--mut);font-size:13px}
.wrap{display:flex;min-height:calc(100vh - 64px)}nav{width:330px;flex:none;border-right:1px solid var(--line);overflow-y:auto;max-height:calc(100vh - 64px);position:sticky;top:0}
nav h4{margin:12px 14px 4px;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut)}
nav button{display:block;width:100%;text-align:left;border:0;background:none;color:var(--fg);padding:6px 14px;font:13px system-ui,sans-serif;cursor:pointer}
nav button:hover{background:var(--sel)}nav button.on{background:var(--sel);box-shadow:inset 3px 0 var(--acc)}
nav .qn{color:var(--mut);margin-right:4px}main{flex:1;padding:16px 20px;min-width:0}
.sum{border-collapse:collapse;margin:4px 0 14px;font-size:13px}.sum td,.sum th{padding:3px 10px;border-bottom:1px solid var(--line);text-align:right}.sum th:first-child,.sum td:first-child{text-align:left}
.q{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:10px 14px;margin-bottom:12px}.q h2{margin:0 0 4px;font-size:17px}
.tag{display:inline-block;font-size:12px;padding:0 7px;border-radius:9px;background:var(--sel);margin-left:6px;vertical-align:2px}
.q p{margin:3px 0;color:var(--mut)}.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}
.col{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:8px 10px}.col h3{margin:0;font-size:15px;display:flex;justify-content:space-between}
.col h3 span{font-weight:normal;color:var(--mut);font-size:13px}ol{margin:6px 0 0;padding-left:22px}li{margin:4px 0}
.b{display:inline-block;min-width:17px;text-align:center;color:#fff;border-radius:3px;font-size:12px;margin-right:4px}
.g0{background:var(--g0)}.g1{background:var(--g1)}.g2{background:var(--g2)}.g3{background:var(--g3)}
li a{color:var(--fg);text-decoration:none;cursor:pointer}li a:hover{text-decoration:underline}.yr{color:var(--mut);font-size:12px}
li .abs{display:none;color:var(--mut);font-size:12px;margin:3px 0 6px}li.open .abs{display:block}
.legend{color:var(--mut);font-size:12px;margin:10px 0}.tog{margin:0 0 10px;font-size:13px}.tog label{margin-right:12px}
@media (max-width:760px){.wrap{display:block}nav{width:auto;max-height:240px;position:static;border-right:0;border-bottom:1px solid var(--line)}}
</style></head><body>
<header><h1>Results Explorer: BM25 vs. neural retrieval on arXiv cs.CR (Group 10)</h1>
<p>50 test queries &middot; top 10 of each evaluated system &middot; grades from the team's frozen, adjudicated relevance judgments &middot; works offline</p></header>
<div class="wrap"><nav id="nav"></nav><main id="main"></main></div>
<script>
const D=__DATA__;
const CAT=["identifier","homonym","negation","time","paraphrase"];
const GT=["0 not relevant","1 on topic, does not answer","2 relevant","3 highly relevant"];
let shown=new Set(["BM25","E5","BM25+E5"]),cur=null;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function nav(){let h="";for(const c of CAT){h+=`<h4>${c}</h4>`;for(const q of D.queries.filter(q=>q.category==c))
h+=`<button data-q="${q.qid}"><span class="qn">Q${q.qid}</span>${esc(q.query)}</button>`}
document.getElementById("nav").innerHTML=h;
document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>show(b.dataset.q))}
function summary(){let h=`<table class="sum"><tr><th>System</th><th>nDCG@10 [95% CI]</th><th>P@5</th><th>MRR@10</th></tr>`;
for(const s of D.systems){const x=D.summary[s];h+=`<tr><td>${s}</td><td>${x["ndcg@10"].toFixed(3)} [${x["ndcg@10_ci_low"].toFixed(2)}, ${x["ndcg@10_ci_high"].toFixed(2)}]</td><td>${x["p@5"].toFixed(3)}</td><td>${x["mrr@10"].toFixed(3)}</td></tr>`}
return h+"</table>"}
function show(qid){cur=qid;try{location.hash="q"+qid}catch(e){}
document.querySelectorAll("nav button").forEach(b=>b.classList.toggle("on",b.dataset.q==qid));
const q=D.queries.find(x=>x.qid==qid);
let h=`<div class="q"><h2>Q${q.qid}: ${esc(q.query)}<span class="tag">${q.category}</span></h2><p>${esc(q.desc)}</p><p><b>Relevance criteria:</b> ${esc(q.narr)}</p></div>`;
h+=`<div class="tog">Systems: `+D.systems.map(s=>`<label><input type="checkbox" data-s="${s}" ${shown.has(s)?"checked":""}> ${s}</label>`).join("")+`</div><div class="cols">`;
for(const s of D.systems){if(!shown.has(s))continue;const r=q.runs[s];
h+=`<div class="col"><h3>${s}<span>nDCG@10 ${r.ndcg.toFixed(3)}</span></h3><ol>`;
for(const [d,g] of r.docs){const [t,a]=D.docs[d];const yr=d.match(/^\d{4}\./)?"20"+d.slice(0,2):"";
h+=`<li><span class="b g${g}" title="${GT[g]}">${g}</span><a>${esc(t)}</a> <span class="yr">${yr}</span><div class="abs">${esc(a)} <a href="https://arxiv.org/abs/${d}" target="_blank" rel="noopener">arXiv:${d}</a></div></li>`}
h+=`</ol></div>`}
h+=`</div><p class="legend">Grade: `+GT.map((t,g)=>`<span class="b g${g}">${g}</span>${t.slice(2)}`).join(" &nbsp; ")+` &middot; click a title for its abstract &middot; year = first arXiv version</p>`;
h+=`<details><summary>Overall results (all 50 queries)</summary>${summary()}</details>`;
document.getElementById("main").innerHTML=h;
document.querySelectorAll("li a:not([href])").forEach(a=>a.onclick=()=>a.parentElement.classList.toggle("open"));
document.querySelectorAll(".tog input").forEach(i=>i.onchange=()=>{i.checked?shown.add(i.dataset.s):shown.delete(i.dataset.s);show(cur)})}
nav();let start="8";try{const m=location.hash.match(/^#q(\d+)$/);if(m)start=m[1]}catch(e){}show(start);
</script></body></html>"""
out = Path(a.out)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")), encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size // 1024} KB): {len(data['queries'])} queries, {len(data['docs'])} documents")
