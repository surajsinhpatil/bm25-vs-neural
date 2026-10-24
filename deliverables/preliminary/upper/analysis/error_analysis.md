# Error analysis

Metric values use `deliverables/preliminary/qrels/qrels.preliminary-upper.txt` (PRELIMINARY (unresolved conflicts at the upper grade).). Grades in brackets are the two annotators' original grades: `3` = both gave 3, `1|3` = they disagreed.

## Where BM25 and E5 differ most

BM25 better on 21 queries, E5 better on 25, ties 4.

### E5 much better than BM25

**Query 48 (paraphrase): "programs that lock a victim's files and demand payment to unlock them"**: nDCG@10 BM25 0.183, E5 0.824, BM25+E5 0.675

- BM25 top 5:
  1. `2508.21075` [0] A Stream Pipeline Framework for Digital Payment Programming based on Smart Contracts
  2. `2308.01280` [0] Scalable Time-Lock Puzzle
  3. `2109.12162` [3] POSSE: Patterns of Systems During Software Encryption
  4. `1906.03043` [0] A Fuzzy-Fuzzy Vault Scheme
  5. `2305.00107` [0] Unraveling Latch Locking Using Machine Learning, Boolean Analysis, and ILP
- E5 top 5:
  1. `1911.08364` [3] Volenti non fit injuria: Ransomware and its Victims
  2. `2103.11014` [3] Fight Virus Like a Virus: A New Defense Method Against File-Encrypting Ransomware
  3. `2504.11744` [2] From Cyber Threat to Data Shield: Constructing Provably Secure File Erasure with Repurposed Ransomware Cryptog
  4. `2410.21979` [3] VaultFS: Write-once Software Support at the File System Level Against Ransomware Attacks
  5. `2003.04426` [3] Ransomware as a Service using Smart Contracts and IPFS

**Query 42 (paraphrase): "telling whether a particular person's record was used to train a model"**: nDCG@10 BM25 0.367, E5 0.929, BM25+E5 0.886

- BM25 top 5:
  1. `2106.08393` [0] Spoofing Generalization: When Can't You Trust Proprietary Models?
  2. `2501.11120` [0] Tell me about yourself: LLMs are aware of their learned behaviors
  3. `2006.06296` [0] Fingerprinting Analog IoT Sensors for Secret-Free Authentication
  4. `2112.02230` [3] SHAPr: An Efficient and Versatile Membership Privacy Risk Metric for Machine Learning
  5. `2103.11030` [0] Don't Tell Me The Cybersecurity Moon Is Shining... (Cybersecurity Show And Tell)
- E5 top 5:
  1. `2407.15100` [3] A General Framework for Data-Use Auditing of ML Models
  2. `2203.02077` [3] User-Level Membership Inference Attack against Metric Embedding Learning
  3. `2310.16789` [3] Detecting Pretraining Data from Large Language Models
  4. `2209.07341` [3] Does CLIP Know My Face?
  5. `2001.04011` [3] Membership Inference Attacks Against Object Detection Models

**Query 29 (negation): "anonymous communication systems that are not based on Tor"**: nDCG@10 BM25 0.429, E5 0.826, BM25+E5 0.507

- BM25 top 5:
  1. `2105.05943` [1] Tomen: Application of Bitcoin Transaction Based on Tor
  2. `2208.11149` [1] Analyzing Trends in Tor
  3. `1805.01977` [1] Towards Predicting Efficient and Anonymous Tor Circuits
  4. `1904.01240` [1] DNS-Morph: UDP-Based Bootstrapping Protocol For Tor
  5. `2307.02429` [1] DarkHorse: A UDP-based Framework to Improve the Latency of Tor Onion Services
- E5 top 5:
  1. `2405.06126` [1] Quantum Secure Anonymous Communication Networks
  2. `1610.06549` [2|3] Untraceable VoIP Communication based on DC-nets
  3. `2111.05523` [1|2] Anonymous communication system provides a secure environment without leaking metadata, which has many applicat
  4. `1712.07601` [2] An Analytical Perspective to Traffic Engineering in Anonymous Communication Systems
  5. `1812.07927` [1|2] Preventing Attacks on Anonymous Data Collection

**Query 27 (negation): "smart contract vulnerability detection without symbolic execution"**: nDCG@10 BM25 0.496, E5 0.781, BM25+E5 0.697

- BM25 top 5:
  1. `1911.00570` [1] MPro: Combining Static and Symbolic Analysis for Scalable Testing of Smart Contract
  2. `2312.15392` [1] Blockchain Smart Contract Threat Detection Technology Based on Symbolic Execution
  3. `2007.01029` [1|3] Hunting for Re-Entrancy Attacks in Ethereum Smart Contracts via Static Analysis
  4. `1811.06632` [3] Towards Safer Smart Contracts: A Sequence Learning Approach to Detecting Security Threats
  5. `1907.03868` [1] Annotary: A Concolic Execution System for Developing Secure Smart Contracts
- E5 top 5:
  1. `2312.15392` [1] Blockchain Smart Contract Threat Detection Technology Based on Symbolic Execution
  2. `1811.06632` [3] Towards Safer Smart Contracts: A Sequence Learning Approach to Detecting Security Threats
  3. `2106.13422` [2|3] Vulnerability and Transaction behavior based detection of Malicious Smart Contracts
  4. `2301.08824` [2|3] An Automated Vulnerability Detection Framework for Smart Contracts
  5. `2410.20712` [3] Interaction-Aware Vulnerability Detection in Smart Contract Bytecodes

### BM25 much better than E5

**Query 8 (identifier): "replay attacks on TLS 1.3 0-RTT early data"**: nDCG@10 BM25 0.775, E5 0.211, BM25+E5 0.550

- BM25 top 5:
  1. `1907.12762` [0|1] The Era of TLS 1.3: Measuring Deployment and Use with Active and Passive Methods
  2. `2306.11643` [1|2] On Cross-Layer Interactions of QUIC, Encrypted DNS and HTTP/3: Design, Evaluation and Dataset
  3. `2207.01841` [1] Challenges in Adapting ECH in TLS for Privacy Enhancement over the Internet
  4. `2106.08759` [1] OpenSSLNTRU: Faster post-quantum TLS key exchange
  5. `1905.03518` [1] Enhanced Performance and Privacy for TLS over TCP Fast Open
- E5 top 5:
  1. `2004.02257` [0] Security Analysis and Fault Detection Against Stealthy Replay Attacks
  2. `1901.11218` [0] Replay Attacks and Defenses Against Cross-shard Consensus in Sharded Distributed Ledgers
  3. `2506.17446` [0] Open Sky, Open Threats: Replay Attacks in Space Launch and Re-entry Phases
  4. `2309.13579` [0|1] Seeing Is Not Always Believing: Invisible Collision Attack and Defence on Pre-Trained Models
  5. `1602.02148` [0] A replay-attack resistant message authentication scheme using time-based keying hash functions and unique mess

**Query 10 (identifier): "nonce reuse forgery attacks on AES-GCM"**: nDCG@10 BM25 1.000, E5 0.558, BM25+E5 0.786

- BM25 top 5:
  1. `2309.07782` [0|1] The Nonce-nce of Web Security: an Investigation of CSP Nonces Reuse
  2. `2111.05117` [0|1] AEAD Modes for ZUC Family Stream Ciphers
  3. `2005.13864` [1] Mitigating TLS compromise with ECDHE and SRP
  4. `2309.14368` [0|1] Quantum forgery attacks on COPA,AES-COPA and marble authenticated encryption algorithms
  5. `2504.07265` [0|1] ECDSA Cracking Methods
- E5 top 5:
  1. `2309.14368` [0|1] Quantum forgery attacks on COPA,AES-COPA and marble authenticated encryption algorithms
  2. `1904.07550` [0] Re: What's Up Johnny? -- Covert Content Attacks on Email End-to-End Encryption
  3. `2111.05117` [0|1] AEAD Modes for ZUC Family Stream Ciphers
  4. `2412.03283` [0] Black-Box Forgery Attacks on Semantic Watermarks for Diffusion Models
  5. `1602.02148` [0|1] A replay-attack resistant message authentication scheme using time-based keying hash functions and unique mess

**Query 41 (paraphrase): "inferring which websites a user visits from encrypted traffic patterns"**: nDCG@10 BM25 0.927, E5 0.629, BM25+E5 0.915

- BM25 top 5:
  1. `1907.01317` [1|3] Padding Ain't Enough: Assessing the Privacy Guarantees of Encrypted DNS
  2. `2409.04341` [3] Towards Fine-Grained Webpage Fingerprinting at Scale
  3. `2512.17667` [3] STAR: Semantic-Traffic Alignment and Retrieval for Zero-Shot HTTPS Website Fingerprinting
  4. `2509.12462` [3] Redefining Website Fingerprinting Attacks With Multiagent LLMs
  5. `2510.14283` [3] Beyond a Single Perspective: Towards a Realistic Evaluation of Website Fingerprinting Attacks
- E5 top 5:
  1. `1708.06376` [3] Automated Website Fingerprinting through Deep Learning
  2. `2006.12352` [1] A Survey on Analyzing Encrypted Network Traffic of Mobile Devices
  3. `1807.02719` [2|3] Nothing But Net: Invading Android User Privacy Using Only Network Access Patterns
  4. `2302.13763` [3] Efficient and Low Overhead Website Fingerprinting Attacks and Defenses based on TCP/IP Traffic
  5. `1603.04865` [1] Robust Machine Learning for Encrypted Traffic Classification

**Query 12 (homonym): "padding oracle attacks on CBC mode encryption"**: nDCG@10 BM25 0.643, E5 0.397, BM25+E5 0.551

- BM25 top 5:
  1. `1601.08139` [0|1] Quantitative Evaluation of Chaotic CBC Mode of Operation
  2. `1706.08099` [0|1] Lyapunov Exponent Evaluation of the CBC Mode of Operation
  3. `1608.05838` [0|1] Proving chaotic behaviour of CBC mode of operation
  4. `2407.09490` [1] Performance Comparison of Various Modes of Advanced Encryption Standard
  5. `1708.03243` [0|1] Summary of Topological Study of Chaotic CBC Mode of Operation
- E5 top 5:
  1. `2311.08027` [0] A practical key-recovery attack on LWE-based key-encapsulation mechanism schemes using Rowhammer
  2. `1605.02950` [0|1] The dynamics of the CBC Mode of Operation
  3. `1608.05838` [0|1] Proving chaotic behaviour of CBC mode of operation
  4. `1706.08099` [0|1] Lyapunov Exponent Evaluation of the CBC Mode of Operation
  5. `1807.05782` [1] Determining the Optimal Random-padding Size for Rabin Cryptosystems

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
