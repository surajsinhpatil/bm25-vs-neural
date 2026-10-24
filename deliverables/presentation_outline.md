# Presentation outline (10–15 min + demo)

All numbers are final (frozen, adjudicated qrels; 24 Oct 2026).

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
   (2,678 judgments, every pair judged twice). Weighted κ = 0.76. 325 conflicts resolved in team discussion (no independent adjudicator; disclosed).
   Metrics validated against trec_eval. Randomisation tests with Holm correction.
   *Demo: the judging page (static HTML, works offline).*
6. **Main result (2 min).** nDCG@10: BM25+E5 0.744, E5 0.713, BM25 0.689, BM25+SPECTER2 0.681,
   SPECTER2 0.543. E5 ≈ BM25 (RQ1: no, p_Holm 0.93). SPECTER2 significantly worst (RQ3: no).
   BM25+E5 significantly beats BM25 (+0.055, p_Holm 0.023) but not E5 (RQ4: not both components);
   honest caveat: that margin is significant in only 7% of random adjudications.
7. **By query type (2 min).** Bar chart with CIs. BM25 leads on identifiers (0.80 vs 0.66), E5 on
   negation (0.68 vs 0.56) and paraphrase (0.69 vs 0.59), the hybrid on time and paraphrase.
   Exploratory: 10 queries per category.
8. **Why: error analysis (2 min).**
   - "Anonymous communication *not* based on Tor": 7 of BM25's top 10 titles name Tor; E5 finds DC-nets, Atom, Pirates.
   - "Programs that lock a victim's files and demand payment": BM25 0.18 ("Scalable Time-Lock Puzzle"), E5 0.82 (ransomware papers).
   - "Replay attacks on TLS 1.3 0-RTT": E5 0.18 (replay attacks in space launch, sharded ledgers), BM25 0.82.
   - Every system ignores date limits (30–38% of the top 10 breaks them); the date filter (S2) fixes this.
   - BM25 and E5 find largely different relevant documents, which is why fusion works.
9. **Cost (1 min).** BM25 1.6 ms/query, 29 MB index vs dense 17–30 ms, 116 MB, 3 min of GPU to index.
   The hybrid costs about 12× BM25's query time (+0.055 nDCG@10, adjudication-sensitive), and only
   about 1.1× E5's time, over which it gains a non-significant +0.031.
10. **Limitations (1 min).** 50 queries; pool limited to five systems; authors wrote and judged the
    queries; adjudication without an independent adjudicator (27 decisions from titles); possible pre-training exposure of the dense models; one query with no relevant document.
11. **Conclusions (1 min).** On technical security text, use BM25 as a serious baseline. Choose the
    method by query type. Handle conditions (negation, dates) explicitly rather than hoping a model learns them.
12. **Backup slides.** SciFact validation, agreement per annotator pair, significance table, RQ5
    (exploratory):
    - k1/b heatmaps (nDCG@10, condensed, Hole@10): flat near the default; cross-validated tuning gave no gain.
    - Identifier handling makes no measurable difference.
    - Stemming is inconclusive because of pool bias (141 unjudged pairs would settle it).
