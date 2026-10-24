"""Generates kaggle_rq5.ipynb (run: python notebooks/make_rq5_notebook.py)."""
from pathlib import Path

import nbformat as nbf

nb = nbf.v4.new_notebook()
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s))
code = lambda s: C.append(nbf.v4.new_code_cell(s))

md("""# RQ5 on Kaggle: BM25 parameter sweep and tokenisation ablation (Group 10)

**Setup (once):**
1. *Settings → Accelerator:* **None** (CPU is enough). *Settings → Internet:* **On**.
2. *Add Input → Datasets:* **"arXiv Dataset" by Cornell University**. If Kaggle lets you choose the
   version, pick the one that was current on **19 Oct 2026** (the corpus of the frozen runs).
3. *Run All*. Expected time: about 10–15 minutes (corpus build 3–5 min, sweep and ablation a few minutes).

The notebook **stops** if the rebuilt corpus is not the one behind the frozen runs
(39,613 documents, SHA-256 starting `fda391ecc5b6`, and the default BM25 run must reproduce the
committed `runs/bm25.run`). Nothing in `data/qrels/`, `runs/` or `deliverables/final/` is written.

At the end, download **`/kaggle/working/rq5_outputs.zip`**.""")

code("""REPO_URL = "https://github.com/surajsinhpatil/bm25-vs-neural.git"
import glob, os, subprocess, sys
def sh(cmd):
    print("$", cmd, flush=True)
    r = subprocess.run(cmd, shell=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"command failed ({r.returncode}): {cmd}")
os.chdir("/kaggle/working")
if not os.path.exists("bm25-vs-neural"):
    sh(f"git clone {REPO_URL}")
os.chdir("/kaggle/working/bm25-vs-neural")
sh("git log -1 --format='%H %s'")
assert os.path.exists("src/irproj/rq5.py"), "this commit does not contain the RQ5 code yet - push it first"
SNAPSHOT = (glob.glob("/kaggle/input/arxiv/arxiv-metadata-oai-snapshot.json")
            or glob.glob("/kaggle/input/**/arxiv-metadata-oai-snapshot.json", recursive=True))
assert SNAPSHOT, "attach the Cornell 'arXiv Dataset' (Add Input -> Datasets)"
SNAPSHOT = SNAPSHOT[0]; print("snapshot:", SNAPSHOT, os.path.getsize(SNAPSHOT) // 2**20, "MB")""")

md("## 1. Install and test")
code("""sh("pip install -q -e . pytrec_eval-terrier scikit-learn")
sh("python -m pytest -q tests")""")

md("## 2. Rebuild the corpus and compare it with the frozen one")
code("""sh(f"python scripts/build_corpus.py --snapshot {SNAPSHOT} --out data/corpus/cscr.jsonl > /dev/null")
import json
m = json.load(open("data/corpus/cscr.jsonl.manifest.json")); e = json.load(open("data/corpus/EXPECTED.json"))
print("n_docs  :", m["n_docs"], "expected", e["n_docs"])
print("sha256  :", m["sha256"], "expected prefix", e["sha256_prefix"])
if m["n_docs"] != e["n_docs"] or not m["sha256"].startswith(e["sha256_prefix"]):
    raise RuntimeError("Corpus differs from the one behind the frozen runs. Attach the arXiv dataset version "
                       "from 19 Oct 2026 and run again. (The RQ5 scripts would refuse to run on this corpus.)")
print("corpus matches")""")

md("## 3. BM25 k1 / b sweep (132 settings, 5-fold CV)")
code("""sh("python scripts/bm25_sweep.py --corpus data/corpus/cscr.jsonl")""")

md("## 4. Tokenisation ablation (5 analyzers, k1=1.2, b=0.75)")
code("""sh("python scripts/tokenizer_ablation.py --corpus data/corpus/cscr.jsonl")""")

md("## 5. Check that no frozen file changed, then package")
code("""sh("git status --porcelain data/qrels runs judging deliverables/final deliverables/candidate deliverables/preliminary")
out = subprocess.run("git status --porcelain data/qrels runs judging deliverables/final", shell=True,
                     capture_output=True, text=True).stdout.strip()
assert not out, "a frozen file changed:\\n" + out
sh("zip -qr /kaggle/working/rq5_outputs.zip deliverables/rq5 report/tables/rq5_sweep.tex report/tables/rq5_tok.tex "
   "data/corpus/cscr.jsonl.manifest.json data/corpus/cscr.ids.txt")
sh("ls -la /kaggle/working/rq5_outputs.zip")""")

nb["cells"] = C
nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                  "language_info": {"name": "python"}}
nbf.write(nb, Path(__file__).with_name("kaggle_rq5.ipynb"))
print("written")
