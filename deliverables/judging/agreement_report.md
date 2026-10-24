# Inter-annotator agreement

## Design

- Pool: top 10 of each of the five runs for 50 queries, 1339 query–document pairs.
- Each query was judged independently by two of the four annotators; the six annotator pairs were spread evenly (8–9 queries each), so every pair contributes to the estimate.
- Annotators saw no system names or ranks; dates were shown only for time-constraint queries.
- Grades: 0 not relevant, 1 on topic but does not answer / breaks a condition, 2 relevant, 3 highly relevant.

## Method

- Cohen's kappa computed over all pairs judged by both assigned annotators (1339 pairs). Ratings that do not exist are never paired or counted as 0.
- Weighted kappa for the ordinal 0–3 scale: linear weights |i−j|/3 (primary, pre-registered) and quadratic weights ((i−j)/3)²; also unweighted kappa and kappa on binary relevance (grade ≥ 2), the level used by P@5, MRR@10 and MAP@10.
- Implementation: `irproj.stats.weighted_kappa`, checked against scikit-learn's `cohen_kappa_score` in `tests/test_core.py`.

## Results (validated)

| Measure | Value |
|---|---|
| Weighted κ, linear (primary) | 0.760 |
| Weighted κ, quadratic | 0.829 |
| Unweighted κ | 0.656 |
| κ on binary relevance (≥ 2) | 0.795 |
| Exact agreement | 0.757 (1014 of 1339) |
| Conflicts by gap (1 / 2 / 3) | 266 / 38 / 21 |
| Conflicts crossing the relevance line | 134 |

Per annotator pair:

| Pair | Shared pairs | Queries | κ linear | κ quadratic | Exact |
|---|---|---|---|---|---|
| Saksham-Suraj | 228 | 8 | 0.694 | 0.697 | 0.785 |
| Saksham-Swayam | 224 | 9 | 0.807 | 0.878 | 0.795 |
| Saksham-Tejas | 245 | 8 | 0.831 | 0.906 | 0.808 |
| Suraj-Swayam | 213 | 8 | 0.764 | 0.856 | 0.756 |
| Suraj-Tejas | 231 | 9 | 0.684 | 0.760 | 0.745 |
| Swayam-Tejas | 198 | 8 | 0.593 | 0.662 | 0.636 |

## Interpretation

- Overall linear κ = 0.76 meets the protocol's target of ≥ 0.6, so the guidelines did not need revision and no query has to be re-judged on agreement grounds.
- Pair(s) below 0.6: Swayam-Tejas. Their conflicts deserve particular care at adjudication.
- Most conflicts are one grade apart; conflicts of two or more grades and conflicts on the relevance line are the ones that change binary metrics and are adjudicated first.
