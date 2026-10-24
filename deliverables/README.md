# Deliverables: status and index

Every result here carries one label:
- **validated**: checked against an independent reference or complete data
- **preliminary**: depends on the 325 judgment conflicts that are not adjudicated yet
- **exploratory**: too few queries for a conclusion
- **blocked**: cannot be produced yet, with the reason

## Current state (24 Oct 2026, qrels frozen)

| Item | Status | Where |
|---|---|---|
| Judgment audit: 4 files, 2,678 judgments, all 1,339 pool pairs double-judged, no integrity problems | validated | `judging/audit_report.md` |
| Inter-annotator agreement: linear κ 0.760, quadratic κ 0.829 | validated | `judging/agreement_report.md` |
| Adjudication: 325 conflicts decided in team discussion, recorded by Suraj; 27 rows decided from titles or by "lower when unsure"; 1 rationale copied by mistake (grade kept) | done, disclosed | `../judging/adjudication/` (sheet + `ADJUDICATION_NOTE.txt`), `judging/recheck_28.*` |
| Final qrels, SHA-256 `8cc5fac5…`, provenance (export and sheet hashes, git commit, κ, note) | validated (frozen) | `../data/qrels/` |
| Metric code = trec_eval on the final qrels (max difference 3e-16) | validated | `final/metric_validation.json` |
| Overall results, 5 systems, with bootstrap CIs | validated | `final/results/summary.csv`, `final/tables/` |
| Significance (randomisation, 100k permutations, Holm over 10 pairs, CI of each difference, W/T/L) | validated | `final/results/significance.csv` |
| Sensitivity of each comparison to adjudication (exact bounds, worst case, 500 random adjudications) | validated as a sensitivity analysis | `preliminary/sensitivity/` |
| Per-category results with 95% CIs | exploratory (10 queries each) | `final/results/per_category.csv`, `final/figures/` |
| Error analysis with titles and both annotators' original grades | validated (examples), metrics final | `final/analysis/error_analysis.md` |
| Efficiency from run logs | validated as measured | `efficiency/efficiency.md` |
| SciFact implementation checks (not cs.CR) | validated | `validation/` |
| RQ5: BM25 k1/b sweep (5-fold CV) and tokenisation ablation | **blocked**: needs the full corpus, run on Kaggle | commands printed by `final_pipeline.sh final` |
| Final report | final except RQ5, GitHub URL and contribution matrix | `final_report.pdf` |
| Presentation outline | updated with the final numbers | `presentation_outline.md` |
| Preliminary (pre-adjudication) results | superseded, kept for the record | `preliminary/` |

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
Done on 24 Oct 2026: `final_pipeline.sh final judging/adjudication/adjudication_sheet_completed.csv
judging/adjudication/ADJUDICATION_NOTE.txt`. The report prose was rewritten for the final numbers and
every figure in it was checked against `final/`. Re-running the final command re-freezes the same qrels
(same checksum) with a new timestamp.

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
