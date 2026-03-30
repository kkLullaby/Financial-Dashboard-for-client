#!/bin/bash
# ====================================
# 开盘期间每8秒运行fast_sniper.py
# ====================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/fast_sniper_loop.log"
PID_FILE="/tmp/fast_sniper_loop.pid"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检查是否已运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo -e "${YELLOW}脚本已在运行中 (PID: $OLD_PID)${NC}"
        exit 0
    fi
fi

echo $$ > "$PID_FILE"

log_msg() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 判断是否在开盘时间内
is_trading_time() {
    local now=$(date +%H%M%S)
    local now_val=$(echo "$now" | sed 's/^0//' | sed 's/^0//')
    
    # 上午盘: 9:30:00 - 11:30:00
    if [ "$now" -ge 93000 ] && [ "$now" -le 113000 ]; then
        return 0
    fi
    # 下午盘: 13:00:00 - 15:00:00
    if [ "$now" -ge 130000 ] && [ "$now" -le 150000 ]; then
        return 0
    fi
    return 1
}

log_msg "🚀 启动快速狙击监控 (每8秒)"

# 主循环
while true; do
    # 控制日志文件大小在5MB以内（约50000行）
    if [ $(wc -l < "$LOG_FILE" 2>/dev/null || echo 0) -gt 50000 ]; then
        tail -n 10000 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
    fi
    if is_trading_time; then
        cd "$SCRIPT_DIR"
        python3 fast_sniper.py >> "$LOG_FILE" 2>&1
        log_msg "✅ 执行完成，等待8秒..."
        sleep 8
    else
        log_msg "⏰ 非交易时间，等待30秒检查..."
        sleep 30
    fi
done