# Presentation outline (10–15 min + demo)

Numbers are currently **preliminary** ranges (unresolved conflicts at the lower grade – at the
higher grade). Replace them with the final values after `final_pipeline.sh final`.

1. **Motivation (1 min).** Security text is full of exact strings (CVE-2021-44228, TLS 1.3),
   homonyms (oracle, poisoning) and conditions ("not based on Tor", "after 2018"). Are general
   dense retrievers really better than BM25 here?
2. **Research questions (0.5 min).** RQ1 dense vs BM25; RQ2 by query type; RQ3 SPECTER2 vs E5;
   RQ4 hybrids; RQ5 BM25 sensitivity.
3. **Data (1 min).** 39,613 cs.CR abstracts (2016–2025, frozen with SHA-256). 50 queries, 10 in
   each of five categories, each with written relevance criteria. Show one example per category.
4. **Systems (1.5 min).** Identifier-aware BM25 (our own implementation, matches Lucene within
   0.001 nDCG@10 on SciFact). E5-base-v2 and SPECTER2 without fine-tuning, exact search.
   RRF k=60. Nothing tuned on our queries.
5. **Evaluation protocol (2 min).** Pool = top 10 of 5 runs (1,339 pairs). Blind double judging
   (2,678 judgments, every pair judged twice). Weighted κ = 0.76. 325 conflicts adjudicated by the team (pending as of 24 Oct).
   Metrics validated against trec_eval. Randomisation tests with Holm correction.
   *Demo: the judging page (static HTML, works offline).*
6. **Main result (2 min).** Table of the 5 systems. BM25+E5 highest (0.70–0.77 nDCG@10) but not
   significantly above BM25 or E5. E5 ≈ BM25 (RQ1: no). SPECTER2 significantly worst (RQ3: no; significant in 99–100% of random adjudications, to be confirmed on the final qrels).
7. **By query type (2 min).** Bar chart with CIs. BM25 leads on identifiers, E5 on paraphrase and
   negation, the hybrid on time and paraphrase. Exploratory: 10 queries per category.
8. **Why: error analysis (2 min).**
   - "Anonymous communication *not* based on Tor": 9 of BM25's top 10 are graded 1 by both annotators, the grade the criteria give to papers about Tor itself (show the titles once the paper text is in).
   - "Programs that lock a victim's files and demand payment": BM25 fails, E5 finds ransomware papers.
   - Every system ignores date limits (30–38% of the top 10 breaks them); the date filter (S2) fixes this.
   - BM25 and E5 find largely different relevant documents, which is why fusion works.
9. **Cost (1 min).** BM25 1.6 ms/query, 29 MB index vs dense 17–30 ms, 116 MB, 3 min of GPU to index.
   The hybrid costs about 12× BM25's query time for a non-significant gain.
10. **Limitations (1 min).** 50 queries; pool limited to five systems; authors wrote and judged the
    queries; possible pre-training exposure of the dense models; one query with no relevant document.
11. **Conclusions (1 min).** On technical security text, use BM25 as a serious baseline. Choose the
    method by query type. Handle conditions (negation, dates) explicitly rather than hoping a model learns them.
12. **Backup slides.** SciFact validation, agreement per annotator pair, significance table, RQ5 sweep
    (after the final run).
