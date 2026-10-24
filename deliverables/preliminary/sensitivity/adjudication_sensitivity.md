# Sensitivity of the results to adjudication

325 conflicts over 50 queries; all 40,269 per-query combinations of the two submitted grades were enumerated. Bounds are exact over every adjudication that picks one of the two submitted grades for each conflict.

## Exact bounds on mean nDCG@10

| System | Min | Max |
|---|---|---|
| BM25 | 0.614 | 0.765 |
| E5 | 0.639 | 0.774 |
| SPECTER2 | 0.474 | 0.656 |
| BM25+E5 | 0.657 | 0.798 |
| BM25+SPECTER2 | 0.598 | 0.760 |

## Exact bounds on mean differences, worst-case tests, random adjudications

| Pair (A vs B) | Min A−B | Max A−B | Worst-case p (Holm, 10 pairs) | Significant in % of random adjudications |
|---|---|---|---|---|
| BM25 vs E5 | -0.099 | +0.068 | sign can flip | 0% |
| BM25 vs SPECTER2 | +0.001 | +0.250 | 1.0000 (n.s.) | 99% |
| BM25 vs BM25+E5 | -0.092 | +0.015 | sign can flip | 7% |
| BM25 vs BM25+SPECTER2 | -0.064 | +0.088 | sign can flip | 0% |
| E5 vs SPECTER2 | +0.020 | +0.262 | 1.0000 (n.s.) | 100% |
| E5 vs BM25+E5 | -0.080 | +0.035 | sign can flip | 0% |
| E5 vs BM25+SPECTER2 | -0.067 | +0.118 | sign can flip | 0% |
| SPECTER2 vs BM25+E5 | -0.283 | -0.046 | 1.0000 (n.s.) | 100% |
| SPECTER2 vs BM25+SPECTER2 | -0.202 | -0.032 | 1.0000 (n.s.) | 100% |
| BM25+E5 vs BM25+SPECTER2 | -0.021 | +0.122 | sign can flip | 16% |

Share of random adjudications in which each system has the highest mean nDCG@10: BM25 0%, E5 0%, SPECTER2 0%, BM25+E5 100%, BM25+SPECTER2 0%

Most frequent system orders: bm25+e5 > e5 > bm25 > bm25+specter2 > specter2 (93%); bm25+e5 > e5 > bm25+specter2 > bm25 > specter2 (7%); bm25+e5 > bm25 > e5 > bm25+specter2 > specter2 (0%)
