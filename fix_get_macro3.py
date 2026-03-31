with open('fast_sniper.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_func = """def get_macro_data():
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
            str_lines = response.text.strip().split('\\n')
            
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
"""

start_idx = 0
end_idx = 0
for i, line in enumerate(lines):
    if line.startswith('def get_macro_data()'):
        start_idx = i
    if line.startswith('def main()'):
        end_idx = i

if start_idx < end_idx:
    final_lines = lines[:start_idx] + [new_func, '\n'] + lines[end_idx:]
    with open('fast_sniper.py', 'w', encoding='utf-8') as f:
        f.writelines(final_lines)
