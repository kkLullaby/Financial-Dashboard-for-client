#!/bin/bash
# 狙击手循环脚本 - 每个交易时段循环执行
# 由 cron 每分钟触发

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$SCRIPT_DIR/data"

# 检查数据文件是否存在
if [ ! -f "$DATA_DIR/sector_radar.json" ]; then
    echo "⚠️ 雷达数据不存在，跳过执行"
    exit 0
fi

# 检查是否在交易时间
is_trading_time() {
    local now=$(date +%H%M%S)
    local now_num=$(echo "$now" | tr -d ':')
    
    # 上午: 09:30:00 - 11:30:00
    # 下午: 13:00:00 - 15:05:00 (含盘后结算)
    if [ "$now_num" -ge 93000 ] && [ "$now_num" -lt 113000 ]; then
        return 0
    elif [ "$now_num" -ge 130000 ] && [ "$now_num" -le 150500 ]; then
        return 0
    fi
    return 1
}

if ! is_trading_time; then
    echo "⏰ 非交易时间，退出"
    exit 0
fi

# 循环执行 12 次（每5秒 × 12 = 60秒，覆盖整分钟）
# 但只在当前分钟的交易时间段内运行
for i in {1..12}; do
    if ! is_trading_time; then
        echo "📊 交易时间结束，退出"
        break
    fi
    
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 执行第 $i 次..."
    cd "$SCRIPT_DIR" && python3 fast_sniper.py
    
    if [ $i -lt 12 ]; then
        sleep 5
    fi
done

echo "✅ 本轮执行完成"