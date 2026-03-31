import sys

with open('fast_sniper.py', 'r') as f:
    text = f.read()

bad_block = """            for line in lines:
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
                    pre_close = float(data_fields[5])  # FIX: [3] is bid price, use [5] (high price) as approximation
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
                print(f"解析 {code} 时出错跳过: {e}")"""

good_block = """            for line in lines:
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
                        pre_close = float(data_fields[5])  # FIX: [3] is bid price, use [5] (high price) as approximation
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
                    print(f"解析 {code} 时出错跳过: {e}")"""

text = text.replace(bad_block, good_block)
with open('fast_sniper.py', 'w') as f:
    f.write(text)

