# Error analysis

Metric values use `deliverables/preliminary/qrels/qrels.preliminary-lower.txt` (PRELIMINARY (unresolved conflicts at the lower grade).). Grades in brackets are the two annotators' original grades: `3` = both gave 3, `1|3` = they disagreed. Paper titles are not shown because the paper text was not available when this was generated (re-run with `--pages judging/round1`).

## Where BM25 and E5 differ most

BM25 better on 25 queries, E5 better on 24, ties 1.

### E5 much better than BM25

**Query 48 (paraphrase): "programs that lock a victim's files and demand payment to unlock them"**: nDCG@10 BM25 0.183, E5 0.754, BM25+E5 0.580

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

**Query 42 (paraphrase): "telling whether a particular person's record was used to train a model"**: nDCG@10 BM25 0.367, E5 0.882, BM25+E5 0.835

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

**Query 29 (negation): "anonymous communication systems that are not based on Tor"**: nDCG@10 BM25 0.473, E5 0.762, BM25+E5 0.521

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

**Query 25 (negation): "phishing website detection without URL-based features"**: nDCG@10 BM25 0.423, E5 0.704, BM25+E5 0.485

- BM25 top 5:
  1. `2411.09813` [1|2]
  2. `2011.04412` [1]
  3. `2205.05121` [1]
  4. `2404.09802` [1]
  5. `2508.09765` [1]
- E5 top 5:
  1. `2207.10801` [3]
  2. `2205.05121` [1]
  3. `2209.01454` [1]
  4. `2112.02226` [1]
  5. `2408.01667` [2]

### BM25 much better than E5

**Query 8 (identifier): "replay attacks on TLS 1.3 0-RTT early data"**: nDCG@10 BM25 0.780, E5 0.215, BM25+E5 0.574

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

**Query 31 (time): "attacks on TLS 1.3 published after its 2018 standardisation"**: nDCG@10 BM25 1.000, E5 0.455, BM25+E5 0.870

- BM25 top 5:
  1. `1904.02148` [1]
  2. `1907.12762` [1]
  3. `2106.08759` [1]
  4. `2207.01841` [1|2]
  5. `2011.12035` [1]
- E5 top 5:
  1. `2208.06722` [0|1]
  2. `1904.02148` [1]
  3. `1907.12762` [1]
  4. `2208.13035` [0]
  5. `2312.00021` [0]

**Query 10 (identifier): "nonce reuse forgery attacks on AES-GCM"**: nDCG@10 BM25 0.379, E5 0.000, BM25+E5 0.098

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

**Query 5 (identifier): "WannaCry ransomware spreading through the EternalBlue SMBv1 exploit (MS17-010)"**: nDCG@10 BM25 0.467, E5 0.199, BM25+E5 0.453

- BM25 top 5:
  1. `2401.14979` [0|3]
  2. `2112.14773` [0|3]
  3. `1709.08753` [0|3]
  4. `2106.05434` [1|3]
  5. `2504.07868` [1]
- E5 top 5:
  1. `2112.14773` [0|3]
  2. `1709.08753` [0|3]
  3. `2401.14979` [0|3]
  4. `2403.07540` [0|1]
  5. `1905.05726` [0]

## Share of the top 10 graded 1 (on topic, but does not answer the query or breaks a condition)

| System | identifier | homonym | negation | time | paraphrase |
|---|---|---|---|---|---|
| BM25 | 0.36 | 0.10 | 0.81 | 0.58 | 0.16 |
| E5 | 0.32 | 0.07 | 0.63 | 0.50 | 0.20 |
| SPECTER2 | 0.27 | 0.10 | 0.74 | 0.43 | 0.26 |
| BM25+E5 | 0.36 | 0.08 | 0.74 | 0.53 | 0.17 |
| BM25+SPECTER2 | 0.35 | 0.08 | 0.78 | 0.49 | 0.16 |

On negation and time queries a grade of 1 is mostly a document that breaks the exclusion or the date limit, so a high share means the system ignores the condition.

## Complementarity of BM25 and E5

Relevant documents (grade ≥ 2) in the top 10: found by both 96, only by BM25 116, only by E5 140.

| Category | Only BM25 | Only E5 | Both |
|---|---|---|---|
| identifier | 15 | 10 | 23 |
| homonym | 32 | 34 | 41 |
| negation | 12 | 29 | 5 |
| time | 15 | 22 | 16 |
| paraphrase | 42 | 45 | 11 |

Many relevant documents are found by only one of the two systems, which is why rank fusion can help even when neither component is better overall.

## Queries where every system fails (best nDCG@10 < 0.3)

- Query 12 (homonym): "padding oracle attacks on CBC mode encryption". Best system 0.292; documents with grade ≥ 2 in the pool: 1
- Query 45 (paraphrase): "recovering secret keys by measuring how long cryptographic operations take". Best system 0.206; documents with grade ≥ 2 in the pool: 2
