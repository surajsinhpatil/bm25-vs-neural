# Deliverables: status and index

Every result here carries one label:
- **validated**: checked against an independent reference or complete data
- **preliminary**: depends on the 325 judgment conflicts that are not adjudicated yet
- **exploratory**: too few queries for a conclusion
- **blocked**: cannot be produced yet, with the reason

## Current state (24 Oct 2026)

| Item | Status | Where |
|---|---|---|
| Judgment audit: 4 files, 2,678 judgments, every one of the 1,339 pool pairs double-judged, no integrity problems, record order matches the generated pages | validated | `judging/audit_report.md`, `judging/audit.json` |
| Inter-annotator agreement: linear κ 0.760, quadratic κ 0.829 | validated | `judging/agreement_report.md` |
| Adjudication sheet: 325 conflicts sorted by priority (21 are 0 vs 3; 38 have a gap of 2; 75 are 1 vs 2; 191 differ by one grade on the same side) | ready for the team | `judging/adjudication_sheet.csv` (fill `final`), `.html` for reading |
| Final qrels + checksum + provenance | **blocked**: needs the team's adjudication | will be `../data/qrels/` |
| Metric code = trec_eval on the real runs and qrels (max difference 3e-16) | validated | `preliminary/*/metric_validation.json` |
| Overall results, 5 systems | preliminary (lower/upper fallback runs) | `preliminary/{lower,upper}/results/summary.csv` |
| Significance tests (paired randomisation, 100k permutations, Holm over 10 pairs, paired bootstrap CI of each difference, win/tie/loss) | preliminary | `preliminary/*/results/significance.csv` |
| Sensitivity to adjudication: exact bounds over all adjudications, adversarial worst case, 500 random adjudications | validated (as a sensitivity analysis) | `preliminary/sensitivity/adjudication_sensitivity.md` |
| Per-category results with 95% bootstrap CIs | preliminary + exploratory | `preliminary/*/results/per_category.csv`, `figures/` |
| Error analysis (examples show both annotators' original grades) | preliminary metrics; examples are grade-exact | `preliminary/*/analysis/error_analysis.md` |
| Efficiency (from run logs, nothing estimated) | validated as measured | `efficiency/efficiency.md` |
| BM25 vs Lucene and metric checks on SciFact; SciFact comparison of the 5 systems (implementation check only, not cs.CR) | validated | `validation/` |
| BM25 k1/b sweep with 5-fold CV, tokenisation ablation (RQ5) | **blocked**: needs final qrels + corpus (Kaggle) | commands in `../scripts/final_pipeline.sh` |
| Paper titles/abstracts in the adjudication sheet and error analysis | **blocked**: the paper text is not in this workspace | re-run with `PAGES=judging/round1` |
| Final report | preliminary | `final_report_PRELIMINARY.pdf` (`../report/final_report.tex`) |
| Presentation outline | done | `presentation_outline.md` |

## What "lower" and "upper" mean, and what they do not
Until adjudication, the fallback runs set every unresolved conflict to the lower of the two grades
(`lower`) or to the higher (`upper`). These rules are used only for preliminary numbers: they are
never written to `data/qrels/` and never frozen. **They are not bounds.** nDCG is not monotone in the
grades: raising the grade of a document a system did not retrieve lowers that system's score. A mixed
adjudication can therefore fall outside the lower–upper range.

The real bounds are in `preliminary/sensitivity/adjudication_sensitivity.md`. For each query, every
way of resolving its conflicts to one of the two submitted grades is enumerated (40,269 combinations
in total), which gives exact ranges of each system's mean nDCG@10 and of every pairwise difference.
The file also reports the test on the most adversarial adjudication of each comparison, and how
often each comparison is significant across 500 random adjudications.
(If the team gives a grade outside the two submitted ones, re-run the final pipeline; it always
recomputes from scratch.)

## After adjudication
`final_pipeline.sh final` regenerates every table and figure. The **prose** of the report's results
section (`report/final_report.tex`, Sections 5.2–5.4, Limitations, Conclusions) was written for the
preliminary numbers. Re-read it against the final tables and remove the sensitivity paragraph before
submitting. Each claim in it names the table it comes from.

## Reproduce
```bash
pip install -e . pytrec_eval-terrier scikit-learn pytest      # + playwright for the browser tests
bash scripts/final_pipeline.sh preliminary                      # everything above, about 30 s
bash scripts/final_pipeline.sh final <adjudicated_sheet.csv>    # after adjudication: freeze + final results
```
Environment used for these outputs: Python 3.13.16, numpy 2.5.3, scipy 1.18.1, nltk 3.10.3,
pandas 3.0.5, matplotlib 3.11.2, pytrec_eval-terrier 0.5.10, scikit-learn 1.9.1, pytest 9.1.1.
The runs themselves were produced on Kaggle on 19 Oct 2026 (Tesla T4 for E5/SPECTER2; BM25 on CPU),
with torch / transformers 4.57 / adapters 1.3; see `runs/*.eff.json`.
