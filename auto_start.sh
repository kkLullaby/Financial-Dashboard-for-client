#!/bin/bash
# ====================================
# 自动启动量化看板服务
# 每天交易时段自动运行
# ====================================

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/auto_start_stock.log"

log_msg() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 检查是否已有进程运行
if pgrep -f "streamlit.*app.py" > /dev/null; then
    log_msg "服务已在运行中，跳过启动"
    exit 0
fi

log_msg "🚀 启动量化看板服务..."

# 启动 Streamlit
cd ${APP_DIR}
nohup streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --browser.gatherUsageStats false > /tmp/streamlit_app.log 2>&1 &
STREAM_PID=$!
sleep 5

# 启动 Cloudflare Tunnel
nohup cloudflared tunnel --url http://localhost:8501 --loglevel info > /tmp/cloudflared_streamlit.log 2>&1 &
TUNNEL_PID=$!
sleep 8

# 获取 Tunnel URL
sleep 3
TUNNEL_URL=$(grep -o 'https://[^ ]*\.trycloudflare\.com' /tmp/cloudflared_streamlit.log | head -1)

if [ -n "$TUNNEL_URL" ]; then
    echo "${TUNNEL_URL}" > ${APP_DIR}/tunnel_url.txt
    log_msg "✅ 服务已启动: ${TUNNEL_URL}"
else
    log_msg "⚠️ Tunnel URL 获取失败"
fi