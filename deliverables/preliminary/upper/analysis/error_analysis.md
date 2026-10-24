# Error analysis

Metric values use `deliverables/preliminary/qrels/qrels.preliminary-upper.txt` (PRELIMINARY (unresolved conflicts at the upper grade).). Grades in brackets are the two annotators' original grades: `3` = both gave 3, `1|3` = they disagreed. Paper titles are not shown because the paper text was not available when this was generated (re-run with `--pages judging/round1`).

## Where BM25 and E5 differ most

BM25 better on 21 queries, E5 better on 25, ties 4.

### E5 much better than BM25

**Query 48 (paraphrase): "programs that lock a victim's files and demand payment to unlock them"**: nDCG@10 BM25 0.183, E5 0.824, BM25+E5 0.675

- BM25 top 5:
  1. `2508.21075` [0]
  2. `2308.01280` [0]
  3. `2109.12162` [3]
  4. `1906.03043` [0]
  5. `2305.00107` [0]
- E5 top 5:
  1. `1911.08364` [3]
  2. `2103.11014` [3]
  3. `2504.11744` [2]
  4. `2410.21979` [3]
  5. `2003.04426` [3]

**Query 42 (paraphrase): "telling whether a particular person's record was used to train a model"**: nDCG@10 BM25 0.367, E5 0.929, BM25+E5 0.886

- BM25 top 5:
  1. `2106.08393` [0]
  2. `2501.11120` [0]
  3. `2006.06296` [0]
  4. `2112.02230` [3]
  5. `2103.11030` [0]
- E5 top 5:
  1. `2407.15100` [3]
  2. `2203.02077` [3]
  3. `2310.16789` [3]
  4. `2209.07341` [3]
  5. `2001.04011` [3]

**Query 29 (negation): "anonymous communication systems that are not based on Tor"**: nDCG@10 BM25 0.429, E5 0.826, BM25+E5 0.507

- BM25 top 5:
  1. `2105.05943` [1]
  2. `2208.11149` [1]
  3. `1805.01977` [1]
  4. `1904.01240` [1]
  5. `2307.02429` [1]
- E5 top 5:
  1. `2405.06126` [1]
  2. `1610.06549` [2|3]
  3. `2111.05523` [1|2]
  4. `1712.07601` [2]
  5. `1812.07927` [1|2]

**Query 27 (negation): "smart contract vulnerability detection without symbolic execution"**: nDCG@10 BM25 0.496, E5 0.781, BM25+E5 0.697

- BM25 top 5:
  1. `1911.00570` [1]
  2. `2312.15392` [1]
  3. `2007.01029` [1|3]
  4. `1811.06632` [3]
  5. `1907.03868` [1]
- E5 top 5:
  1. `2312.15392` [1]
  2. `1811.06632` [3]
  3. `2106.13422` [2|3]
  4. `2301.08824` [2|3]
  5. `2410.20712` [3]

### BM25 much better than E5

**Query 8 (identifier): "replay attacks on TLS 1.3 0-RTT early data"**: nDCG@10 BM25 0.775, E5 0.211, BM25+E5 0.550

- BM25 top 5:
  1. `1907.12762` [0|1]
  2. `2306.11643` [1|2]
  3. `2207.01841` [1]
  4. `2106.08759` [1]
  5. `1905.03518` [1]
- E5 top 5:
  1. `2004.02257` [0]
  2. `1901.11218` [0]
  3. `2506.17446` [0]
  4. `2309.13579` [0|1]
  5. `1602.02148` [0]

**Query 10 (identifier): "nonce reuse forgery attacks on AES-GCM"**: nDCG@10 BM25 1.000, E5 0.558, BM25+E5 0.786

- BM25 top 5:
  1. `2309.07782` [0|1]
  2. `2111.05117` [0|1]
  3. `2005.13864` [1]
  4. `2309.14368` [0|1]
  5. `2504.07265` [0|1]
- E5 top 5:
  1. `2309.14368` [0|1]
  2. `1904.07550` [0]
  3. `2111.05117` [0|1]
  4. `2412.03283` [0]
  5. `1602.02148` [0|1]

**Query 41 (paraphrase): "inferring which websites a user visits from encrypted traffic patterns"**: nDCG@10 BM25 0.927, E5 0.629, BM25+E5 0.915

- BM25 top 5:
  1. `1907.01317` [1|3]
  2. `2409.04341` [3]
  3. `2512.17667` [3]
  4. `2509.12462` [3]
  5. `2510.14283` [3]
- E5 top 5:
  1. `1708.06376` [3]
  2. `2006.12352` [1]
  3. `1807.02719` [2|3]
  4. `2302.13763` [3]
  5. `1603.04865` [1]

**Query 12 (homonym): "padding oracle attacks on CBC mode encryption"**: nDCG@10 BM25 0.643, E5 0.397, BM25+E5 0.551

- BM25 top 5:
  1. `1601.08139` [0|1]
  2. `1706.08099` [0|1]
  3. `1608.05838` [0|1]
  4. `2407.09490` [1]
  5. `1708.03243` [0|1]
- E5 top 5:
  1. `2311.08027` [0]
  2. `1605.02950` [0|1]
  3. `1608.05838` [0|1]
  4. `1706.08099` [0|1]
  5. `1807.05782` [1]

## Share of the top 10 graded 1 (on topic, but does not answer the query or breaks a condition)

| System | identifier | homonym | negation | time | paraphrase |
|---|---|---|---|---|---|
| BM25 | 0.39 | 0.12 | 0.76 | 0.52 | 0.12 |
| E5 | 0.30 | 0.08 | 0.59 | 0.41 | 0.17 |
| SPECTER2 | 0.35 | 0.24 | 0.61 | 0.39 | 0.31 |
| BM25+E5 | 0.38 | 0.11 | 0.68 | 0.44 | 0.08 |
| BM25+SPECTER2 | 0.43 | 0.14 | 0.73 | 0.43 | 0.16 |

On negation and time queries a grade of 1 is mostly a document that breaks the exclusion or the date limit, so a high share means the system ignores the condition.

## Complementarity of BM25 and E5

Relevant documents (grade ≥ 2) in the top 10: found by both 115, only by BM25 146, only by E5 174.

| Category | Only BM25 | Only E5 | Both |
|---|---|---|---|
| identifier | 18 | 17 | 29 |
| homonym | 38 | 38 | 44 |
| negation | 18 | 35 | 6 |
| time | 23 | 31 | 23 |
| paraphrase | 49 | 53 | 13 |

Many relevant documents are found by only one of the two systems, which is why rank fusion can help even when neither component is better overall.

## Queries where every system fails (best nDCG@10 < 0.3)

- none
