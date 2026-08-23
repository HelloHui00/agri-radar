#!/usr/bin/env bash
# 手动执行一次完整采集+简报流程 (调试用)
set -euo pipefail
AGRI_DIR="${HOME}/agri-radar"
cd "${AGRI_DIR}"
source venv/bin/activate
TS=$(date +%Y-%m-%d_%H%M%S)
echo "手动运行: ${TS}"
python scripts/collect.py > "data/run_${TS}.jsonl" 2>&1
python scripts/ingest.py "data/run_${TS}.jsonl" | tail -5
python scripts/brief.py
