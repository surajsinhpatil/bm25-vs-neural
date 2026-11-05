"""Generates kaggle_demo.ipynb, the live search demo (run: python notebooks/make_demo_notebook.py)."""
from pathlib import Path

import nbformat as nbf

nb = nbf.v4.new_notebook()
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s))
code = lambda s: C.append(nbf.v4.new_code_cell(s))

md("""# Live demo: BM25 vs. neural retrieval on 39,613 arXiv cs.CR abstracts (Group 10)

**Setup (once, about 10 minutes):**
1. *Settings → Accelerator:* **GPU T4**. *Settings → Internet:* **On**.
2. *Add Input → Datasets:* **"arXiv Dataset" by Cornell University** (the version used on 19 Oct 2026, if you can choose).
3. *Run All*, then use the search box at the end.

Start it **30 minutes before the meeting** and keep the tab open: the indexes live in memory.
The systems are exactly the evaluated ones (identifier-aware BM25 with k1=1.2, b=0.75; E5-base-v2 with exact
cosine search; RRF k=60 over the top 100). Section 4 checks this against the committed runs.""")

code("""REPO_URL = "https://github.com/surajsinhpatil/bm25-vs-neural.git"
import glob, os, subprocess, time
def sh(cmd):
    print("$", cmd, flush=True)
    r = subprocess.run(cmd, shell=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"command failed ({r.returncode}): {cmd}")
os.chdir("/kaggle/working")
if not os.path.exists("bm25-vs-neural"):
    sh(f"git clone -q {REPO_URL}")
os.chdir("/kaggle/working/bm25-vs-neural")
sh("git log -1 --format='%h %s'")
sh("pip install -q -e .")
import torch
print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NONE - set Accelerator to GPU T4")
SNAPSHOT = (glob.glob("/kaggle/input/arxiv/arxiv-metadata-oai-snapshot.json")
            or glob.glob("/kaggle/input/**/arxiv-metadata-oai-snapshot.json", recursive=True))
assert SNAPSHOT, "attach the Cornell 'arXiv Dataset' (Add Input -> Datasets)"
SNAPSHOT = SNAPSHOT[0]""")

md("## 1. Corpus (3-5 min)")
code("""C = "data/corpus/cscr.jsonl"
if not os.path.exists(C):
    sh(f"python scripts/build_corpus.py --snapshot {SNAPSHOT} --out {C} > /dev/null")
import json
m, e = json.load(open(C + ".manifest.json")), json.load(open("data/corpus/EXPECTED.json"))
SAME_CORPUS = m["n_docs"] == e["n_docs"] and m["sha256"].startswith(e["sha256_prefix"])
print(f"{m['n_docs']:,} documents, SHA-256 {m['sha256'][:12]}...",
      "= the frozen corpus" if SAME_CORPUS else "- WARNING: not the frozen corpus; search works, but grades may not match")""")

md("## 2. BM25 index (about 30 s)")
code("""from irproj.demo import Searcher
S = Searcher.from_files(C, topics="data/queries/topics.jsonl", qrels="data/qrels/qrels.txt")
print(f"BM25 index: {len(S.bm25.vocab):,} terms, {S.bm25.index_bytes() / 2**20:.1f} MB, built in {S.bm25_build_s:.0f} s")""")

md("## 3. E5 dense index (about 3 min on a T4)")
code("""if not os.path.exists("indexes/e5.npy"):
    sh(f"python scripts/encode_corpus.py --model e5 --corpus {C} --out indexes/e5 --batch-size 128")
from irproj.dense import DenseIndex, encoder_from_args
E5 = encoder_from_args("e5", None, None, None)
S.add_dense("E5", E5, DenseIndex.load("indexes/e5"))
S.search("warm up")   # first query loads CUDA kernels
print("ready")""")

md("## 4. Check: the demo returns the evaluated rankings\nFor all 50 test queries, compares the demo's top 10 with the committed run files.")
code("""from irproj.io import load_topics, read_run, rank_docs
runs = {"BM25": read_run("runs/bm25.run"), "E5": read_run("runs/e5.run"), "BM25+E5": read_run("runs/bm25+e5.run")}
same = {n: 0 for n in runs}
for t in load_topics("data/queries/topics.jsonl"):
    r = S.search(t["query"])
    for n, run in runs.items():
        same[n] += [x["docid"] for x in r["systems"][n]["items"]] == [d for d, _ in rank_docs(run[t["qid"]])[:10]]
print("queries with an identical top 10 (of 50):", same)
print("(E5 on a GPU in fp16 can move a near-tie by one place; BM25 must be 50/50 on the frozen corpus)")""")

md("""## 5. Search
Pick a test query (team's relevance grades shown: 0 grey, 1 orange, 2 green, 3 blue, ? never judged) or type any query.

**Suggested demo order**
1. Q8 *replay attacks on TLS 1.3 0-RTT early data*: exact identifiers, BM25 0.82 vs. E5 0.18.
2. Q48 *programs that lock a victim's files and demand payment to unlock them*: paraphrase, BM25 0.18 vs. E5 0.82.
3. Q29 *anonymous communication systems that are not based on Tor*: negation, BM25 0.45 vs. E5 0.79; many BM25 results are Tor papers.
4. Q38 *membership inference attacks on large language models published since 2023*: the hybrid (0.95) beats both.
5. Q33 *ransomware detection published before 2018*: look at the years; every system returns 10 of 10 papers from 2018 or later.
6. Any query typed live; compare the times (BM25 ~1-2 ms, E5 ~10-20 ms).""")
code("""import ipywidgets as W
from IPython.display import HTML, display
topics = load_topics("data/queries/topics.jsonl")
pick = W.Dropdown(options=[("- type your own query below -", "")] + [(f"Q{t['qid']} [{t['category']}] {t['query']}", t["query"]) for t in topics],
                  layout=W.Layout(width="95%"), description="Test query")
box = W.Text(placeholder="type any query and press Enter", layout=W.Layout(width="80%"), description="Query")
btn = W.Button(description="Search", button_style="primary")
out = W.Output()
def run(_=None):
    q = box.value.strip() or pick.value
    if q:
        with out:
            out.clear_output()
            display(HTML(S.render(S.search(q))))
pick.observe(lambda ch: (setattr(box, "value", ""), run()) if ch["name"] == "value" and ch["new"] else None)
box.on_submit(run); btn.on_click(run)
display(pick, W.HBox([box, btn]), out)""")

md("If the widgets do not render, call `show(\"your query\")` instead:")
code("""def show(q):
    display(HTML(S.render(S.search(q))))
show("replay attacks on TLS 1.3 0-RTT early data")""")

nb["cells"] = C
nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                  "language_info": {"name": "python"}}
nbf.write(nb, Path(__file__).with_name("kaggle_demo.ipynb"))
print("written")
