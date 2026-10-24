# RQ5: BM25 sensitivity to k1, b and tokenisation

**Status: DONE, EXPLORATORY.** Run on Kaggle on 24 Oct 2026 from commit `df51119`. All checks passed:
- frozen qrels SHA-256 `8cc5fac5…`;
- corpus of 39,613 documents with SHA-256 `fda391ecc5b6…`;
- the default BM25 run reproduced the committed `runs/bm25.run` (same top 10 for all 50 queries, scores within 4e-6).

The files in `sweep/` and `tokenisation/`, and the corpus manifest and id list in `kaggle_run/`, are the Kaggle outputs, unchanged; this README is the only file edited since. `kaggle_run/rq5_outputs.sha256` (added after download) lists the SHA-256 of every file in the downloaded zip, plus the zip itself. `rq5_sweep.tex` and `rq5_tok.tex` were written by the experiment scripts on Kaggle. The report uses tables made from these outputs by `scripts/make_rq5_report.py`. Every number in those tables was checked independently against the per-query CSVs and against `trec_eval` on the saved runs.

## Findings (details and caveats in report Section 5.6)
- **k1 / b:** on nDCG@10, none of the 132 settings beats the default. 12 settings lie within 0.01 of it (k1 0.9–1.2, b 0.4–0.9).
- **Cross-validated tuning:**
  - nDCG@10 is 0.684 against 0.689 for the default (Δ −0.006, 95% CI −0.011 to −0.002, p = 0.012).
  - On condensed nDCG@10 the difference is −0.0001 (p = 0.96).
  - The metrics disagree, so the conclusion is "tuning did not help", not "tuning hurts".
- **The two metrics favour opposite regions of the grid.** The best setting on condensed nDCG@10 is (0.2, 0.9), where 25.8% of the top 10 is unjudged. Across the grid, Hole@10 correlates with nDCG@10 at r = −0.97 and with condensed nDCG@10 at r = +0.86.
- **Identifier handling (`plain` vs `id`):** Δ −0.003 (p_Holm 0.27); 41 of 50 queries are unchanged, and the two metrics agree. With Hole@10 at 0.8%, this is the one comparison almost free of pool bias.
- **Stemming:** without stemming, nDCG@10 drops by 0.089, but Hole@10 rises to 23.6%, and condensed nDCG@10 rises by 0.033. Both differences are significant and point in opposite directions, so this is inconclusive.
- **Stopwords:** no conclusion either way.
- **What would settle it:** judging the 141 unjudged query–document pairs in the variants' top 10s.

Every RQ5 result is **exploratory** (see "Interpretation" below). The frozen primary results
(`data/qrels/`, `runs/`, `deliverables/final/`) are not changed. The scripts refuse to write into
those locations and refuse to run on qrels whose SHA-256 differs from `data/qrels/qrels.sha256`.

## Design (fixed before any result was computed)
Unless stated otherwise, everything matches the main experiment:
- same corpus, the 50 queries (`query` field), the frozen qrels and the same metric code;
- nDCG@10 is the primary metric; unjudged documents count as non-relevant.

### RQ5a: k1/b sweep (`scripts/bm25_sweep.py`)
- **Analyzer:** `id`, the main one.
- **Grid:** 132 settings.
  - k1 ∈ {0.2, 0.4, …, 2.0} ∪ {0.9}.
  - b ∈ {0.0, 0.1, …, 1.0} ∪ {0.75}.
  - Why this grid:
    - b covers its whole range.
    - k1 runs from almost binary term frequency to the top of the usual range. Documents are short abstracts (mean length 140 tokens).
    - It contains the main setting (1.2, 0.75) and the Anserini default (0.9, 0.4).
- **No separate tuning set exists.** The only tuned number reported is cross-validated:
  - 5 folds, stratified by category (2 queries per category per fold), fold seed 11;
  - for each held-out fold, the setting with the best mean nDCG@10 on the other four folds is used;
  - exact ties go to the setting closest to (1.2, 0.75);
  - 20 further fold seeds (101–120) show how much the estimate depends on the split.
- **Best grid setting:** reported only as *sensitivity*. It is chosen on the same queries it is scored on, so it is not a performance estimate.
- **CV vs default:** compared with a paired randomisation test (100,000 permutations).

### RQ5b: tokenisation ablation (`scripts/tokenizer_ablation.py`)
k1 = 1.2 and b = 0.75 throughout, so only the analyzer changes. The analyzers are those in `src/irproj/tokenize.py`, unchanged:

| Variant | What changes compared with `id` (main) |
|---|---|
| `plain` | No identifier handling. No protocol-version normalisation ("TLS 1.3" stays "tl" + "1.3"); identifiers such as CVE-2021-44228 are split into pieces and not kept whole; tokens with digits are stemmed. Same stopwords and Porter stemmer. |
| `id-nostem` | No Porter stemming. |
| `plain-nostem` | Both of the above (completes a 2×2: identifier handling × stemming). |
| `id-nostop` | Lucene's 33 stopwords are kept, including "not" and "no". |

Each variant is compared with `id` by a paired randomisation test, with Holm correction over the 4 comparisons.

## Interpretation: pool bias
The judging pool is the top 10 of five runs, and one of them is exactly the default BM25 run (`id`, k1 = 1.2, b = 0.75). Every other setting or analyzer retrieves documents nobody judged, and they count as non-relevant, which favours the default. To show how large this effect is, each result also reports:
- **Hole@10**: the share of the top 10 never judged;
- **condensed nDCG@10** (`ndcgc@10`; Sakai 2007): nDCG@10 after unjudged documents are removed from the ranking.

Condensed nDCG is a robustness check, not a bound and not an unbiased estimate. A conclusion is called robust only if nDCG@10 and condensed nDCG@10 agree. Because the bias favours the default, "worse than the default" is weaker evidence than "better than the default". Only an extra round of human judging of the new documents would remove the bias.

## Checks done before any number is computed
1. The qrels SHA-256 equals `data/qrels/qrels.sha256`; otherwise the script stops.
2. The rebuilt corpus has the 39,613 documents and SHA-256 prefix `fda391ecc5b6` recorded in `data/corpus/EXPECTED.json`.
3. The default BM25 run rebuilt from that corpus reproduces the committed `runs/bm25.run`: same top 10 for every query, scores within 1e-4.

If check 2 or 3 fails, the scripts stop. `--allow-corpus-mismatch` overrides this, and the results are then labelled NOT COMPARABLE.

## Outputs
```
deliverables/rq5/sweep/
  bm25_sweep.json             summary: design, checks, default, CV (+ test vs default, other seeds),
                              best grid setting, range, per-category best settings (exploratory)
  bm25_sweep_grid.csv         mean nDCG@10, condensed nDCG@10, Hole@10, MRR@10, P@5 (+ nDCG@10 per category) per setting
  bm25_sweep_per_query.csv    every setting x query
  bm25_sweep_cv_per_query.csv setting used for each held-out query, CV vs default per query
  bm25_sweep_{ndcg10,ndcgc10,hole10}.{pdf,png}   heatmaps
  metadata.json               commit, Python and package versions, SHA-256 of corpus/topics/qrels, arguments
  rq5_sweep.tex               table written by the script
deliverables/rq5/tokenisation/
  tokenizer_ablation.json / .csv, tokenizer_ablation_per_query.csv, metadata.json, rq5_tok.tex
  runs/bm25-<variant>.run     top 100 per query (TREC format)
deliverables/rq5/kaggle_run/
  cscr.jsonl.manifest.json    manifest of the corpus rebuilt on Kaggle (full SHA-256, filter counts)
  cscr.ids.txt                the 39,613 arXiv ids
  rq5_outputs.sha256          SHA-256 of every file in the downloaded rq5_outputs.zip
```
Report tables, macros and the figure: `python scripts/make_rq5_report.py` writes `report/tables/rq5_{sweep,tok,macros}.tex` and `report/figures/rq5_sweep.pdf` from these files. It stops unless every recorded check passed.

## Run elsewhere
To run outside Kaggle, `data/corpus/cscr.jsonl` must first be built from the arXiv snapshot (`scripts/build_corpus.py`). Then:
```bash
pip install -e .
python scripts/bm25_sweep.py --corpus data/corpus/cscr.jsonl
python scripts/tokenizer_ablation.py --corpus data/corpus/cscr.jsonl
```
On a synthetic corpus of the same size (39,613 documents), the sweep took 32 s and the ablation 56 s on one CPU. Real text tokenises more slowly.
