# Progress report (70–80% milestone), Group 10

- `10_BM25NeuralRetrieval.pdf`: the submission, 4 pages, A4.
- `10_BM25NeuralRetrieval.tex`: its editable source, self-contained (the architecture diagram is TikZ). Build with `pdflatex 10_BM25NeuralRetrieval.tex`, run twice.

This is not the final report. That is `report/final_report.pdf`, unchanged by this folder.

## Where the numbers come from (all checked against these files on 25 Oct 2026)
| Content | Source |
|---|---|
| Table 2, effectiveness | `deliverables/final/results/summary.csv` (frozen qrels, SHA-256 `8cc5fac5…`) |
| Table 2, efficiency | `runs/*.run.eff.json`, `deliverables/efficiency/efficiency.md` |
| Table 3 | `deliverables/final/results/significance.csv` |
| Table 4 | `deliverables/final/results/per_category.csv` |
| Agreement, judging counts | `deliverables/judging/audit.json`, `judging/exports/*.json` |
| Adjudication | `judging/adjudication/ADJUDICATION_NOTE.txt` |
| Adjudication sensitivity (7%) | `deliverables/preliminary/sensitivity/` |
| Corpus | `deliverables/rq5/kaggle_run/cscr.jsonl.manifest.json`, `data/corpus/EXPECTED.json` |
| RQ5 | `deliverables/rq5/sweep/bm25_sweep.json`, `deliverables/rq5/tokenisation/tokenizer_ablation.json` |
| Remaining-work sizes (272 pairs on 48 queries; S1 142, S2 17, RQ5 141) | top 10 of `runs/ce.run`, `runs/bm25+e5+time.run` and `deliverables/rq5/tokenisation/runs/*.run`, compared with `data/qrels/qrels.txt` |

## To confirm before submitting
The contribution matrix (Table 5) and the work-package leads (Table 6) show the **proposed** allocation and are marked "to be confirmed". Only the judgment counts are recorded in the repository. Once all four members agree, edit both tables and remove the "(proposed; to be confirmed)" wording.
