#!/bin/bash
cd /root/.openclaw/workspace/finance_workspace/low_latency_ver
exec /usr/local/bin/streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false