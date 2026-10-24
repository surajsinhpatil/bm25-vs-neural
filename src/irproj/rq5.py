"""Shared machinery for RQ5 (BM25 parameter sweep and tokenisation ablation).

Everything here protects the frozen primary results:
  * outputs may not be written into frozen locations (qrels, judgment exports, adjudication
    records, the primary runs and the final / candidate / preliminary deliverables)
  * the qrels must be byte-identical to the frozen file (SHA-256 against data/qrels/qrels.sha256)
  * the rebuilt corpus is checked against data/corpus/EXPECTED.json, and the default BM25 run
    rebuilt from it is compared with the committed runs/bm25.run
and every output is accompanied by a metadata record (files, checksums, versions, commit, args).
"""
from __future__ import annotations

import json
import platform
import random
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

import numpy as np

from .io import Run, rank_docs, read_run, sha256_file

ROOT = Path(__file__).resolve().parents[2]

# Relative to the repository root. Nothing produced by RQ5 may be written inside these.
PROTECTED = ("data/qrels", "data/corpus/EXPECTED.json", "judging/exports", "judging/adjudication",
             "judging/round1", "runs", "deliverables/final", "deliverables/candidate",
             "deliverables/preliminary", "deliverables/judging")

DEFAULT = (1.2, 0.75)                 # the main BM25 setting (k1, b)
K1_GRID = tuple(sorted({round(0.2 * i, 1) for i in range(1, 11)} | {0.9}))     # 0.2..2.0 + 0.9
B_GRID = tuple(sorted({round(0.1 * i, 1) for i in range(0, 11)} | {0.75}))     # 0.0..1.0 + 0.75
CV_SEED = 11                          # primary fold assignment (fixed before any result was seen)
EXTRA_SEEDS = tuple(range(101, 121))  # 20 further fold assignments, robustness only


class FrozenPathError(SystemExit):
    pass


# --------------------------------------------------------------------------- output guard
def guard_output(path: str | Path, root: Path = ROOT) -> Path:
    """Return the resolved path, or stop if it lies inside a frozen location of the repository."""
    p = Path(path).resolve()
    for rel in PROTECTED:
        prot = (root / rel).resolve()
        if p == prot or prot in p.parents:
            raise FrozenPathError(f"refusing to write to {p}: inside frozen location '{rel}'. "
                                  "RQ5 outputs belong in deliverables/rq5/ and report/tables/rq5_*.")
    return p


# --------------------------------------------------------------------------- input checks
def frozen_qrels_sha(root: Path = ROOT) -> str:
    return (root / "data" / "qrels" / "qrels.sha256").read_text().split()[0]


def verify_qrels(path: str | Path, expected_sha: str) -> str:
    """Stop unless the qrels file has exactly the expected SHA-256."""
    got = sha256_file(path)
    if got != expected_sha:
        raise SystemExit(f"ERROR: {path} has SHA-256 {got}, expected the frozen {expected_sha}. "
                         "RQ5 must use the frozen qrels unchanged.")
    return got


def verify_corpus(path: str | Path, n_docs: int, expected_json: str | Path | None = None) -> Dict:
    """Compare the corpus with EXPECTED.json (document count and SHA-256 prefix).
    `expected_json` = None or "none" skips the check explicitly (synthetic tests only); a path that
    does not exist is an error, so a mistyped path cannot silently disable the check."""
    sha = sha256_file(path)
    out = {"path": str(path), "sha256": sha, "n_docs": n_docs}
    skip = expected_json is None or str(expected_json).lower() == "none"
    if not skip and not Path(expected_json).exists():
        raise SystemExit(f"ERROR: expected-corpus file {expected_json} does not exist "
                         "(pass 'none' to skip the corpus check on synthetic data)")
    out["skipped"] = skip
    if not skip:
        exp = json.loads(Path(expected_json).read_text())
        out.update(expected_n_docs=exp.get("n_docs"), expected_sha256_prefix=exp.get("sha256_prefix"),
                   n_docs_match=n_docs == exp.get("n_docs"),
                   sha256_prefix_match=sha.startswith(exp.get("sha256_prefix", "")))
        out["match"] = bool(out["n_docs_match"] and out["sha256_prefix_match"])
    else:
        out["match"] = None
    return out


def reproduction_check(run: Run, ref_path: str | Path, k: int = 10, tol: float = 1e-4) -> Dict:
    """Compare a rebuilt run with the committed reference run: same top-k documents in the same
    order and scores within `tol` (the reference stores 6 decimals)."""
    ref = read_run(ref_path)
    # the reference was written with 6 decimals: round the same way so that near-ties are ordered
    # identically (by docid, as trec_eval does) in both
    run = {q: {d: round(s, 6) for d, s in r.items()} for q, r in run.items()}
    qids = sorted(set(ref) | set(run))
    same, max_diff, bad = 0, 0.0, []
    for q in qids:
        a = rank_docs(run.get(q, {}))[:k]
        b = rank_docs(ref.get(q, {}))[:k]
        ok = [d for d, _ in a] == [d for d, _ in b]
        diff = max([abs(x[1] - y[1]) for x, y in zip(a, b)] or [0.0]) if ok else float("inf")
        if ok:
            max_diff = max(max_diff, diff)
        if ok and diff <= tol:
            same += 1
        else:
            bad.append(q)
    return {"reference": str(ref_path), "k": k, "queries": len(qids), "identical_topk": same,
            "max_abs_score_diff": max_diff, "mismatched_queries": bad, "ok": not bad}


# --------------------------------------------------------------------------- metadata
def _version(mod: str) -> str | None:
    try:
        from importlib.metadata import version
        return version(mod)
    except Exception:
        return None


def git_state(root: Path = ROOT) -> Dict:
    def run(*a):
        r = subprocess.run(["git", *a], cwd=root, capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    status = run("status", "--porcelain", "--untracked-files=no")
    return {"commit": run("rev-parse", "HEAD"), "dirty": bool(status) if status is not None else None}


def metadata(args: Mapping, files: Mapping[str, str | Path], extra: Mapping | None = None) -> Dict:
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git": git_state(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": {m: _version(m) for m in ("numpy", "scipy", "nltk", "matplotlib", "pandas", "irproj")},
        "args": dict(args),
        "files_sha256": {name: sha256_file(p) for name, p in files.items()},
        **(dict(extra) if extra else {}),
    }


# --------------------------------------------------------------------------- cross-validation
def stratified_folds(topics: Sequence[dict], n_folds: int = 5, seed: int = CV_SEED) -> Dict[str, int]:
    """qid -> fold. Within each category (in order of first appearance) the qids are sorted,
    shuffled with one shared RNG and dealt round-robin, so every fold gets the same mix."""
    by_cat: Dict[str, List[str]] = defaultdict(list)
    for t in topics:
        by_cat[t["category"]].append(t["qid"])
    rng = random.Random(seed)
    fold_of = {}
    for _, qs in by_cat.items():
        qs = sorted(qs)
        rng.shuffle(qs)
        for i, q in enumerate(qs):
            fold_of[q] = i % n_folds
    return fold_of


Setting = Tuple[float, float]


def _key(p: Setting, train_mean: float):
    # higher training mean first; exact ties (after rounding away float noise) go to the setting
    # closest to the default, then to the smaller k1 and b so the choice is deterministic
    return (-round(train_mean, 12), abs(p[0] - DEFAULT[0]) + abs(p[1] - DEFAULT[1]), p[0], p[1])


def cv_select(scores: Mapping[Setting, Mapping[str, float]], fold_of: Mapping[str, int],
              n_folds: int) -> Tuple[Dict[str, Setting], List[dict]]:
    """For each fold choose the setting with the best mean on the other folds.
    Returns (qid -> setting used for that held-out query, per-fold choices)."""
    qids = sorted(fold_of)
    used, chosen = {}, []
    for f in range(n_folds):
        train = [q for q in qids if fold_of[q] != f]
        test = [q for q in qids if fold_of[q] == f]
        means = {p: float(np.mean([v[q] for q in train])) for p, v in scores.items()}
        best = min(scores, key=lambda p: _key(p, means[p]))
        chosen.append({"fold": f, "k1": best[0], "b": best[1], "train_mean": means[best],
                       "n_train": len(train), "test_qids": test})
        for q in test:
            used[q] = best
    return used, chosen


def best_setting(scores: Mapping[Setting, Mapping[str, float]], qids: Sequence[str]) -> Setting:
    means = {p: float(np.mean([v[q] for q in qids])) for p, v in scores.items()}
    return min(scores, key=lambda p: _key(p, means[p]))


# --------------------------------------------------------------------------- figure
def heatmap(path: str | Path, k1s: Sequence[float], bs: Sequence[float], grid: np.ndarray,
            label: str, marks: Mapping[str, Setting] | None = None, fmt: str = "{:.2f}") -> None:
    """Heatmap on categorical axes (the grid is not evenly spaced), value printed in each cell."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from .report import INK, INK2
    fig, ax = plt.subplots(figsize=(5.2, 3.6), dpi=200)
    im = ax.imshow(grid, origin="lower", aspect="auto", cmap="Blues")
    ax.set_xticks(range(len(bs)), [f"{b:g}" for b in bs], fontsize=6)
    ax.set_yticks(range(len(k1s)), [f"{k:g}" for k in k1s], fontsize=6)
    lo, hi = np.nanmin(grid), np.nanmax(grid)
    for i in range(len(k1s)):
        for j in range(len(bs)):
            v = grid[i, j]
            dark = hi > lo and (v - lo) / (hi - lo) > 0.5
            ax.text(j, i, fmt.format(v), ha="center", va="center", fontsize=4.2,
                    color="white" if dark else INK)
    merged: Dict[Setting, List[str]] = {}
    for name, p in (marks or {}).items():
        merged.setdefault(tuple(p), []).append(name)
    for (k1, b), names in merged.items():
        name = " = ".join(names)
        if k1 in k1s and b in bs:
            ax.add_patch(plt.Rectangle((list(bs).index(b) - 0.5, list(k1s).index(k1) - 0.5), 1, 1,
                                       fill=False, ec="#d6336c", lw=1.0))
            ax.annotate(name, (list(bs).index(b), list(k1s).index(k1) + 0.5), fontsize=5,
                        color="#d6336c", ha="center", va="bottom")
    ax.set_xlabel("b", fontsize=8, color=INK2)
    ax.set_ylabel("k1", fontsize=8, color=INK2)
    cb = fig.colorbar(im, ax=ax)
    cb.ax.tick_params(labelsize=6)
    cb.set_label(label, fontsize=7, color=INK2)
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight")
    fig.savefig(str(Path(path).with_suffix(".png")), bbox_inches="tight")
    plt.close(fig)
