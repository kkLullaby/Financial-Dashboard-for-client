#!/bin/bash
# ====================================
# 启动量化狙击大屏 + Cloudflare Tunnel
# ====================================

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STREAMLOG="/tmp/streamlit_app.log"
TUNNEL_LOG="/tmp/cloudflared_streamlit.log"
TUNNEL_NAME="stock-quant-screen"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "======================================"
echo "🚀 启动量化狙击大屏 + Cloudflare Tunnel"
echo "======================================"

# 1. 停止旧进程
echo -e "${YELLOW}[1/4]${NC} 清理旧进程..."
pkill -f "streamlit run" 2>/dev/null && echo "  ✓ 已停止旧 Streamlit"
pkill -f "cloudflared.*8501" 2>/dev/null && echo "  ✓ 已停止旧 Tunnel"
sleep 2

# 2. 启动 Streamlit
echo -e "${YELLOW}[2/4]${NC} 启动 Streamlit 应用..."
cd "${APP_DIR}"
nohup streamlit run app.py --server.port 8501 --server.address 0.0.0.0 > "${STREAMLOG}" 2>&1 &
STREAM_PID=$!
sleep 5

if curl -s http://localhost:8501 > /dev/null; then
    echo -e "  ${GREEN}✓ Streamlit 已启动${NC} (PID: ${STREAM_PID})"
else
    echo -e "  ${YELLOW}⚠ Streamlit 启动中...${NC}"
    sleep 5
fi

# 3. 启动 Cloudflare Tunnel
echo -e "${YELLOW}[3/4]${NC} 启动 Cloudflare Tunnel..."
nohup cloudflared tunnel --url http://localhost:8501 --loglevel info > "${TUNNEL_LOG}" 2>&1 &
TUNNEL_PID=$!
sleep 8

# 4. 获取 Tunnel URL
echo -e "${YELLOW}[4/4]${NC} 获取公网地址..."
sleep 3
TUNNEL_URL=$(grep -o 'https://[^ ]*\.trycloudflare\.com' ${TUNNEL_LOG} | head -1)

echo ""
echo "======================================"
echo -e "${GREEN}✓ 服务已启动！${NC}"
echo "======================================"
echo ""
echo "📊 本地访问: http://localhost:8501"
echo "🌐 公网访问: ${TUNNEL_URL}"
echo ""
echo "📝 日志位置:"
echo "  • Streamlit: ${STREAMLOG}"
echo "  • Tunnel: ${TUNNEL_LOG}"
echo ""
echo "======================================"

# 保存 URL
echo "${TUNNEL_URL}" > "${APP_DIR}/tunnel_url.txt"echo "${TUNNEL_URL}" > "${APP_DIR}/tunnel_url.txt"
