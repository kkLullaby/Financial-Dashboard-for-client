#!/bin/bash
# ====================================
# 保持 Streamlit 运行 (被杀后自动重启)
# ====================================

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/streamlit_watchdog.log"

log_msg() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_msg "🚀 Streamlit Watchdog 已启动"

while true; do
    if ! pgrep -f "streamlit.*app.py" > /dev/null; then
        log_msg "⚠️ Streamlit 未运行，正在启动..."
        cd "$APP_DIR"
        nohup streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --browser.gatherUsageStats false > /tmp/streamlit_app.log 2>&1 &
        sleep 5
    else
        log_msg "✅ Streamlit 运行中"
    fi
    sleep 30
done