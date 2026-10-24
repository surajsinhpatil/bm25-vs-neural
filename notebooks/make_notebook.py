"""Generates kaggle_pipeline.ipynb (run: python notebooks/make_notebook.py)."""
import nbformat as nbf
from pathlib import Path

nb = nbf.v4.new_notebook()
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s))
code = lambda s: C.append(nbf.v4.new_code_cell(s))

md("""# BM25 vs. Neural Retrieval on cs.CR abstracts: full pipeline (Group 10)

**Kaggle setup (once):**
1. *Settings → Accelerator:* GPU T4 x2 or P100. *Settings → Internet:* On (needs a phone-verified Kaggle account).
2. *Add Input → Datasets:* search **"arXiv Dataset" by Cornell University** and add it. It appears under `/kaggle/input/arxiv/`.
3. Put the GitHub URL of the team repository in the first code cell and *Run All*.

Part A (sections 1–6) needs no relevance judgments and takes roughly 30–45 minutes.
It builds the corpus, validates BM25 and the metrics on SciFact, produces all five runs and writes
one blind judging page per annotator. Download `/kaggle/working/outputs.zip` at the end.

Part B (section 7) is run after the team has judged the pool and committed the exported
judgments to `judging/exports/` in the repository.""")

code("""REPO_URL = "https://github.com/<your-user>/bm25-vs-neural.git"   # <-- change me
ANNOTATORS = ["Suraj", "Tejas", "Swayam", "Saksham"]
SNAPSHOT = "/kaggle/input/arxiv/arxiv-metadata-oai-snapshot.json"
import os, subprocess, sys
os.chdir("/kaggle/working")
if not os.path.exists("bm25-vs-neural"):
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL], check=True)
os.chdir("/kaggle/working/bm25-vs-neural")
print(subprocess.run(["git", "log", "-1", "--oneline"], capture_output=True, text=True).stdout)""")

md("## 0. Install dependencies\n`adapters` pins a compatible `transformers`; Pyserini is installed without its heavy dependencies because we only use its Lucene BM25 (Java 21 is installed for it).")
code("""!pip install -q adapters pytrec_eval-terrier install-jdk nbformat
!pip install -q --no-deps pyserini pyjnius
!pip install -q -e .
import jdk, glob
if not glob.glob("/tmp/jdk/jdk-21*"):
    jdk.install("21", path="/tmp/jdk")
JAVA_HOME = sorted(glob.glob("/tmp/jdk/jdk-21*"))[0]
os.environ["JAVA_HOME"] = JAVA_HOME
os.environ["PATH"] = JAVA_HOME + "/bin:" + os.environ["PATH"]
!java -version
import torch; print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none")""")
code("!python -m pytest -q tests")

md("## 1. Build and freeze the corpus (≈ 3–5 min)")
code("""!python scripts/build_corpus.py --snapshot {SNAPSHOT} --out data/corpus/cscr.jsonl
!sha256sum data/corpus/cscr.jsonl""")

md("## 2. Validation on BEIR SciFact (success criteria i and ii) + all five systems on SciFact\nThis gives the first quantitative comparison against a baseline on a collection that already has judgments.")
code("""r = subprocess.run([sys.executable, "scripts/validate_scifact.py", "--data", "data/beir", "--out", "results",
                    "--dense", "--tables", "report/tables"], capture_output=True, text=True)
print(r.stdout[-6000:]); print(r.stderr[-3000:])
# significance tests on SciFact (qrels ship with Pyserini)
from pyserini.search import get_qrels
from irproj.io import write_qrels
q = get_qrels("beir-v1.0.0-scifact-test")
write_qrels("data/beir/scifact.test.qrels.txt", {str(k): {str(d): int(g) for d, g in v.items()} for k, v in q.items()})
!python scripts/scifact_significance.py --runs-dir runs/scifact --qrels data/beir/scifact.test.qrels.txt""")

md("## 3. Check the queries against the corpus\nEvery query needs at least one confirmed relevant document. Anchors that are missing must be replaced by reading random abstracts (`scripts/sample_anchors.py`), **not** by searching with our systems.")
code("!python scripts/check_queries.py --corpus data/corpus/cscr.jsonl --topics data/queries/topics.jsonl")
code('!python scripts/sample_anchors.py --corpus data/corpus/cscr.jsonl --n 3 --pattern "CVE-[0-9]+-[0-9]+" --seed 1')

md("## 4. The five runs")
code("""T = "data/queries/topics.jsonl"; C = "data/corpus/cscr.jsonl"
!python scripts/run_bm25.py --corpus {C} --topics {T} --analyzer id --k1 1.2 --b 0.75 --out runs/bm25.run
!python scripts/encode_corpus.py --model e5 --corpus {C} --out indexes/e5 --batch-size 128
!python scripts/run_dense.py --model e5 --index indexes/e5 --topics {T} --out runs/e5.run
!python scripts/encode_corpus.py --model specter2 --corpus {C} --out indexes/specter2 --batch-size 64
!python scripts/run_dense.py --model specter2 --index indexes/specter2 --topics {T} --out runs/specter2.run
!python scripts/run_fusion.py --runs runs/bm25.run runs/e5.run --tag bm25+e5 --out runs/bm25+e5.run
!python scripts/run_fusion.py --runs runs/bm25.run runs/specter2.run --tag bm25+specter2 --out runs/bm25+specter2.run""")
code("""RUNS = "runs/bm25.run runs/e5.run runs/specter2.run runs/bm25+e5.run runs/bm25+specter2.run"
!python scripts/run_overlap.py --runs runs/bm25.run runs/e5.run runs/specter2.run --topics {T} --out results --tables report/tables
!python scripts/make_report_macros.py --fallback report/tables/macros.tex""")

md("""## 5. Judging pages
The round-1 pool is frozen in the repository (`judging/round1/pool.json`, 1,339 pairs). If you
re-run the retrieval, freeze a new pool first with `scripts/make_pool.py ... --force`.
This cell renders one page per annotator from the frozen pool and checks every item
(query, description, relevance criteria, title, abstract, date for time queries, assignment).
Download `/kaggle/working/judging_round1.zip`.""")
code("""ANN = " ".join(ANNOTATORS)
!python scripts/make_judging_pages.py --snapshot {SNAPSHOT} --zip /kaggle/working/judging_round1.zip""")

md("## 6. Package everything for download")
code("""!zip -qr /kaggle/working/outputs.zip runs results report/tables report/figures judging/round1 data/corpus/cscr.jsonl.manifest.json data/corpus/cscr.ids.txt indexes/*.encode.json
!ls -la /kaggle/working/outputs.zip""")

md("""## 6b. (Optional, for the intermediate report) preliminary numbers from partial judgments
Commit whatever the annotators have exported so far (phase 1 first) to `judging/exports/`.
Disagreements are resolved to the lower grade and unjudged documents count as non-relevant,
so these numbers are exploratory only; @5 metrics are the most reliable once phase 1 is done.""")
code("""!git pull -q
!python scripts/merge_judgments.py --exports "judging/exports/*_main.json" --out data/qrels --fallback lower
!python scripts/evaluate.py --qrels data/qrels/qrels.preliminary-lower.txt --topics {T} --runs {RUNS} --out results --tables report/tables --figures report/figures --label -prelim
!python scripts/make_report_macros.py
!zip -qr /kaggle/working/outputs_prelim.zip results report/tables report/figures data/qrels""")

md("""## 7. Part B: after judging
Commit the exported `judgments_<name>_main.json` files to `judging/exports/` (and the
filled-in `data/qrels/disagreements.csv` after the adjudication meeting), push, then re-run
the first cell (it pulls the repo) and the cells below. The runs from Part A are in
`outputs.zip`; unzip them into the repo folder first if this is a new session.""")
code("""!git pull -q
# stop here (Run All halts on this exception) if nobody has exported judgments yet
import glob
if not glob.glob("judging/exports/*_main.json"):
    raise RuntimeError("No judgments in judging/exports/ - Part B needs the annotators' exported JSON files.")
!python scripts/merge_judgments.py --exports "judging/exports/*_main.json" --out data/qrels --corpus {C}
# after adjudication:
# !python scripts/merge_judgments.py --exports "judging/exports/*_main.json" --adjudication data/qrels/disagreements.csv --out data/qrels --freeze""")
code("""Q = "data/qrels/qrels.txt"
!python scripts/evaluate.py --qrels {Q} --topics {T} --runs {RUNS} --out results --tables report/tables --figures report/figures
!python scripts/bm25_sweep.py --corpus {C}
!python scripts/tokenizer_ablation.py --corpus {C}""")
md("### Stretch goals")
code("""!python scripts/stretch_rerank.py --run runs/bm25+e5.run --corpus {C} --topics {T} --out runs/ce.run
!python scripts/stretch_time_filter.py --run runs/bm25+e5.run --corpus {C} --topics {T} --out runs/bm25+e5+time.run
!python scripts/stretch_cc_fusion.py --lexical runs/bm25.run --dense runs/e5.run --topics {T} --qrels {Q} --out runs/cc-bm25+e5.run
# new documents retrieved by these runs must be judged in an extra round before their scores are final:
!python scripts/make_pool.py --runs runs/ce.run runs/bm25+e5+time.run runs/cc-bm25+e5.run --topics {T} --annotators {ANN} --out judging/round2 --already-judged {Q} --round extra
!python scripts/make_judging_pages.py --pool judging/round2/pool.json --practice-k 0 --zip /kaggle/working/judging_round2.zip""")
code("""!zip -qr /kaggle/working/outputs_final.zip runs results report/tables report/figures judging/round2 data/qrels""")

nb["cells"] = C
nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                  "language_info": {"name": "python"}}
nbf.write(nb, Path(__file__).with_name("kaggle_pipeline.ipynb"))
print("written")
