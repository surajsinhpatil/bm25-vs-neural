"""Figures (matplotlib) and LaTeX tables generated from the evaluation results."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np

# Validated categorical palette (fixed order; colour follows the system, never its rank)
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"

PRETTY = {
    "bm25": "BM25", "e5": "E5", "specter2": "SPECTER2",
    "bm25+e5": "BM25+E5", "bm25+specter2": "BM25+SPECTER2",
    "bm25-plain": "BM25 (plain tok.)", "ce": "Cross-encoder", "pyserini": "Pyserini BM25",
}
CATEGORY_NAMES = {"identifier": "Exact identifier", "homonym": "Homonym", "negation": "Negation",
                  "time": "Time constraint", "paraphrase": "Paraphrase"}
METRIC_NAMES = {"ndcg@10": "nDCG@10", "ndcg@5": "nDCG@5", "p@5": "P@5", "mrr@10": "MRR@10",
                "map@10": "MAP@10", "recall@10": "R@10", "hole@10": "Hole@10"}


def pretty(s: str) -> str:
    return PRETTY.get(s, s)


def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def grouped_bars(path: str | Path, groups: Sequence[str], systems: Sequence[str],
                 means: Dict[str, Dict[str, float]], lows=None, highs=None, ylabel="nDCG@10",
                 title=None, colors: Dict[str, str] | None = None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = colors or {s: SERIES[i % len(SERIES)] for i, s in enumerate(systems)}
    fig, ax = plt.subplots(figsize=(7.0, 2.6), dpi=200)
    n = len(systems)
    width = 0.8 / n
    x = np.arange(len(groups))
    for i, s in enumerate(systems):
        m = np.array([means[s].get(g, np.nan) for g in groups])
        pos = x - 0.4 + width * (i + 0.5)
        hatch = "////" if "+" in s else None          # secondary encoding for hybrid runs
        ax.bar(pos, m, width * 0.88, color=colors[s], label=pretty(s), hatch=hatch,
               edgecolor="white", linewidth=0.4)
        if lows is not None:
            lo = np.array([lows[s].get(g, np.nan) for g in groups])
            hi = np.array([highs[s].get(g, np.nan) for g in groups])
            ax.errorbar(pos, m, yerr=[m - lo, hi - m], fmt="none", ecolor=INK2, elinewidth=0.6, capsize=1.5)
    ax.set_xticks(x)
    ax.set_xticklabels([CATEGORY_NAMES.get(g, g) for g in groups], fontsize=8, color=INK)
    ax.set_ylabel(ylabel, fontsize=8, color=INK2)
    ax.set_ylim(0, 1.0)
    if title:
        ax.set_title(title, fontsize=9, color=INK, loc="left")
    _style(ax)
    ax.legend(fontsize=7, ncol=min(n, 5), frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.18))
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight")
    fig.savefig(str(Path(path).with_suffix(".png")), bbox_inches="tight")
    plt.close(fig)


def heatmap(path: str | Path, k1s: Sequence[float], bs: Sequence[float], grid: np.ndarray,
            marks: Dict[str, tuple] | None = None, label="nDCG@10"):
    """Sequential single-hue heatmap of BM25 effectiveness over (b, k1)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
    fig, ax = plt.subplots(figsize=(3.4, 2.5), dpi=200)
    im = ax.imshow(grid, origin="lower", aspect="auto", cmap=cmap,
                   extent=[bs[0] - 0.05, bs[-1] + 0.05, k1s[0] - 0.1, k1s[-1] + 0.1])
    for name, (k1, b) in (marks or {}).items():
        ax.plot(b, k1, marker="o", ms=5, mfc="white", mec=INK, mew=0.8)
        ax.annotate(name, (b, k1), textcoords="offset points", xytext=(4, 4), fontsize=6, color=INK)
    ax.set_xlabel("b", fontsize=8, color=INK2)
    ax.set_ylabel("k1", fontsize=8, color=INK2)
    ax.tick_params(colors=INK2, labelsize=7)
    cb = fig.colorbar(im, ax=ax)
    cb.ax.tick_params(labelsize=7, colors=INK2)
    cb.set_label(label, fontsize=7, color=INK2)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    fig.savefig(str(Path(path).with_suffix(".png")), bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- LaTeX
def _fmt(v, d=3):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "--"
    return f"{v:.{d}f}"


def latex_table(rows: List[List[str]], header: List[str], align: str, caption: str, label: str,
                bold_max_cols: Sequence[int] = (), small: bool = True) -> str:
    """Booktabs table. Columns listed in bold_max_cols get their maximum value in bold."""
    body = [list(r) for r in rows]
    for c in bold_max_cols:
        vals = []
        for r in body:
            try:
                vals.append(float(r[c].split()[0].replace("$", "")))
            except (ValueError, IndexError):
                vals.append(-np.inf)
        if vals and max(vals) > -np.inf:
            best = max(vals)
            for r, v in zip(body, vals):
                if v == best:
                    r[c] = r"\textbf{" + r[c] + "}"
    lines = [r"\begin{table}[t]", r"\centering"]
    if small:
        lines.append(r"\small")
    lines += [rf"\caption{{{caption}}}", rf"\label{{{label}}}", rf"\begin{{tabular}}{{{align}}}",
              r"\toprule", " & ".join(header) + r" \\", r"\midrule"]
    lines += [" & ".join(r) + r" \\" for r in body]
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def write(path: str | Path, text: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")


fmt = _fmt
