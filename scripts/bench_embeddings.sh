#!/usr/bin/env bash
# Overnight: install what is missing, index the corpus with each model, score
# every model against both labelled sets, write the comparison.
#
#   ./scripts/bench_embeddings.sh
#
# Resumable. An index already built is skipped, so re-running after a crash
# costs only the step it died in. Read data/embedding_bench.json in the morning.
set -uo pipefail
cd "$(dirname "$0")/.."
LOG="data/embedding_bench.log"

echo "=== started $(date) ===" | tee -a "$LOG"

if ! .venv/bin/python -c "import sentence_transformers" 2>/dev/null; then
  echo "installing sentence-transformers (this is the slow network step)" | tee -a "$LOG"
  .venv/bin/pip install -q sentence-transformers 2>&1 | tail -5 | tee -a "$LOG"
fi

.venv/bin/python scripts/bench_embeddings.py "$@" 2>&1 | tee -a "$LOG"

echo "=== finished $(date) ===" | tee -a "$LOG"
echo
echo "results: data/embedding_bench.json"
