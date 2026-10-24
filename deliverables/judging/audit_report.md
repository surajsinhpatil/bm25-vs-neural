# Judgment audit

Pool `e2d5915c1130cb3c` (1339 query-document pairs, 722 phase 1, 50 queries, 2 annotators per query). Files audited: 4.

## Per file

| File | Annotator | Exported (UTC) | Records | Expected | Missing | Unexpected | Duplicates | Null grades | Invalid grades | Practice | Queries | Grade 0/1/2/3 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| judgments_Saksham_main.json | Saksham | 2026-10-21T10:15:41.000Z | 697 | 697 | 0 | 0 | 0 | 0 | 0 | 0 | 25/25 | 159/211/73/254 |
| judgments_Suraj_main.json | Suraj | 2026-10-21T11:53:14.898Z | 672 | 672 | 0 | 0 | 0 | 0 | 0 | 0 | 25/25 | 199/287/57/129 |
| judgments_Swayam_main.json | Swayam | 2026-10-21T14:24:27.979Z | 635 | 635 | 0 | 0 | 0 | 0 | 0 | 0 | 25/25 | 90/210/88/247 |
| judgments_Tejas_main.json | Tejas | 2026-10-21T11:04:14.890Z | 674 | 674 | 0 | 0 | 0 | 0 | 0 | 0 | 25/25 | 113/271/38/252 |

SHA-256 of each export:

- `judgments_Saksham_main.json`: `46af05bacba987e4f17621337eaf4728889615fa5715fbfbb3e59b447a063065`
- `judgments_Suraj_main.json`: `cbb545f36a47445b99c36fda23ae3dd7193f090109862d7ca494efc182319e37`
- `judgments_Swayam_main.json`: `b29a15253e11d586bd2bdb90c2e5275492a057982dbac42fa8dc24b8861accf8`
- `judgments_Tejas_main.json`: `415cb4850a9103aa0c2404cc1ba7dc1d7a1b8e998b3c612f7244a1b06e117ee0`

## Across files

- Records in all files: 2678
- Unique (query, document) pairs judged: 1339 of 1339 pool pairs
- Pairs with two judgments: 1339; with one: 0; with more than two: 0; with none: 0
- Agreeing pairs: 1014; conflicting pairs: 325
- Grade gap distribution (|g1-g2|: count): {'0': 1014, '1': 266, '2': 38, '3': 21}; 0-vs-3 conflicts: 21
- Disagreements on binary relevance (grade >= 2): 134
- Weighted Cohen's kappa: linear 0.760, quadratic 0.829; unweighted 0.656; binary (>=2) 0.795; exact agreement 0.757
- Method: Cohen's kappa over all double-judged pairs, annotators ordered alphabetically within each pair; weights: linear |i-j|/3, quadratic ((i-j)/3)^2 on the 0-3 scale. Only pairs graded by both assigned annotators are used; no missing rating is counted as 0.

## Per annotator pair

| Pair | Shared pairs | Queries | κ linear | κ quadratic | Exact | Binary agreement | Mean grade (first, second) |
|---|---|---|---|---|---|---|---|
| Saksham-Suraj | 228 | 8 | 0.694 | 0.697 | 0.785 | 0.890 | 1.01, 1.00 |
| Saksham-Swayam | 224 | 9 | 0.807 | 0.878 | 0.795 | 0.942 | 1.88, 1.97 |
| Saksham-Tejas | 245 | 8 | 0.831 | 0.906 | 0.808 | 0.927 | 1.91, 1.93 |
| Suraj-Swayam | 213 | 8 | 0.764 | 0.856 | 0.756 | 0.911 | 1.47, 1.52 |
| Suraj-Tejas | 231 | 9 | 0.684 | 0.760 | 0.745 | 0.896 | 1.07, 1.07 |
| Swayam-Tejas | 198 | 8 | 0.593 | 0.662 | 0.636 | 0.823 | 1.83, 1.94 |

## Diagnostics (for the team, not evidence of a problem by themselves)

- Saksham: longest run of identical consecutive grades 13; queries (≥5 docs) where every document got one grade: 21:1
- Suraj: longest run of identical consecutive grades 17; queries (≥5 docs) where every document got one grade: none
- Swayam: longest run of identical consecutive grades 11; queries (≥5 docs) where every document got one grade: none
- Tejas: longest run of identical consecutive grades 23; queries (≥5 docs) where every document got one grade: none

Queries with the lowest exact agreement:

| Query | Category | Pairs | Exact | Gaps ≥ 2 | Binary disagreements |
|---|---|---|---|---|---|
| 17 | homonym | 19 | 0.42 | 4 | 4 |
| 15 | homonym | 21 | 0.43 | 3 | 6 |
| 32 | time | 23 | 0.48 | 7 | 7 |
| 2 | identifier | 23 | 0.48 | 0 | 8 |
| 40 | time | 26 | 0.54 | 6 | 8 |
| 23 | negation | 27 | 0.59 | 1 | 4 |
| 5 | identifier | 28 | 0.61 | 6 | 6 |
| 39 | time | 18 | 0.61 | 1 | 1 |
| 13 | homonym | 29 | 0.62 | 1 | 3 |
| 10 | identifier | 29 | 0.62 | 0 | 0 |

## Problems

- none found
