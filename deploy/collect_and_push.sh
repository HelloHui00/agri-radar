#!/usr/bin/env bash
# systemd service 调用的主入口：采集 → 入库 → LLM 筛选 → 写简报 → 推飞书
set -euo pipefail

AGRI_DIR="${HOME}/agri-radar"
cd "${AGRI_DIR}"
source venv/bin/activate

TS=$(date +%Y-%m-%d_%H%M%S)
DATE=$(date +%Y-%m-%d)

echo "=== [${TS}] 开始采集 ==="
python scripts/collect.py > "data/run_${TS}.jsonl" 2>> logs/collect_err.log
python scripts/ingest.py "data/run_${TS}.jsonl" >> logs/ingest.log

echo "=== [${TS}] 开始 LLM 筛选与简报生成 ==="
python scripts/brief.py > "logs/brief_${TS}.log" 2>&1

BRIEF_PATH="output/brief_${DATE}.md"
if [ -f "${BRIEF_PATH}" ]; then
    echo "=== [${TS}] 推送飞书 ==="
    python scripts/feishu_push.py "${BRIEF_PATH}"
else
    echo "错误：简报文件 ${BRIEF_PATH} 未生成"
    exit 1
fi

echo "=== [${TS}] 完成 ==="
