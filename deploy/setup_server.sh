#!/usr/bin/env bash
# ============================================================
# agri-radar 境外服务器一键初始化脚本
# 目标系统：Ubuntu 22.04 LTS (阿里云国际轻量应用服务器)
# 用法：chmod +x setup_server.sh && sudo ./setup_server.sh
# ============================================================
set -euo pipefail

# ---------- 前提检查 ----------
if [ "$(id -u)" -ne 0 ]; then
    echo "错误：请用 root 或 sudo 运行"
    exit 1
fi

AGRI_USER="agri"
AGRI_HOME="/home/${AGRI_USER}"
AGRI_DIR="${AGRI_HOME}/agri-radar"
REPO_SOURCE="${1:-/tmp/agri-radar.tar.gz}"   # 你打包上传过来的代码

echo "=== [1/7] 系统依赖安装 ==="
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv sqlite3 curl git tzdata

# 时区设置为中国北京时间（服务器在境外也需要显示北京时间）
timedatectl set-timezone Asia/Shanghai

echo "=== [2/7] 创建专用用户 ==="
if ! id "${AGRI_USER}" &>/dev/null; then
    useradd -m -s /bin/bash "${AGRI_USER}"
    echo "用户 ${AGRI_USER} 已创建"
fi

echo "=== [3/7] 部署代码到 ${AGRI_DIR} ==="
if [ ! -f "${REPO_SOURCE}" ]; then
    echo "错误：没找到安装包 ${REPO_SOURCE}"
    echo "请先用 scp 把打包好的 agri-radar.tar.gz 传到 /tmp/"
    exit 1
fi
mkdir -p "${AGRI_DIR}"
tar -xzf "${REPO_SOURCE}" -C "${AGRI_DIR}" --strip-components=1
chown -R "${AGRI_USER}:${AGRI_USER}" "${AGRI_DIR}"

echo "=== [4/7] Python 虚拟环境 ==="
sudo -u "${AGRI_USER}" python3 -m venv "${AGRI_DIR}/venv"
sudo -u "${AGRI_USER}" "${AGRI_DIR}/venv/bin/pip" install -q --upgrade pip
# agri-radar 只用标准库，无需额外 pip install
echo "  -> 虚拟环境已创建于 ${AGRI_DIR}/venv"

echo "=== [5/7] 目录结构 & 初始化数据库 ==="
sudo -u "${AGRI_USER}" mkdir -p "${AGRI_DIR}"/{data,logs,output}
sudo -u "${AGRI_USER}" bash -c "cd ${AGRI_DIR} && venv/bin/python scripts/db.py && echo 'db initialized'"

echo "=== [6/7] 配置 systemd 定时任务 ==="
# 创建 systemd service 单元 (采集 + 简报)
cat > /etc/systemd/system/agri-radar-collect.service <<'EOF'
[Unit]
Description=agri-radar morning collector
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=agri
Group=agri
WorkingDirectory=/home/agri/agri-radar
Environment=AGRI_RADAR_DB=/home/agri/agri-radar/data/agri_radar.db
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/agri/agri-radar/deploy/collect_and_push.sh
StandardOutput=append:/home/agri/agri-radar/logs/systemd.log
StandardError=append:/home/agri/agri-radar/logs/systemd.log
EOF

cat > /etc/systemd/system/agri-radar-collect.timer <<'EOF'
[Unit]
Description=Daily agri-radar collection at 07:30 Beijing time

[Timer]
OnCalendar=07:30
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable agri-radar-collect.timer
systemctl start agri-radar-collect.timer
echo "  -> systemd timer 已启用，明天 07:30 CST 自动触发"

echo "=== [7/7] 配置 LLM API Key ==="
if [ -z "${LLM_API_KEY:-}" ]; then
    echo "警告：环境变量 LLM_API_KEY 未设置"
    echo "请执行："
    echo "  sudo -u ${AGRI_USER} bash -c 'echo \"export LLM_API_KEY=你的key\" >> ~/.bashrc'"
    echo "  sudo -u ${AGRI_USER} bash -c 'echo \"LLM_API_KEY=你的key\" >> ~/.profile'"
else
    sudo -u "${AGRI_USER}" bash -c "echo \"export LLM_API_KEY=${LLM_API_KEY}\" >> ~/.bashrc"
    sudo -u "${AGRI_USER}" bash -c "echo \"LLM_API_KEY=${LLM_API_KEY}\" >> ~/.profile"
    echo "  -> API key 已写入 ${AGRI_USER} 用户环境"
fi

echo ""
echo "============================================================"
echo "✅ 部署完成！"
echo "   代码目录: ${AGRI_DIR}"
echo "   定时器: systemctl status agri-radar-collect.timer"
echo "   手动跑采集: sudo -u ${AGRI_USER} ${AGRI_DIR}/deploy/manual_run.sh"
echo "   简报推送: 默认推到飞书群 (需配置 config/server.json 的 webhook)"
echo "============================================================"
