"""Step 4: compute annotator agreement, list disagreements and freeze the qrels.

    # 1) agreement + disagreement sheet (before discussion)
    python scripts/merge_judgments.py --exports judging/exports/judgments_*_main.json --out data/qrels
    # 2) after the team fills the `final` column of data/qrels/disagreements.csv
    python scripts/merge_judgments.py --exports judging/exports/judgments_*_main.json \
        --adjudication data/qrels/disagreements.csv --out data/qrels --freeze

`--fallback lower` produces preliminary qrels before adjudication is finished
(marked as preliminary in the output; never use them for the final report).
"""
import argparse
import csv
import glob
import json
from pathlib import Path

from irproj.io import sha256_file, write_qrels
from irproj.pool import agreement, load_exports, merge, read_adjudication

ap = argparse.ArgumentParser()
ap.add_argument("--exports", nargs="+", required=True)
ap.add_argument("--adjudication", default=None)
ap.add_argument("--fallback", choices=["lower", "mean"], default=None)
ap.add_argument("--out", default="data/qrels")
ap.add_argument("--freeze", action="store_true")
ap.add_argument("--corpus", default=None, help="optional, adds titles to the disagreement sheet")
a = ap.parse_args()

paths = sorted({p for pat in a.exports for p in glob.glob(pat)})
judg = load_exports(paths)
agree = agreement(judg)
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
(out / "agreement.json").write_text(json.dumps(agree, indent=2))
print(f"double-judged pairs: {agree['n']}, weighted kappa (linear) = {agree['kappa_linear']:.3f}, "
      f"quadratic = {agree['kappa_quadratic']:.3f}, exact agreement = {agree['exact_agreement']:.3f}")

adj = read_adjudication(a.adjudication) if a.adjudication else {}
qrels, unresolved = merge(judg, adj, a.fallback)

titles = {}
if a.corpus:
    from irproj.io import read_jsonl
    titles = {d["id"]: d["title"] for d in read_jsonl(a.corpus)}
if unresolved:
    anns = sorted(judg)
    sheet = out / "disagreements.csv"
    if not a.adjudication or Path(a.adjudication).resolve() != sheet.resolve():
        with open(sheet, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["qid", "docid", "title"] + anns + ["final"])
            for u in sorted(unresolved, key=lambda r: (r["qid"], r["docid"])):
                w.writerow([u["qid"], u["docid"], titles.get(u["docid"], "")] + [u.get(x, "") for x in anns] + [""])
    print(f"{len(unresolved)} disagreements without a final grade -> {sheet}")

name = "qrels.txt" if not a.fallback else f"qrels.preliminary-{a.fallback}.txt"
if unresolved and not a.fallback:
    print("qrels NOT written: resolve all disagreements first (or use --fallback for preliminary numbers)")
else:
    write_qrels(out / name, qrels)
    n = sum(len(v) for v in qrels.values())
    print(f"wrote {out / name}: {len(qrels)} queries, {n} judged documents")
    if a.freeze and not a.fallback:
        (out / "qrels.sha256").write_text(sha256_file(out / name) + "  qrels.txt\n")
        print("frozen: checksum written to", out / "qrels.sha256")
