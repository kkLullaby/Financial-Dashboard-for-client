import json
import os
import time
import requests
import pandas as pd
from pytdx.hq import TdxHq_API
import os
import time

# while True:
#     print("正在抓取最新盘口切片...")
#     # 调用你的快照脚本
#     os.system("python3 fast_sniper.py")
    
#     # 休息 3 秒，避免被新浪或通达信服务器封 IP
#     time.sleep(15)

# ==========================================
# 1. 动态路径配置 (彻底解决本地与云端路径切换问题)
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 读取雷达脚本生成的本地 json
HOT_POOL_PATH = os.path.join(DATA_DIR, "sector_radar.json")
# 狙击手最终生成的分析数据
MARKET_DATA_PATH = os.path.join(DATA_DIR, "fast_sniper_data.json")

TDX_SERVERS = [
    {'name': '上证云成都电信一', 'ip': '218.6.170.47', 'port': 7709},
    {'name': '上证云北京联通一', 'ip': '123.125.108.14', 'port': 7709},
    {'name': '上海电信主站Z1', 'ip': '180.153.18.170', 'port': 7709},
]

def format_tdx_code(code: str):
    """将标准代码转为 PyTDX 市场格式，并带有防弹清洗逻辑"""
    code = code.lower().strip()
    
    # 1. 暴力提取纯数字部分，把 'bj', 'sh', 'sz' 全部扒掉
    pure_code = ''.join(filter(str.isdigit, code))
    if len(pure_code) != 6:
        return None  # 如果提取后不是6位数字，直接当废点扔掉
        
    # 2. 根据前缀或号段精准匹配市场 ID
    # 沪市 (1)
    if code.startswith('sh') or pure_code.startswith(('60', '68')):
        return (1, pure_code)
    # 深市 (0)
    elif code.startswith('sz') or pure_code.startswith(('00', '30')):
        return (0, pure_code)
    # 北交所 (2)
    elif code.startswith('bj') or pure_code.startswith(('4', '8', '9')):
        return (2, pure_code)
        
    # 兜底给深市
    return (0, pure_code)

def get_macro_data():
    """通过新浪底层接口极速获取宏观先行指标 (自动计算并拼接涨跌幅)"""
    print("正在拉取全球宏观先行指标...")
    start_time = time.time()
    
    url = "https://hq.sinajs.cn/list=fx_susdcnh,hf_GC,hf_CL,nf_T0,nf_TL0"
    
    headers = {
        'Referer': 'https://finance.sina.com.cn',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    macro_result = {}
    try:
        response = requests.get(url, headers=headers, timeout=2)
        response.raise_for_status()
        lines = response.text.strip().split('\n')
        
        for line in lines:
            if not line or '=' not in line: continue
            name_part, data_part = line.split('=')
            code = name_part.split('_')[-1]
            data_fields = data_part.strip('";').split(',')
            
            try:
                price = 0.0
                pre_close = 0.0
                
                # 1. 离岸人民币 (Sina 外汇格式: [1]是最新, [3]是昨收)
                if code == 'susdcnh':
                    price = float(data_fields[1])
                    pre_close = float(data_fields[3])
                    key = 'USD/CNH'
                    
                # 2. 外盘期货 (Sina 国际期货格式: [0]是最新, [7]是昨收)
                elif code in ['GC', 'CL']:
                    price = float(data_fields[0])
                    pre_close = float(data_fields[7])
                    key = f'Global_{code}'
                    
                # 3. 内盘期货 (Sina 国内期货格式: [3]是最新, [0]是昨收)
                # 字段实测: [0]=昨收, [1]=开盘, [2]=最低, [3]=最新, [4]=成交量, [5]=成交额(万元), [6]=持仓量
                elif code in ['T0', 'TL0']:
                    latest_price = float(data_fields[3]) if len(data_fields) > 3 else 0.0
                    pre_close = float(data_fields[0]) if len(data_fields) > 0 else 0.0
                    price = latest_price if latest_price > 0 else pre_close
                    key = f'CN_Bond_{code}'
                else:
                    continue
                    
                # 🎯 核心计算逻辑：算出涨跌幅
                if pre_close > 0:
                    pct_chg = (price - pre_close) / pre_close * 100
                else:
                    pct_chg = 0.0
                    
                # 拼接方向箭头与百分比符号
                sign = "↑" if pct_chg > 0 else ("↓" if pct_chg < 0 else "-")
                
                # 格式化输出 (汇率保留4位小数，其他保留3位小数)
                if 'susdcnh' in code:
                    formatted_str = f"{price:.4f} ({sign} {pct_chg:+.2f}%)"
                else:
                    formatted_str = f"{price:.3f} ({sign} {pct_chg:+.2f}%)"
                    
                macro_result[key] = formatted_str
                
            except Exception as e:
                print(f"解析 {code} 时出错跳过: {e}")
                
        elapsed = (time.time() - start_time) * 1000
        print(f"✅ 宏观指标获取完成，耗时: {elapsed:.2f} ms")
    except Exception as e:
        print(f"⚠️ 宏观数据获取失败 (可能是网络波动): {e}")
        
    return macro_result

def main():
    start_time = time.time()
    
    # --- 步骤 0: 并行拉取宏观数据 ---
    macro_data = get_macro_data()
    
    # --- 步骤 1: 瞬间加载预设池 ---
    try:
        with open(HOT_POOL_PATH, 'r', encoding='utf-8') as f:
            hot_pool = json.load(f)
    except FileNotFoundError:
        print(f"⚠️ 未找到雷达数据，使用空数据池回退进行测试。")
        hot_pool = {"candidate_stocks": [], "my_stocks": [], "news": "No news."}
        
    # 安全提取数据，防止 key 不存在
    candidates = hot_pool.get('candidate_stocks', [])
    my_stocks = hot_pool.get('my_stocks', [])
    news = hot_pool.get('news', '')

    # ⚠️ 候选池为空（雷达成份股接口维护中）时，用当日涨停板股票作紧急替代监控池
    if not candidates:
        zt_details = hot_pool.get('market_summary', {}).get('top_zt_sector_details', {})
        zt_codes = []
        for stocks in zt_details.values():
            for s in stocks:
                code = str(s.get('code', '')).zfill(6)
                if code.startswith(('60', '68')):
                    zt_codes.append('sh' + code)
                elif code.startswith(('00', '30')):
                    zt_codes.append('sz' + code)
                elif code.startswith(('4', '8', '9')):
                    zt_codes.append('bj' + code)
        if zt_codes:
            candidates = list(dict.fromkeys(zt_codes))  # 去重保序
            print(f"⚠️ 候选池为空，回落至当日涨停板股票 {len(candidates)} 只作为监控池")

    all_codes = list(set(candidates + my_stocks))
    if not all_codes:
        print("⚠️ 股票池为空，直接退出。")
        return
        
    query_list = [format_tdx_code(c) for c in all_codes]
    
    # --- 步骤 2: PyTDX 闪电直连与容错轮询 ---
    api = TdxHq_API(auto_retry=True)
    connected = False
    
    for server in TDX_SERVERS:
        print(f"尝试连接 {server['name']} ({server['ip']})...", end="")
        try:
            if api.connect(server['ip'], server['port']):
                print(" ✅ 成功")
                connected = True
                break
        except Exception:
            print(" ❌ 超时")
            
    if not connected:
        print("🚨 所有行情服务器均连接失败，请检查网络或关闭代理！")
        return
        
    # --- 步骤 3: 批量快照请求 (分块拉取，突破 80 只限制) ---
    quotes = []
    try:
        # 每次最多请求 80 只股票 (PyTDX 底层硬性限制)
        chunk_size = 80
        for i in range(0, len(query_list), chunk_size):
            chunk = query_list[i:i + chunk_size]
            q = api.get_security_quotes(chunk)
            if q:
                quotes.extend(q)
    finally:
        api.disconnect() # 确保连接被释放
        
    if not quotes:
        print("⚠️ 未获取到行情数据，可能是请求被服务器拒绝。")
        return
        
    # --- 步骤 4: Pandas 内存极速过滤 ---
    df = pd.DataFrame(quotes)
    
    df['pct_chg'] = df.apply(
        lambda row: (row['price'] - row['last_close']) / row['last_close'] * 100 if row['last_close'] > 0 else 0, 
        axis=1
    )
    def restore_code(row):
        prefix = 'sh' if row['market'] == 1 else 'sz'
        return f"{prefix}{row['code']}"
        
    df['stock_code'] = df.apply(restore_code, axis=1)
    df['is_holding'] = df['stock_code'].isin(my_stocks)
    
    # 计算主动买盘占比
    df['buy_vol_ratio'] = df.apply(
        lambda row: (row['b_vol'] / row['vol'] * 100) if row['vol'] > 0 else 0, 
        axis=1
    )
    
    # 硬逻辑过滤
    mask_holding = df['is_holding'] == True
    # 候选股额外要求：实时涨跌幅 > 3%（排除假强 / 路았 股）
    mask_filtered = (df['is_holding'] == False) & (df['vol'] > 0) & (df['buy_vol_ratio'] > 50.0) & (df['pct_chg'] > 3.0)
    
    df_final = df[mask_holding | mask_filtered]
    
    # --- 步骤 5: 数据组装与落盘 ---
    result = {
        "timestamp": time.time(),
        "macro_indicators": macro_data,  # 🚀 这里注入了刚刚抓取的宏观指标
        "news_catalyst": news,
        "valid_targets": df_final[['stock_code', 'price', 'pct_chg', 'vol', 'buy_vol_ratio', 'is_holding']].to_dict(orient='records')
    }
    
    # 数据落盘
    try:
        with open(MARKET_DATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"📁 狙击手数据已写入: {MARKET_DATA_PATH}")
    except Exception as e:
        print(f"写入失败: {e}")
        with open(os.path.join(DATA_DIR, 'market_data_fallback.json'), 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start_time
    print(f"⚡ 狙击手脚本全流程耗时 (含宏观): {elapsed*1000:.2f} ms")

if __name__ == '__main__':  
    main()