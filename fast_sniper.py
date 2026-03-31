import json
import os
import time
import requests
import pandas as pd
from pytdx.hq import TdxHq_API
import threading
import signal

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

# 新浪行情接口超时设置
SINA_TIMEOUT = 3

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

def format_sina_code(code: str):
    """将标准代码转为新浪格式 (sh600000, sz000001)"""
    code = code.lower().strip()
    pure_code = ''.join(filter(str.isdigit, code))
    if len(pure_code) != 6:
        return None
    if pure_code.startswith(('60', '68', '5')):
        return f"sh{pure_code}"
    else:
        return f"sz{pure_code}"

def get_sina_quotes(codes):
    """通过新浪接口批量获取行情 (备用方案)"""
    if not codes:
        return []
    
    # 标准化codes
    sina_codes = []
    for c in codes:
        sc = format_sina_code(c)
        if sc:
            sina_codes.append(sc)
    
    if not sina_codes:
        return []
    
    results = []
    
    # 分批请求，每批30只
    batch_size = 30
    headers = {
        'Referer': 'https://finance.sina.com.cn',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for i in range(0, len(sina_codes), batch_size):
        batch = sina_codes[i:i + batch_size]
        url = f"https://hq.sinajs.cn/list={','.join(batch)}"
        
        try:
            resp = requests.get(url, headers=headers, timeout=SINA_TIMEOUT)
            resp.encoding = 'gbk'
            
            lines = resp.text.strip().split('\n')
            for line in lines:
                if '="' not in line:
                    continue
                left, right = line.split('="')
                stock_code = left.split('_')[-1]
                data_str = right.strip('";')
                data_parts = data_str.split(',')
                
                if len(data_parts) < 10:
                    continue
                
                try:
                    name = data_parts[0]
                    prev_close = float(data_parts[2]) if data_parts[2] and data_parts[2] != '-' else 0
                    price = float(data_parts[3]) if data_parts[3] and data_parts[3] != '-' else 0
                    vol = float(data_parts[8]) / 100 if len(data_parts) > 8 and data_parts[8] else 0
                    
                    # 计算涨跌幅
                    pct_chg = 0
                    if prev_close > 0:
                        pct_chg = (price - prev_close) / prev_close * 100
                    
                    # 市场ID
                    market = 1 if stock_code.startswith('sh') else 0
                    pure_code = stock_code[2:]
                    
                    results.append({
                        'code': pure_code,
                        'name': name,
                        'market': market,
                        'price': price,
                        'last_close': prev_close,
                        'vol': vol,
                        'b_vol': 0  # Sina不提供主动买入量
                    })
                except:
                    continue
        except:
            continue
    
    return results

def get_quote_with_timeout(api, stock_list, timeout_sec=2):
    """带超时的行情获取 (防止特定股票导致挂起)"""
    result = {'data': None, 'error': None}
    
    def _get():
        try:
            result['data'] = api.get_security_quotes(stock_list)
        except Exception as e:
            result['error'] = str(e)
    
    t = threading.Thread(target=_get)
    t.daemon = True
    t.start()
    t.join(timeout_sec)
    
    if t.is_alive():
        return None  # 超时返回None
    return result['data']

def get_macro_data():
    start_time = time.time()
    codes = "fx_susdcnh,hf_GC,hf_CL,nf_T0,nf_TL0"
    url = f"https://hq.sinajs.cn/list={codes}"
    headers = {
        'Referer': 'https://finance.sina.com.cn',
        'User-Agent': 'Mozilla/5.0'
    }
    
    macro_result = {}
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=2)
            response.raise_for_status()
            str_lines = response.text.strip().split('\n')
            
            for line in str_lines:
                if not line or '=' not in line: continue
                name_part, data_part = line.split('=')
                code = name_part.split('_')[-1]
                data_fields = data_part.strip('";').split(',')
                try:
                    price = 0.0
                    pre_close = 0.0
                    if code == 'susdcnh':
                        price = float(data_fields[1])
                        pre_close = float(data_fields[5])
                        key = 'USD/CNH'
                    elif code in ['GC', 'CL']:
                        price = float(data_fields[0])
                        pre_close = float(data_fields[7])
                        key = f'Global_{code}'
                    elif code in ['T0', 'TL0']:
                        latest_price = float(data_fields[3]) if len(data_fields) > 3 else 0.0
                        pre_close = float(data_fields[0]) if len(data_fields) > 0 else 0.0
                        price = latest_price if latest_price > 0 else pre_close
                        key = f'CN_Bond_{code}'
                    else:
                        continue
                    if pre_close > 0:
                        pct_chg = (price - pre_close) / pre_close * 100
                    else:
                        pct_chg = 0.0
                    sign = "↑" if pct_chg > 0 else ("↓" if pct_chg < 0 else "-")
                    if 'susdcnh' in code:
                        formatted_str = f"{price:.4f} ({sign} {pct_chg:+.2f}%)"
                    else:
                        formatted_str = f"{price:.3f} ({sign} {pct_chg:+.2f}%)"
                    macro_result[key] = formatted_str
                except Exception as e:
                    pass
            elapsed = (time.time() - start_time) * 1000
            print(f"✅ 宏观指标获取完成，耗时: {elapsed:.2f} ms")
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(0.5)
            else:
                pass
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
    candidates = hot_pool.get("candidate_stocks", [])
    # 兼容新格式({"code": xxx, "name": xxx})和旧格式("xxx")
    if candidates and isinstance(candidates[0], dict):
        candidates = [c.get("code", "") for c in candidates if c.get("code")]
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
    query_list = [q for q in query_list if q is not None]
    
    # --- 步骤 2: PyTDX 闪电直连与容错轮询 ---
    api = TdxHq_API(auto_retry=True)
    connected = False
    tdx_works = False
    
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
        
    # --- 步骤 3: 批量快照请求 (带超时保护) ---
    quotes = []
    try:
        chunk_size = 80
        for i in range(0, len(query_list), chunk_size):
            chunk = query_list[i:i + chunk_size]
            
            # 使用带超时的获取 (每只股票最多等待2秒)
            q = get_quote_with_timeout(api, chunk, timeout_sec=2)
            
            if q:
                quotes.extend(q)
            else:
                # TDX超时，标记失败，稍后用Sina备用
                print(f"  批次 {i//chunk_size + 1} TDX超时，切换至Sina备用...")
                tdx_works = False
                break
    finally:
        api.disconnect()
    
    # 如果TDX完全失败，使用Sina备用
    if not quotes:
        print("⚠️ TDX行情获取失败，启用新浪备用接口...")
        quotes = get_sina_quotes(all_codes)
        if quotes:
            print(f"✅ Sina备用接口获取成功，共 {len(quotes)} 条")
    
    if not quotes:
        print("⚠️ 未获取到任何行情数据。")
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
    
    # 计算主动买盘占比 (Sina数据b_vol=0，使用默认50)
    df['buy_vol_ratio'] = df.apply(
        lambda row: (row['b_vol'] / row['vol'] * 100) if row['vol'] > 0 and row.get('b_vol', 0) > 0 else 50.0, 
        axis=1
    )
    
    # 硬逻辑过滤
    mask_holding = df['is_holding'] == True
    # 候选股额外要求：实时涨跌幅 > 3%（排除假强股），买盘比 >= 50.0 (修复新浪备用数据被团灭的BUG)
    mask_filtered = (df['is_holding'] == False) & (df['vol'] > 0) & (df['buy_vol_ratio'] >= 50.0) & (df['pct_chg'] > 3.0)
    
    df_final = df[mask_holding | mask_filtered]
    
    # --- 步骤 5: 数据组装与落盘 ---
    export_cols = ['stock_code', 'price', 'pct_chg', 'vol', 'buy_vol_ratio', 'is_holding']
    if 'name' in df_final.columns:
        export_cols.append('name')
        
    result = {
        "timestamp": time.time(),
        "macro_indicators": macro_data,
        "news_catalyst": news,
        "valid_targets": df_final[export_cols].to_dict(orient='records')
    }
    
    # 数据落盘 (原子写入)
    try:
        tmp_path = MARKET_DATA_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, MARKET_DATA_PATH)
        print(f"📁 狙击手数据已写入: {MARKET_DATA_PATH}")
    except Exception as e:
        print(f"写入失败: {e}")
        with open(os.path.join(DATA_DIR, 'market_data_fallback.json'), 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start_time
    print(f"⚡ 狙击手脚本全流程耗时 (含宏观): {elapsed*1000:.2f} ms")

if __name__ == '__main__':  
    main()