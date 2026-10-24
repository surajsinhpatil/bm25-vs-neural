# Efficiency (measured)

| System | Index build (s) | Index size (MB) | Query mean (ms) | Query p95 (ms) | Hardware |
|---|---|---|---|---|---|
| BM25 | 20.3 | 29.3 | 1.6 | 1.7 | cpu |
| E5 | 174.6 | 116.0 | 17.3 | 18.2 | Tesla T4 |
| SPECTER2 | 182.6 | 116.0 | 30.0 | 36.6 | Tesla T4 |
| BM25+E5 | 194.9 | 145.4 | 19.3 | – |  |
| BM25+SPECTER2 | 202.8 | 145.4 | 32.0 | – |  |
| Cross-encoder re-rank (S1, top-100 of BM25+E5) | – | – | 455.8 | 487.8 | cuda |

## How these were measured

- All numbers come from the logs the run scripts wrote during the Kaggle run of 19 Oct 2026 (`runs/*.run.eff.json`); nothing is estimated.
- Corpus: 39,613 cs.CR abstracts; 50 test queries, each timed separately with `time.perf_counter()`.
- **BM25**: index build = tokenising the corpus and building the sparse term-document matrix, one CPU process (the Kaggle CPU model was not logged). Size = postings (data, indices, pointers) + document lengths + vocabulary in memory. Query time = tokenising the query + sparse matrix-vector product + top-1000.
- **E5 / SPECTER2**: index build = encoding all abstracts on one Tesla T4 GPU in fp16, length-sorted batches. Size = 39,613 × 768 float32 vectors. Query time = encoding the query alone on the GPU (batch size 1, after one warm-up) + exact cosine search over all vectors on the CPU + top-1000; the search part alone was 5.9 ms (E5) and 7.4 ms (SPECTER2).
- **Hybrids**: the logs hold the components' mean latencies plus the measured RRF time (about 0.42 ms); hybrid time = BM25 + dense + fusion, i.e. the components run one after the other. Running them in parallel would cost about the slower component. No p95 for hybrids.
- **Cross-encoder (stretch S1)**: re-ranking time only (100 query–document pairs on the T4); add the BM25+E5 time for the full pipeline.
- Not measured: CPU-only dense encoding, memory of a production ANN index, or throughput under load.
