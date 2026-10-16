#!/usr/bin/env bash
# Offline end-to-end run of the whole pipeline on a fake arXiv snapshot with tiny random models.
# The numbers it produces are meaningless; it only proves every step runs and connects.
#   bash tests/smoke_test.sh <reuters_beir_dir> <tiny_models_dir> <work_dir>
set -euo pipefail
SRC=$1; TINY=$2; W=$3
rm -rf "$W"; mkdir -p "$W"
T=data/queries/topics.jsonl
python3 tests/make_fake_snapshot.py "$SRC/corpus.jsonl" "$W/snapshot.json"
python3 scripts/build_corpus.py --snapshot "$W/snapshot.json" --out "$W/corpus.jsonl" --max-docs 4000 | tail -25
python3 scripts/check_queries.py --corpus "$W/corpus.jsonl" --topics $T --out "$W/results/query_check.json" | tail -15
python3 scripts/run_bm25.py --corpus "$W/corpus.jsonl" --topics $T --out "$W/runs/bm25.run"
for M in e5 specter2; do
  if [ $M = e5 ]; then X=(--model-name "$TINY/base"); else X=(--model-name "$TINY/base" --adapters "$TINY/proximity" "$TINY/adhoc_query"); fi
  python3 scripts/encode_corpus.py --model $M --corpus "$W/corpus.jsonl" --out "$W/indexes/$M" --batch-size 64 "${X[@]}" | tail -3
  python3 scripts/run_dense.py --model $M --index "$W/indexes/$M" --topics $T --out "$W/runs/$M.run" "${X[@]}"
done
python3 scripts/run_fusion.py --runs "$W/runs/bm25.run" "$W/runs/e5.run" --tag bm25+e5 --out "$W/runs/bm25+e5.run"
python3 scripts/run_fusion.py --runs "$W/runs/bm25.run" "$W/runs/specter2.run" --tag bm25+specter2 --out "$W/runs/bm25+specter2.run"
RUNS="$W/runs/bm25.run $W/runs/e5.run $W/runs/specter2.run $W/runs/bm25+e5.run $W/runs/bm25+specter2.run"
python3 scripts/run_overlap.py --runs $RUNS --topics $T --out "$W/results" --tables "$W/tables"
python3 scripts/make_pool.py --runs $RUNS --topics $T --corpus "$W/corpus.jsonl" \
  --annotators Suraj Tejas Swayam Saksham --out "$W/judging" | head -12
python3 tests/simulate_judges.py "$W/judging" "$W/exports"
python3 scripts/merge_judgments.py --exports "$W/exports/*.json" --out "$W/qrels" --corpus "$W/corpus.jsonl" || true
python3 scripts/merge_judgments.py --exports "$W/exports/*.json" --out "$W/qrels" --fallback lower
cp "$W/qrels/qrels.preliminary-lower.txt" "$W/qrels/qrels.txt"
python3 scripts/evaluate.py --qrels "$W/qrels/qrels.txt" --topics $T --runs $RUNS --out "$W/results" \
  --tables "$W/tables" --figures "$W/figures" --n-perm 2000
python3 scripts/bm25_sweep.py --corpus "$W/corpus.jsonl" --topics $T --qrels "$W/qrels/qrels.txt" \
  --out "$W/results" --figures "$W/figures" --tables "$W/tables" | tail -12
python3 scripts/tokenizer_ablation.py --corpus "$W/corpus.jsonl" --topics $T --qrels "$W/qrels/qrels.txt" \
  --out "$W/results" --tables "$W/tables" --runs-dir "$W/runs/ablation"
python3 scripts/stretch_time_filter.py --run "$W/runs/bm25+e5.run" --corpus "$W/corpus.jsonl" --topics $T \
  --out "$W/runs/bm25+e5+time.run"
python3 scripts/stretch_cc_fusion.py --lexical "$W/runs/bm25.run" --dense "$W/runs/e5.run" --topics $T \
  --qrels "$W/qrels/qrels.txt" --out "$W/runs/cc-bm25+e5.run" | head -8
python3 scripts/stretch_rerank.py --run "$W/runs/bm25+e5.run" --corpus "$W/corpus.jsonl" --topics $T \
  --out "$W/runs/ce.run" --model "$TINY/base" --depth 20
python3 scripts/make_pool.py --runs "$W/runs/ce.run" "$W/runs/bm25+e5+time.run" --topics $T --corpus "$W/corpus.jsonl" \
  --annotators Suraj Tejas Swayam Saksham --out "$W/judging_round2" --already-judged "$W/qrels/qrels.txt" --round extra | head -6
echo "SMOKE TEST OK"
