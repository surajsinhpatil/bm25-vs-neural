"""Inter-annotator agreement report (markdown) from the audit output."""
import argparse
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--audit", default="deliverables/judging/audit.json")
ap.add_argument("--out", default="deliverables/judging/agreement_report.md")
a = ap.parse_args()
d = json.loads(Path(a.audit).read_text())
s = d["summary"]
L = ["# Inter-annotator agreement", "",
     "## Design", "",
     f"- Pool: top 10 of each of the five runs for 50 queries, {s['pool_pairs']} query–document pairs.",
     "- Each query was judged independently by two of the four annotators; the six annotator pairs were "
     "spread evenly (8–9 queries each), so every pair contributes to the estimate.",
     "- Annotators saw no system names or ranks; dates were shown only for time-constraint queries.",
     "- Grades: 0 not relevant, 1 on topic but does not answer / breaks a condition, 2 relevant, 3 highly relevant.", "",
     "## Method", "",
     "- Cohen's kappa computed over all pairs judged by both assigned annotators "
     f"({s['pairs_with_two_judgments']} pairs). Ratings that do not exist are never paired or counted as 0.",
     "- Weighted kappa for the ordinal 0–3 scale: linear weights |i−j|/3 (primary, pre-registered) and quadratic "
     "weights ((i−j)/3)²; also unweighted kappa and kappa on binary relevance (grade ≥ 2), the level used by "
     "P@5, MRR@10 and MAP@10.",
     "- Implementation: `irproj.stats.weighted_kappa`, checked against scikit-learn's `cohen_kappa_score` in "
     "`tests/test_core.py`.", "",
     "## Results (validated)", "",
     f"| Measure | Value |", "|---|---|",
     f"| Weighted κ, linear (primary) | {s['kappa_linear']:.3f} |",
     f"| Weighted κ, quadratic | {s['kappa_quadratic']:.3f} |",
     f"| Unweighted κ | {s['kappa_unweighted']:.3f} |",
     f"| κ on binary relevance (≥ 2) | {s['kappa_binary_ge2']:.3f} |",
     f"| Exact agreement | {s['exact_agreement']:.3f} ({s['agreeing_pairs']} of {s['pairs_with_two_judgments']}) |",
     f"| Conflicts by gap (1 / 2 / 3) | {s['gap_distribution'].get('1', 0)} / {s['gap_distribution'].get('2', 0)} / {s['gap_distribution'].get('3', 0)} |",
     f"| Conflicts crossing the relevance line | {s['binary_relevance_disagreements']} |", "",
     "Per annotator pair:", "",
     "| Pair | Shared pairs | Queries | κ linear | κ quadratic | Exact |", "|---|---|---|---|---|---|"]
L += [f"| {k} | {v['n']} | {v['queries']} | {v['kappa_linear']:.3f} | {v['kappa_quadratic']:.3f} | {v['exact']:.3f} |"
      for k, v in d["pairwise"].items()]
low = [k for k, v in d["pairwise"].items() if v["kappa_linear"] < 0.6]
L += ["", "## Interpretation", "",
      f"- Overall linear κ = {s['kappa_linear']:.2f} meets the protocol's target of ≥ 0.6, so the guidelines did "
      "not need revision and no query has to be re-judged on agreement grounds."
      if s["kappa_linear"] >= 0.6 else
      f"- Overall linear κ = {s['kappa_linear']:.2f} is BELOW the protocol's target of 0.6: revise the guidelines "
      "and re-judge the worst queries before freezing.",
      (f"- Pair(s) below 0.6: {', '.join(low)}. Their conflicts deserve particular care at adjudication.") if low else
      "- Every annotator pair is at or above 0.6.",
      "- Most conflicts are one grade apart; conflicts of two or more grades and conflicts on the relevance "
      "line are the ones that change binary metrics and are adjudicated first.", ""]
Path(a.out).write_text("\n".join(L))
print(f"wrote {a.out}")
