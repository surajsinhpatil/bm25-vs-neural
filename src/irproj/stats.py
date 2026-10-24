"""Statistics: significance tests, confidence intervals and annotator agreement."""
from __future__ import annotations

from itertools import combinations
from typing import Dict, List, Sequence, Tuple

import numpy as np


def paired_randomization_test(a: Sequence[float], b: Sequence[float], n_perm: int = 100_000,
                              seed: int = 0) -> Tuple[float, float]:
    """Two-sided paired randomisation (permutation) test on the mean difference
    [Smucker, Allan & Carterette 2007]. Under H0 the system labels of each query are
    exchangeable, i.e. the sign of each per-query difference is random.
    Returns (mean difference a - b, p-value)."""
    d = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    obs = d.mean()
    if np.allclose(d, 0):
        return 0.0, 1.0
    if d.size <= 16:                         # small n: enumerate all 2^n sign patterns exactly
        n = d.size
        bits = ((np.arange(2 ** n)[:, None] >> np.arange(n)) & 1) * 2.0 - 1.0
        perm = (bits * d).mean(axis=1)
        return float(obs), float(np.mean(np.abs(perm) >= abs(obs) - 1e-12))
    rng = np.random.default_rng(seed)
    count, done, chunk = 0, 0, 10_000
    while done < n_perm:
        m = min(chunk, n_perm - done)
        signs = rng.choice((-1.0, 1.0), size=(m, d.size))
        perm = (signs * d).mean(axis=1)
        count += int(np.sum(np.abs(perm) >= abs(obs) - 1e-12))
        done += m
    return float(obs), (count + 1) / (n_perm + 1)


def holm_bonferroni(pvals: Dict[str, float], alpha: float = 0.05) -> Dict[str, Tuple[float, bool]]:
    """Holm's step-down correction. Returns name -> (adjusted p, significant?)."""
    items = sorted(pvals.items(), key=lambda x: x[1])
    m = len(items)
    adjusted, running = {}, 0.0
    for i, (name, p) in enumerate(items):
        adj = min(1.0, (m - i) * p)
        running = max(running, adj)          # enforce monotonicity
        adjusted[name] = running
    return {n: (adjusted[n], adjusted[n] <= alpha) for n in pvals}


def pairwise_tests(per_query: Dict[str, Dict[str, float]], systems: Sequence[str] | None = None,
                   n_perm: int = 100_000, seed: int = 0, alpha: float = 0.05) -> List[dict]:
    """All pairs of systems on one metric. per_query: system -> {qid: value}."""
    systems = list(systems or per_query)
    qids = sorted(set.intersection(*[set(per_query[s]) for s in systems]))
    raw, rows = {}, []
    for s1, s2 in combinations(systems, 2):
        a = [per_query[s1][q] for q in qids]
        b = [per_query[s2][q] for q in qids]
        diff, p = paired_randomization_test(a, b, n_perm, seed)
        _, lo, hi = bootstrap_ci(np.asarray(a) - np.asarray(b), seed=seed)
        key = f"{s1} vs {s2}"
        raw[key] = p
        d = np.asarray(a) - np.asarray(b)
        rows.append({"a": s1, "b": s2, "diff": diff, "diff_ci_low": lo, "diff_ci_high": hi, "p": p, "n": len(qids),
                     "a_better": int((d > 1e-12).sum()), "ties": int((np.abs(d) <= 1e-12).sum()),
                     "b_better": int((d < -1e-12).sum())})
    adj = holm_bonferroni(raw, alpha)
    for r in rows:
        r["p_holm"], r["significant"] = adj[f"{r['a']} vs {r['b']}"]
    return rows


def bootstrap_ci(values: Sequence[float], n_boot: int = 10_000, level: float = 0.95,
                 seed: int = 0) -> Tuple[float, float, float]:
    """Percentile bootstrap CI of the mean. Returns (mean, low, high)."""
    x = np.asarray(values, dtype=np.float64)
    if x.size == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, x.size, size=(n_boot, x.size))].mean(axis=1)
    lo, hi = np.percentile(means, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    return float(x.mean()), float(lo), float(hi)


def weighted_kappa(y1: Sequence[int], y2: Sequence[int], labels: Sequence[int] = (0, 1, 2, 3),
                   weights: str = "linear") -> float:
    """Weighted Cohen's kappa for ordinal grades (linear or quadratic weights)."""
    labels = list(labels)
    k = len(labels)
    pos = {l: i for i, l in enumerate(labels)}
    obs = np.zeros((k, k))
    for a, b in zip(y1, y2):
        obs[pos[a], pos[b]] += 1
    n = obs.sum()
    if n == 0:
        return float("nan")
    obs /= n
    exp = np.outer(obs.sum(1), obs.sum(0))
    i, j = np.meshgrid(range(k), range(k), indexing="ij")
    if weights == "linear":
        w = np.abs(i - j) / (k - 1)
    elif weights == "quadratic":
        w = ((i - j) / (k - 1)) ** 2
    else:
        w = (i != j).astype(float)
    denom = (w * exp).sum()
    return float(1 - (w * obs).sum() / denom) if denom > 0 else 1.0


def kendall_tau(scores_a: Dict[str, float], scores_b: Dict[str, float]) -> float:
    """Kendall's tau between two system rankings (system -> mean score)."""
    from scipy.stats import kendalltau
    systems = sorted(set(scores_a) & set(scores_b))
    tau, _ = kendalltau([scores_a[s] for s in systems], [scores_b[s] for s in systems])
    return float(tau)
