# Demo for the IR group meeting (Group 10, 6 Nov 2026, 2:00–2:20 PM)

Two ways to demo:

| | Live search (main) | Results explorer (fallback) |
|---|---|---|
| File | `notebooks/kaggle_demo.ipynb` | `deliverables/demo/results_explorer.html` |
| Shows | any query typed live: BM25, E5, BM25+E5 side by side with query times; team grades for the 50 test queries | the 50 test queries: top 10 of all five systems, team grades, abstracts, per-query nDCG@10 |
| Needs | Kaggle, GPU T4, Internet on, arXiv dataset; about 10 min of setup | any browser, no internet |

Both show exactly the evaluated systems. Section 4 of the notebook checks the live demo against the committed runs, and `tests/test_demo.py` checks both.

## Live search on Kaggle
1. The notebook clones the repository from GitHub, so the demo code must be pushed first.
2. On Kaggle: *File → Import Notebook →* upload `notebooks/kaggle_demo.ipynb`.
3. Settings:
   - Accelerator: **GPU T4**;
   - Internet: **On**;
   - *Add Input*: **arXiv Dataset (Cornell University)**.
4. **Run All about 30 minutes before the meeting.** Building takes about 10 minutes: corpus 3–5 min, BM25 30 s, E5 about 3 min. Keep the tab open, because the indexes are in memory.
5. Section 4 must print BM25 50/50. E5 and BM25+E5 should also be 50 or very close.

## Suggested 20 minutes
| Time | What | Who |
|---|---|---|
| 0–2 | Problem and research questions | report coordinator |
| 2–5 | Pipeline: corpus → BM25 / E5 / SPECTER2 → RRF → pooling and human judging → evaluation | owners of each part |
| 5–12 | **Live demo** (queries below) | demo driver + person explaining |
| 12–15 | Results table, significance, RQ5 | evaluation owner |
| 15–20 | Remaining work, then questions | everyone |

## Demo queries (numbers are nDCG@10 from the frozen evaluation)
1. **Q8 "replay attacks on TLS 1.3 0-RTT early data"** (exact identifier). BM25 0.82, E5 0.18. E5 finds generic replay attacks (sharded ledgers, spacecraft) and misses "0-RTT". *Exact strings favour BM25.*
2. **Q48 "programs that lock a victim's files and demand payment to unlock them"** (paraphrase). BM25 0.18, E5 0.82. BM25 matches "payment" and "lock" (a payment pipeline, time-lock puzzles); E5 finds ransomware papers. *Meaning without shared words favours E5.*
3. **Q29 "anonymous communication systems that are not based on Tor"** (negation). BM25 0.45, E5 0.79. Many of BM25's results are Tor papers, because "not" is a stopword and "Tor" is a strong term.
4. **Q38 "membership inference attacks on large language models published since 2023"**. BM25 0.63, E5 0.85, BM25+E5 0.95. *Fusion beats both* because they find different relevant papers.
5. **Q33 "ransomware detection published before 2018"**. Every system returns 10 of 10 papers from 2018 or later. *No system understands date constraints*; this is what stretch goal S2 (date filter) addresses.
6. **A query typed live**, for example "detecting deepfake audio". Point out the query times: BM25 about 1–2 ms, E5 about 10–20 ms.

## Likely questions, with honest answers
- **Is the project finished?** The core is: all five research questions are answered on frozen, double-judged qrels. Remaining: round-2 judging of 272 new query–document pairs, then evaluating stretch goals S1–S4 and finishing RQ5's stemming question on the extended qrels.
- **Why not fine-tune E5?** The question was whether off-the-shelf dense models beat BM25 on technical text. With fine-tuning it would become a different comparison, and our 50 queries are too few to train on.
- **How reliable are your judgments?** Every pair was judged by two members: weighted κ = 0.76. The 325 conflicts were resolved in a team discussion; there was no independent adjudicator, which we disclose. The SPECTER2 results hold under every possible adjudication; BM25+E5 > BM25 does not (significant in 7% of random adjudications).
- **Why is SPECTER2 worst?** It is trained on citation links between papers, not on short search queries, so the query side is weak. This is our interpretation, not tested.
- **Your BM25: is it correct?** It is within 0.0009 nDCG@10 of Lucene/Pyserini BM25 on BEIR SciFact, and our metrics match `trec_eval`.

## Regenerate
```bash
python scripts/make_results_explorer.py   # deliverables/demo/results_explorer.html
python notebooks/make_demo_notebook.py    # notebooks/kaggle_demo.ipynb
```
