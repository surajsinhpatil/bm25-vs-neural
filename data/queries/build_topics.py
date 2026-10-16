"""Source of truth for the 50 test queries + 5 practice queries (DRAFT for team review).
Run it to regenerate topics.jsonl and topics.trec.

Grades used in every narrative: 3 = highly relevant (the paper is mainly about exactly this),
2 = relevant (answers the query), 1 = on the topic but does not answer it or breaks a
condition (exclusion, date), 0 = not relevant.
anchor_title: a paper we believe is in the corpus and relevant; scripts/check_queries.py
looks it up. None = the team must confirm a relevant anchor from the frozen corpus."""
import json
from pathlib import Path

T = []
def add(cat, query, desc, narr, anchor=None):
    T.append({"category": cat, "query": query, "description": desc, "narrative": narr, "anchor_title": anchor})

# ---------------------------------------------------------------- exact identifiers (BM25 expected)
add("identifier", "exploitation of Log4Shell (CVE-2021-44228)",
    "Papers that study, measure or defend against exploitation of the Log4Shell vulnerability in Apache Log4j.",
    "Relevant: analyses of Log4Shell/CVE-2021-44228 exploitation, attack traffic, patching or detection. Mentioning it only as one example among many vulnerabilities is grade 1. Other Log4j bugs alone are 0.")
add("identifier", "Spectre variant 1 bounds check bypass (CVE-2017-5753)",
    "Work on the Spectre v1 (bounds check bypass) speculative execution attack or defences specific to it.",
    "Relevant: papers presenting, extending, detecting or mitigating Spectre v1. Papers on other transient execution attacks (Meltdown, Spectre v2, MDS) without treating v1 specifically are grade 1.",
    "Spectre Attacks: Exploiting Speculative Execution")
add("identifier", "Meltdown CVE-2017-5754 reading kernel memory from user space",
    "The Meltdown attack, which lets user processes read kernel memory through out-of-order execution, and its mitigations such as KPTI/KAISER.",
    "Relevant: papers about Meltdown itself, its variants or kernel page-table isolation as a Meltdown defence. Generic surveys of microarchitectural attacks that discuss Meltdown in detail are 2; a passing mention is 1.",
    "Meltdown")
add("identifier", "Rowhammer on DDR4 memory despite Target Row Refresh (TRR)",
    "Rowhammer attacks or measurements on DDR4 DRAM, in particular those that bypass the in-DRAM TRR mitigation.",
    "Relevant: Rowhammer on DDR4 and/or TRR. Rowhammer on DDR3 only, or on other memory types, is grade 1.",
    "TRRespass: Exploiting the Many Sides of Target Row Refresh")
add("identifier", "WannaCry ransomware spreading through the EternalBlue SMBv1 exploit (MS17-010)",
    "Analyses of the WannaCry outbreak, its propagation via EternalBlue / MS17-010, or defences against it.",
    "Relevant: papers analysing WannaCry or EternalBlue. Ransomware papers that only use WannaCry as a sample among many are grade 1.")
add("identifier", "side-channel attacks on CRYSTALS-Kyber implementations",
    "Power, timing, electromagnetic or fault attacks against implementations of the Kyber / ML-KEM post-quantum KEM.",
    "Relevant: attacks on or protections (masking, shuffling) for Kyber/ML-KEM implementations. Side-channel work on other lattice schemes (Dilithium, Saber, NewHope) only is grade 1.")
add("identifier", "Foreshadow L1 Terminal Fault (L1TF) attack on Intel SGX enclaves",
    "The Foreshadow / L1TF transient execution attack that extracts secrets from SGX enclaves.",
    "Relevant: papers on Foreshadow/L1TF or that evaluate SGX defences against it. Other SGX attacks (e.g. Plundervolt, SgxPectre) are grade 1.")
add("identifier", "replay attacks on TLS 1.3 0-RTT early data",
    "Security of the 0-RTT (early data) mode of TLS 1.3, especially replay attacks and anti-replay mechanisms.",
    "Relevant: analyses of 0-RTT/early data security in TLS 1.3 (or QUIC 0-RTT built on it). General TLS 1.3 analyses that do not discuss 0-RTT are grade 1.")
add("identifier", "Mirai botnet infection of IoT devices",
    "Studies of the Mirai botnet or its variants and how they compromise IoT devices.",
    "Relevant: measurement, analysis or detection of Mirai and Mirai-derived botnets. IoT botnet papers that only cite Mirai as motivation are grade 1.")
add("identifier", "nonce reuse forgery attacks on AES-GCM",
    "Attacks that exploit repeated nonces in AES-GCM authenticated encryption, and nonce-misuse-resistant alternatives such as AES-GCM-SIV.",
    "Relevant: GCM nonce-reuse attacks, measurements of nonce reuse, or nonce-misuse-resistant modes positioned against GCM. General AEAD papers without GCM nonce reuse are grade 1.")

# ---------------------------------------------------------------- homonyms (dense expected)
add("homonym", "backdoor attacks on neural network classifiers (not cryptographic backdoors)",
    "Trojan/backdoor attacks that implant a trigger into a machine learning model, and defences against them.",
    "Relevant: ML backdoor/trojan attacks or defences. Backdoors in cryptographic algorithms, random number generators or software are 0.",
    "BadNets: Identifying Vulnerabilities in the Machine Learning Model Supply Chain")
add("homonym", "padding oracle attacks on CBC mode encryption",
    "Attacks that decrypt CBC ciphertexts by observing whether the receiver accepts the padding.",
    "Relevant: padding oracle attacks or defences (e.g. Lucky 13-style variants). Random oracle model or blockchain oracle papers are 0.")
add("homonym", "security proofs in the random oracle model",
    "Cryptographic constructions whose security is proven by modelling a hash function as a random oracle, or work on the limits of that model.",
    "Relevant: proofs in the ROM/QROM or analyses of the model itself. Padding oracles and blockchain oracles are 0.")
add("homonym", "blockchain oracles feeding off-chain data to smart contracts",
    "Oracle services that bring external data onto a blockchain, and attacks on them such as price-oracle manipulation.",
    "Relevant: design or security of blockchain/DeFi oracles, oracle manipulation attacks. Cryptographic oracles (padding, random oracle) are 0.")
add("homonym", "DNS cache poisoning by off-path attackers",
    "Attacks that insert forged records into DNS resolver caches, and defences such as source-port randomisation or DNSSEC.",
    "Relevant: DNS cache poisoning attacks or defences. Data poisoning of ML models is 0. ARP poisoning is 1.")
add("homonym", "poisoning the training data of machine learning models",
    "Attacks that corrupt a model by injecting malicious samples into its training set, and defences.",
    "Relevant: training-data poisoning (including in federated learning). DNS or ARP cache poisoning is 0. Backdoor attacks that work through poisoned data are 2.")
add("homonym", "access tokens for authentication in web APIs such as OAuth and JWT",
    "Security of bearer/access tokens used to authenticate clients to web services.",
    "Relevant: OAuth/OpenID Connect tokens, JWTs, session tokens and attacks on them. Cryptocurrency tokens and LLM tokens are 0.")
add("homonym", "shadow stacks for protecting return addresses",
    "Shadow stack defences (software or hardware such as Intel CET) that protect return addresses against control-flow hijacking.",
    "Relevant: design, evaluation or bypass of shadow stacks. 'Shadow models' in membership inference are 0. General CFI without a shadow stack is 1.")
add("homonym", "browser fingerprinting to track users without cookies",
    "Identifying or tracking web users through the attributes of their browser and device.",
    "Relevant: browser/device fingerprinting for tracking and defences against it. Biometric fingerprints and website fingerprinting on Tor traffic are 0.")
add("homonym", "spoofing attacks on fingerprint biometric sensors",
    "Presentation attacks with fake fingers against fingerprint recognition, and liveness detection.",
    "Relevant: fingerprint presentation attacks / liveness detection. Browser fingerprinting, website fingerprinting and other biometrics only are 0.")

# ---------------------------------------------------------------- negation (both weak)
add("negation", "intrusion detection methods that do not use deep learning",
    "Network or host intrusion detection approaches based on rules, statistics or classical machine learning, not deep neural networks.",
    "Relevant: IDS methods without deep learning. A deep-learning IDS is grade 1 (on topic but breaks the exclusion). Papers that compare against deep learning but propose a non-deep method are 2/3.")
add("negation", "Android malware detection without dynamic analysis",
    "Detecting Android malware purely by static analysis of the app, without executing it.",
    "Relevant: static-only Android malware detection. Methods that run the app (dynamic or hybrid analysis) are grade 1.")
add("negation", "post-quantum signature schemes that are not lattice-based",
    "Hash-based, code-based, multivariate, isogeny-based or other non-lattice post-quantum signatures.",
    "Relevant: design or analysis of non-lattice PQ signatures (SPHINCS+, XMSS, UOV, SQIsign...). Lattice signatures (Dilithium, Falcon) are grade 1.")
add("negation", "privacy-preserving machine learning without homomorphic encryption",
    "Private training or inference using techniques such as secure multi-party computation, differential privacy or trusted hardware instead of HE.",
    "Relevant: privacy-preserving ML that does not rely on homomorphic encryption. HE-based approaches are grade 1.")
add("negation", "phishing website detection without URL-based features",
    "Detecting phishing pages from their content, visual appearance or behaviour rather than from the URL string.",
    "Relevant: phishing detection using page content/visual/behaviour features. Methods relying on URL features are grade 1.")
add("negation", "side-channel attacks that do not need physical access to the device",
    "Remote or software-only side-channel attacks, e.g. timing over the network, cache attacks from co-located code, or software-based power measurement.",
    "Relevant: side channels mounted without physical access. Attacks needing probes, oscilloscopes or physical proximity are grade 1.")
add("negation", "smart contract vulnerability detection without symbolic execution",
    "Finding bugs in smart contracts with static analysis, fuzzing, machine learning or formal methods other than symbolic execution.",
    "Relevant: non-symbolic-execution vulnerability detection for smart contracts. Symbolic execution tools (Oyente, Mythril-style) are grade 1.")
add("negation", "user authentication that does not use passwords",
    "Authentication schemes based on tokens, biometrics, FIDO2/WebAuthn, behavioural signals or other non-password factors.",
    "Relevant: authentication without passwords. Password-based schemes, password managers or password strength are grade 1.")
add("negation", "anonymous communication systems that are not based on Tor",
    "Anonymity networks and protocols other than Tor, such as mixnets, DC-nets or I2P.",
    "Relevant: non-Tor anonymous communication. Papers about Tor itself are grade 1.")
add("negation", "fuzzing approaches that do not rely on code coverage feedback",
    "Black-box, generation-based or other fuzzers that do not use coverage guidance.",
    "Relevant: fuzzers without coverage feedback. Coverage-guided (greybox) fuzzers are grade 1.")

# ---------------------------------------------------------------- time constraints (both weak)
add("time", "attacks on TLS 1.3 published after its 2018 standardisation",
    "Attacks on or security analyses of TLS 1.3 that appeared after RFC 8446 (August 2018).",
    "Relevant: TLS 1.3 attacks/analyses first posted in 2019 or later. Matching papers from 2018 or earlier are grade 1. The annotator can see the date.")
add("time", "prompt injection attacks on LLM-integrated applications published since 2023",
    "Direct or indirect prompt injection against applications built on large language models.",
    "Relevant: prompt injection papers from 2023 onwards. Older matching papers are grade 1 (unlikely to exist).",
    "Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection")
add("time", "ransomware detection published before 2018",
    "Early work on detecting crypto-ransomware, e.g. via file-system activity or entropy.",
    "Relevant: ransomware detection papers first posted in 2016 or 2017. Later ones are grade 1.")
add("time", "security of 5G authentication and key agreement published after 2019",
    "Formal or practical analyses of 5G-AKA and related 5G authentication protocols.",
    "Relevant: 5G authentication analyses from 2020 onwards. Earlier ones (2016-2019) are grade 1. 4G/LTE only is grade 1.")
add("time", "new transient execution attacks published after 2020",
    "Spectre/Meltdown-style transient execution attack variants that appeared from 2021 onwards.",
    "Relevant: new transient execution attacks first posted 2021 or later. Earlier ones are grade 1; defences only are grade 1.")
add("time", "adversarial examples against malware classifiers published before 2019",
    "Early evasion attacks that modify malware so that ML-based detectors misclassify it.",
    "Relevant: adversarial malware papers first posted in 2016-2018. Later ones are grade 1.")
add("time", "privacy of COVID-19 contact tracing apps published in 2020",
    "Privacy analyses and designs of Bluetooth or GPS-based contact tracing apps posted during 2020.",
    "Relevant: contact tracing privacy papers first posted in 2020. Those from 2021 or later are grade 1.")
add("time", "membership inference attacks on large language models published since 2023",
    "Determining whether text was in an LLM's training data.",
    "Relevant: membership inference on LLMs from 2023 onwards. Older or non-LLM membership inference papers are grade 1.")
add("time", "cryptojacking browser mining malware published between 2018 and 2020",
    "Unauthorised cryptocurrency mining in browsers or on compromised machines.",
    "Relevant: cryptojacking papers first posted 2018-2020 inclusive. Others are grade 1.")
add("time", "deployment of post-quantum key exchange in TLS published after 2022",
    "Experiments and measurements of hybrid or post-quantum key exchange in TLS/QUIC.",
    "Relevant: PQ key exchange in TLS from 2023 onwards. Earlier ones are grade 1.")

# ---------------------------------------------------------------- paraphrases (dense expected)
add("paraphrase", "inferring which websites a user visits from encrypted traffic patterns",
    "Website fingerprinting: identifying visited pages from the size and timing of encrypted (e.g. Tor) traffic.",
    "Relevant: website fingerprinting attacks or defences. Browser fingerprinting is 0.",
    "Deep Fingerprinting: Undermining Website Fingerprinting Defenses with Deep Learning")
add("paraphrase", "telling whether a particular person's record was used to train a model",
    "Membership inference attacks against machine learning models and defences.",
    "Relevant: membership inference. Attribute inference or model inversion only is grade 1.",
    "Membership Inference Attacks against Machine Learning Models")
add("paraphrase", "copying a deployed model by repeatedly querying its prediction interface",
    "Model extraction / model stealing through prediction APIs.",
    "Relevant: model extraction or stealing attacks and defences. Membership inference only is grade 1.",
    "Stealing Machine Learning Models via Prediction APIs")
add("paraphrase", "tiny changes to an input that make a classifier give the wrong answer",
    "Adversarial examples (evasion attacks) against neural networks and robustness to them.",
    "Relevant: adversarial example attacks or defences. Training-data poisoning is grade 1.",
    "Towards Evaluating the Robustness of Neural Networks")
add("paraphrase", "recovering secret keys by measuring how long cryptographic operations take",
    "Timing side-channel attacks on cryptographic implementations and constant-time defences.",
    "Relevant: timing attacks or constant-time programming/verification. Power/EM side channels only are grade 1.")
add("paraphrase", "tricking a chatbot into ignoring its safety rules",
    "Jailbreak attacks against safety-aligned large language models and defences.",
    "Relevant: LLM jailbreaks or jailbreak defences. Prompt injection against applications is grade 2 if it bypasses safety rules, otherwise 1.",
    "Universal and Transferable Adversarial Attacks on Aligned Language Models")
add("paraphrase", "hiding secret messages inside images so nobody notices",
    "Image steganography and its detection (steganalysis).",
    "Relevant: image steganography or steganalysis. Watermarking is grade 1.")
add("paraphrase", "programs that lock a victim's files and demand payment to unlock them",
    "Ransomware: analysis, detection and recovery.",
    "Relevant: ransomware papers of any kind. General malware papers are grade 1.")
add("paraphrase", "training a shared model on many phones without collecting their raw data while keeping each phone's update private",
    "Privacy in federated learning, e.g. secure aggregation or differentially private federated learning.",
    "Relevant: privacy protection of client updates in federated learning. Federated learning without a privacy mechanism, or attacks only, are grade 1.")
add("paraphrase", "checking that the software running on a remote device has not been tampered with",
    "Remote attestation of software integrity on IoT devices, servers or enclaves.",
    "Relevant: remote attestation schemes or their analysis. Secure boot only is grade 1.")

# ---------------------------------------------------------------- practice (annotator training only)
for q, d in [("password strength meters", "How well password strength meters estimate guessability."),
             ("reentrancy vulnerabilities in smart contracts", "Detecting or exploiting reentrancy bugs in Ethereum contracts."),
             ("differential privacy for location data", "Protecting location traces with differential privacy."),
             ("solving CAPTCHAs with machine learning", "Automated CAPTCHA breaking using ML."),
             ("private set intersection protocols", "Two-party or multi-party PSI protocols and their efficiency.")]:
    T.append({"category": "practice", "query": q, "description": d,
              "narrative": "Practice query: grade with the standard 0-3 scale.", "anchor_title": None})

for i, t in enumerate(T):
    t["qid"] = str(i + 1) if t["category"] != "practice" else f"P{i - 49}"
here = Path(__file__).parent
with open(here / "topics.jsonl", "w") as f:
    for t in T:
        f.write(json.dumps(t, ensure_ascii=False) + "\n")
import sys; sys.path.insert(0, str(here.parents[1] / "src"))
from irproj.io import write_trec_topics
write_trec_topics(here / "topics.trec", [t for t in T if t["category"] != "practice"])
from collections import Counter
print(Counter(t["category"] for t in T), "anchors:", sum(t["anchor_title"] is not None for t in T))
