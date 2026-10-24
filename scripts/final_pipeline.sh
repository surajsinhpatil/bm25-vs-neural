#!/usr/bin/env bash
# Reproduce every judged result from the repository.
#
#   bash scripts/final_pipeline.sh preliminary
#       Audit + agreement, adjudication sheet, and PRELIMINARY results under two bounds
#       (every unresolved conflict at the lower grade / at the higher grade) -> deliverables/preliminary
#
#   bash scripts/final_pipeline.sh candidate <adjudicated_sheet.csv>
#       Same evaluation as final, into deliverables/candidate, without freezing anything.
#
#   bash scripts/final_pipeline.sh final <adjudicated_sheet.csv> [adjudication_note.txt]
#       Freezes data/qrels/qrels.txt (checksum + provenance) from the agreed grades and the team's
#       adjudicated grades, then evaluates everything against it -> deliverables/final.
#       Refuses to run while any conflict in the sheet has no final grade.
#
# Optional: PAGES=judging/round1 (folder with the judge_*.html pages) adds paper titles/abstracts
# to the adjudication sheet and the error analysis.
set -euo pipefail
cd "$(dirname "$0")/.."
MODE=${1:-preliminary}
T=data/queries/topics.jsonl
EXPORTS="judging/exports/judgments_*_main.json"
RUNS="runs/bm25.run runs/e5.run runs/specter2.run runs/bm25+e5.run runs/bm25+specter2.run"
PAGES=${PAGES:-}
PAGEARG=(); [ -n "$PAGES" ] && PAGEARG=(--pages "$PAGES")

python3 -m pytest -q tests
python3 scripts/audit_judgments.py --exports "$EXPORTS" --out deliverables/judging > /dev/null
python3 scripts/make_adjudication_sheet.py "${PAGEARG[@]}" > /dev/null
python3 scripts/agreement_report.py --audit deliverables/judging/audit.json --out deliverables/judging/agreement_report.md
python3 scripts/efficiency_report.py --out deliverables/efficiency > /dev/null

evaluate_all () {   # $1 = qrels, $2 = output folder, $3 = status text
  local Q=$1 O=$2 S=$3
  python3 scripts/validate_metrics.py --qrels "$Q" --topics $T --runs $RUNS --out "$O/metric_validation.json"
  python3 scripts/evaluate.py --qrels "$Q" --topics $T --runs $RUNS --out "$O/results" --tables "$O/tables" \
    --figures "$O/figures" --status "$S"
  python3 scripts/error_analysis.py --qrels "$Q" --qrels-label "$S" --out "$O/analysis" "${PAGEARG[@]}" > /dev/null
}

if [ "$MODE" = preliminary ]; then
  for B in lower upper; do
    python3 scripts/merge_judgments.py --exports "$EXPORTS" --out deliverables/preliminary/qrels --fallback $B | tail -1
    evaluate_all deliverables/preliminary/qrels/qrels.preliminary-$B.txt deliverables/preliminary/$B \
      "PRELIMINARY (unresolved conflicts at the $B grade)."
  done
  python3 scripts/adjudication_sensitivity.py --out deliverables/preliminary/sensitivity > /dev/null
  python3 scripts/make_report_tables.py --mode preliminary
elif [ "$MODE" = candidate ]; then
  # evaluates a completed adjudication sheet WITHOUT freezing data/qrels (for review before sign-off)
  SHEET=${2:?usage: final_pipeline.sh candidate <adjudicated_sheet.csv>}
  python3 scripts/merge_judgments.py --exports "$EXPORTS" --out deliverables/candidate/qrels --adjudication "$SHEET"
  evaluate_all deliverables/candidate/qrels/qrels.txt deliverables/candidate \
    "CANDIDATE (adjudicated, not yet signed off)."
elif [ "$MODE" = final ]; then
  SHEET=${2:?usage: final_pipeline.sh final <adjudicated_sheet.csv>}
  NOTE=${3:-}
  NOTEARG=(); [ -n "$NOTE" ] && NOTEARG=(--adjudication-note "$NOTE")
  python3 scripts/merge_judgments.py --exports "$EXPORTS" --out data/qrels --adjudication "$SHEET" --freeze "${NOTEARG[@]}"
  sha256sum -c <(sed 's#  qrels.txt#  data/qrels/qrels.txt#' data/qrels/qrels.sha256)
  evaluate_all data/qrels/qrels.txt deliverables/final "Final (adjudicated qrels)."
  python3 scripts/make_report_tables.py --mode final
  echo
  echo "RQ5 needs the corpus: run notebooks/kaggle_rq5.ipynb on Kaggle, or with data/corpus/cscr.jsonl present:"
  echo "  python scripts/bm25_sweep.py --corpus data/corpus/cscr.jsonl          # -> deliverables/rq5/sweep"
  echo "  python scripts/tokenizer_ablation.py --corpus data/corpus/cscr.jsonl  # -> deliverables/rq5/tokenisation"
else
  echo "unknown mode $MODE"; exit 1
fi
if command -v pdflatex > /dev/null; then
  (cd report && for i in 1 2; do pdflatex -interaction=nonstopmode -halt-on-error final_report.tex > /dev/null; done \
     && rm -f final_report.aux final_report.log final_report.out && echo "report/final_report.pdf built")
fi
