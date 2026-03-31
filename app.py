import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import os
import akshare as ak
import altair as alt
import re  # 👈 新增：用于正则提取大盘成交额
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

def _render_scrollable_chart(chart, chart_width: int, height: int = 415):
    """将 Altair 图表渲染在横向可滚动容器内，底部显示灰色原生风格滚动条。"""
    spec_json = json.dumps(chart.to_dict())
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
* {{box-sizing:border-box;margin:0;padding:0;}}
body {{background:transparent;overflow:hidden;}}
#sw {{width:100%;overflow-x:auto;overflow-y:hidden;text-align:center;}}
#sw::-webkit-scrollbar {{height:10px;}}
#sw::-webkit-scrollbar-track {{background:#e8e8e8;border-radius:5px;}}
#sw::-webkit-scrollbar-thumb {{background:#aaaaaa;border-radius:5px;}}
#sw::-webkit-scrollbar-thumb:hover {{background:#777;}}
#vis {{display:inline-block; margin:0 auto; text-align:left;}}
.vega-embed summary {{display:none;}}
</style></head><body>
<div id="sw"><div id="vis"></div></div>
<script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
<script>
vegaEmbed('#vis',{spec_json},{{actions:false,renderer:'canvas'}}).catch(console.error);
</script></body></html>"""
    components.html(html, height=height, scrolling=False)

# ==========================================
# 0. 全局配置与自动刷新
# ==========================================
st.set_page_config(page_title="量化狙击大屏", page_icon="📈", layout="wide")
st_autorefresh(interval=3000, limit=None, key="data_refresh")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ==========================================
# 1. 智能缓存：名称映射
# ==========================================
@st.cache_data(ttl=86400)
def load_stock_names():
    """
    双层名称映射缓存:
    - 优先层: radar_stock_names.json (板块专用 ~888只)
    - 备份层: stock_names.json (全市场 ~5491只)
    - 兜底层: 返回原始代码
    """
    # 第一层: 优先从雷达股缓存加载
    radar_path = os.path.join(BASE_DIR, "data", "radar_stock_names.json")
    try:
        if os.path.exists(radar_path):
            with open(radar_path, 'r', encoding='utf-8') as f:
                radar_map = json.load(f)
                if radar_map:
                    print(f"📦 加载板块专用名称库: {len(radar_map)} 只")
    except Exception as e:
        radar_map = {}
    
    # 第二层: 加载全量备份
    full_path = os.path.join(BASE_DIR, "data", "stock_names.json")
    try:
        if os.path.exists(full_path):
            with open(full_path, 'r', encoding='utf-8') as f:
                full_map = json.load(f)
                if full_map:
                    print(f"📦 加载全量名称库: {len(full_map)} 只")
    except Exception as e:
        full_map = {}
    
    # 合并: 优先用雷达股名称，全量作为兜底
    if radar_map:
        # 用全量补充雷达库中没有的
        for code, name in full_map.items():
            if code not in radar_map:
                radar_map[code] = name
        return radar_map
    elif full_map:
        return full_map
    else:
        return {}

name_map = load_stock_names()

# 加载 volume_cache 获取 THS 全市场成交额
VOLUME_CACHE_PATH = os.path.join(os.path.dirname(__file__), "data/volume_cache.json")
def load_volume_cache():
    if 'last_volume_cache' not in st.session_state:
        st.session_state['last_volume_cache'] = {}
    try:
        if os.path.exists(VOLUME_CACHE_PATH):
            with open(VOLUME_CACHE_PATH, 'r') as f:
                data = json.load(f)
                st.session_state['last_volume_cache'] = data
                return data
    except:
        pass
    return st.session_state['last_volume_cache']


def get_realtime_sina_total() -> float:
    """当日全市场实时成交额（亿元，Sina 板块汇总）"""
    try:
        df = ak.stock_sector_spot()
        if df is not None and not df.empty and '总成交额' in df.columns:
            return pd.to_numeric(df['总成交额'], errors='coerce').fillna(0).sum() / 1e8
    except:
        pass
    return 0.0

# ==========================================
# 2. 动态读取长短双周期数据源
# ==========================================
DATA_PATH = os.path.join(BASE_DIR, "data", "fast_sniper_data.json")
RADAR_PATH = os.path.join(BASE_DIR, "data", "sector_radar.json")

if 'last_metrics_data' not in st.session_state:
    st.session_state['last_metrics_data'] = {"valid_targets": [], "macro_indicators": {}}
if 'last_radar_data' not in st.session_state:
    st.session_state['last_radar_data'] = {}

try:
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        st.session_state['last_metrics_data'] = data
except: 
    data = st.session_state['last_metrics_data']

try:
    with open(RADAR_PATH, 'r', encoding='utf-8') as f:
        radar_data = json.load(f)
        st.session_state['last_radar_data'] = radar_data
    hot_sectors = radar_data.get("strong_sectors", [])
    candidate_sector_map = radar_data.get("candidate_sector_map", {})
    full_sector_map_raw = radar_data.get("full_sector_map", {})
    real_market_ratios = radar_data.get("sector_ratios", {})
    sector_amounts = radar_data.get("sector_amounts", {})  # 板块实时成交额（万元）
    market_summary = radar_data.get("market_summary", {})
except:
    radar_data = st.session_state['last_radar_data']
    hot_sectors = radar_data.get("strong_sectors", [])
    candidate_sector_map = radar_data.get("candidate_sector_map", {})
    full_sector_map_raw = radar_data.get("full_sector_map", {})
    real_market_ratios = radar_data.get("sector_ratios", {})
    sector_amounts = radar_data.get("sector_amounts", {})
    market_summary = radar_data.get("market_summary", {})

def normalize_stock_code(code):
    pure_code = ''.join(filter(str.isdigit, str(code)))
    return pure_code.zfill(6) if pure_code else ""

def get_mtime_str(path):
    try:
        return datetime.fromtimestamp(os.path.getmtime(path)).strftime("%m-%d %H:%M:%S")
    except:
        return "未知"

# 合并两张映射表（full_sector_map 覆盖面更广，优先用来展示归属）
# candidate_sector_map 只包含 top-50% 候选股，full_sector_map 包含所有板块成员
# 重要修复：full_sector_map 的 key 可能是 "sh600489" 或 "600489" 格式，需要同时存储
sector_map = {}
for k, v in candidate_sector_map.items():
    n = normalize_stock_code(k)
    if n:
        sector_map[n] = v
    # 同时存储原始格式
    if k not in sector_map:
        sector_map[k] = v
        
for k, v in full_sector_map_raw.items():
    n = normalize_stock_code(k)
    if n and n not in sector_map:
        sector_map[n] = v
    # 同时存储原始格式（避免丢失 sh/sz 前缀的数据）
    if k not in sector_map:
        sector_map[k] = v

# 把 hot_sectors 转成 set 用于快速校验
hot_sectors_set = set(hot_sectors)



# ==========================================
# 3. 数据清洗与计算
# ==========================================
raw_df = pd.DataFrame(data.get("valid_targets", []))
macro = data.get("macro_indicators", {})

if not raw_df.empty:
    raw_df['amount_w'] = raw_df['vol'] * raw_df['price'] / 100
    if 'name' in raw_df.columns:
        raw_df['证券名称'] = raw_df['name'].fillna(raw_df['stock_code'].map(name_map)).fillna(raw_df['stock_code'])
    else:
        raw_df['证券名称'] = raw_df['stock_code'].map(name_map).fillna(raw_df['stock_code'])

    # sector_map 已在初始化阶段由 full_sector_map 与 candidate_sector_map 合并构建。
    # 如果仍有活跃股未命中（雷达数据陈旧或个股未通过其它途径分配），则直接分配到“🔥 独立逻辑/其他异动”

    def get_real_sector(row):
        pure_code = normalize_stock_code(row['stock_code'])
        if pure_code in sector_map: return sector_map[pure_code]
        if row['is_holding']: return "🛡️ 重点持仓板块"
        return "🔥 独立逻辑/其他异动"
    raw_df['板块名称'] = raw_df.apply(get_real_sector, axis=1)
else:
    raw_df = pd.DataFrame(columns=['stock_code', '证券名称', 'price', 'pct_chg', 'amount_w', 'buy_vol_ratio', '板块名称'])

# ==========================================
# 模块①：板块成交分析
# ==========================================
st.markdown("### 📊 表①：板块资金流向分析")

available_sectors = raw_df['板块名称'].unique().tolist() if not raw_df.empty else []

# 下拉仅展示“真实核心板块”(来自 sector_radar strong_sectors)
# 不再限制为当前有数据的板块，避免只剩 1-2 个选项。
real_core_sectors = list(dict.fromkeys(hot_sectors)) if hot_sectors else []

# 若雷达暂时异常，兜底使用当前活跃数据中的板块
if not real_core_sectors:
    real_core_sectors = [s for s in available_sectors if s not in ["🛡️ 重点持仓板块", "🔥 独立逻辑/其他异动"]]

# 按全市场成交占比 (Liquidity Share) 从高到低排序
core_options = sorted(real_core_sectors, key=lambda s: real_market_ratios.get(s, 0), reverse=True)

all_label = "大盘前50%核心流动性池 (All)"
option_label_to_sector = {all_label: "ALL"}

for sector in core_options:
    ratio = real_market_ratios.get(sector)
    label = f"{sector} ({ratio:.2f}%)" if ratio is not None else f"{sector} (N/A)"
    option_label_to_sector[label] = sector

ordered_options = list(option_label_to_sector.keys())

sniper_time = get_mtime_str(DATA_PATH)
radar_time = get_mtime_str(RADAR_PATH)

col_sel1, col_sel2, col_sel3 = st.columns([1, 2, 1])
with col_sel1:
    st.caption("🔫 fast_sniper 更新")
    st.code(sniper_time, language=None)
with col_sel2:
    selected_label = st.selectbox("选择板块", ordered_options)
    selected_sector = option_label_to_sector.get(selected_label, "ALL")
with col_sel3:
    st.caption("📡 sector_radar 更新")
    st.code(radar_time, language=None)

# 💥 核心修复：这里的判断字符串必须和下拉框里的选项一模一样
if selected_sector == "ALL":
    curr_df = raw_df.copy()
else:
    # 选中板块后，展示该板块按成交额前 50% 的个股
    # 前 50% 采用累积成交额占比达 50% 的最小股票集合（参照全市场板块筛选逻辑）
    sector_df = raw_df[raw_df['板块名称'] == selected_sector].copy()
    if not sector_df.empty:
        sector_df = sector_df.sort_values(by='amount_w', ascending=False).reset_index(drop=True)
        sector_total = sector_df['amount_w'].sum()
        if sector_total > 0:
            sector_df['_cumsum_r'] = sector_df['amount_w'].cumsum() / sector_total
            # 找到累积占比首次达到 50% 的行，不足 2 只则全显
            over50 = sector_df[sector_df['_cumsum_r'] >= 0.5]
            cutoff = over50.index[0] if not over50.empty else sector_df.index[-1]
            curr_df = sector_df.loc[:cutoff].drop(columns=['_cumsum_r']).copy()
        else:
            curr_df = sector_df.copy()
    else:
        curr_df = pd.DataFrame()

if not curr_df.empty:
    sector_amount_w = curr_df['amount_w'].sum()
    # 占比分母：单板块时用该板块全部真实成交额（Sina 实时），ALL 时用全市场合计
    if selected_sector != "ALL":
        _denom_w = sector_amounts.get(selected_sector, 0)
        if _denom_w == 0:  # 旧格式 JSON 兜底：用占比推算
            _srp = real_market_ratios.get(selected_sector, 0)
            _tm = sum(sector_amounts.values()) / 10000 if sector_amounts else 0
            if _srp > 0 and _tm > 0:
                _denom_w = _srp / 100 * _tm * 10000
        if _denom_w == 0:
            _denom_w = sector_amount_w  # 最终兜底
    else:
        _denom_w = sector_amount_w  # ALL 模式：占比相对于当前筛选股合计
    curr_df['sector_ratio'] = (curr_df['amount_w'] / _denom_w) * 100 if _denom_w > 0 else 0
    curr_df = curr_df.sort_values(by='amount_w', ascending=False).reset_index(drop=True)
    curr_df.insert(0, '#', range(1, len(curr_df) + 1))
else:
    sector_amount_w = 0
# 全市场实时成交额：直接读取 volume_cache.json（去除装饰器缓存）
with open(VOLUME_CACHE_PATH) as _f:
    _vc = json.load(_f)
total_market_yi = _vc.get('realtime_total_yi', 0)
if not total_market_yi and sector_amounts:
    total_market_yi = sum(sector_amounts.values()) / 10000
if total_market_yi == 0:
    volume_status = market_summary.get("volume_status", "")
    match = re.search(r"(?:最新成交|实时成交)\s*(\d+)", volume_status)
    if match:
        total_market_yi = float(match.group(1))
volume_status = market_summary.get("volume_status", "")

metric_col1, metric_col2 = st.columns(2)
with metric_col1:
    st.info(f"**选中项总成交额**\n\n### {sector_amount_w / 10000:.2f} 亿元")
    
with metric_col2:
    # 动态计算全市场占比并打上标签
    clean_sector_name = selected_sector.replace("🛡️ ", "").replace("🔥 ", "")
    
    if clean_sector_name in real_market_ratios:
        # 如果选的是真实的板块 (如: 储能) -> 显示该板块在全市场的宏观占比
        display_ratio = f"{real_market_ratios[clean_sector_name]:.2f}% (全板块)"
    else:
        # 如果选的是 "All" 或 "持仓" -> 实时计算当前表格里的股票抽走了全市场多少资金
        if total_market_yi > 0:
            ratio = (sector_amount_w / 10000) / total_market_yi * 100
            display_ratio = f"{ratio:.3f}% (当前股池)"
        else:
            display_ratio = "等待雷达更新..."
            
    st.info(f"**占全市场成交比例**\n\n### {display_ratio}")

if not curr_df.empty:
    display_df = curr_df[['#', 'stock_code', '证券名称', 'price', 'pct_chg', 'amount_w', 'sector_ratio', '板块名称']].copy()
    display_df.rename(columns={
        'stock_code': '证券代码', 'price': '现价', 'pct_chg': '涨跌幅 (%)',
        'amount_w': '成交额 (万元)', 'sector_ratio': '占比 (%)', '板块名称': '归属'
    }, inplace=True)
    
    st.dataframe(
        display_df,
        column_config={
            "#": st.column_config.NumberColumn(format="%d"),
            "涨跌幅 (%)": st.column_config.NumberColumn(format="%.2f%%"),
            "成交额 (万元)": st.column_config.NumberColumn(format="%.0f"),
            "占比 (%)": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100),
        },
        use_container_width=True, hide_index=True
    )

st.divider()

# ==========================================
# 模块②：数据可视化与简报
# ==========================================
chart_col, brief_col = st.columns([1.5, 1])

with chart_col:
    st.markdown("#### 📈 选中项资金分布")
    if not curr_df.empty:
        # ── 顶部控制栏：缩放 ➖/➕ + 模式切换（仅单板块时显示）──
        if 'chart_zoom' not in st.session_state:
            st.session_state['chart_zoom'] = 3
        if 'chart_mode' not in st.session_state:
            st.session_state['chart_mode'] = 'single'

        if selected_sector != "ALL":
            ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([1, 5, 1, 2])
        else:
            ctrl1, ctrl2, ctrl3 = st.columns([1, 7, 1])
            ctrl4 = None

        with ctrl1:
            if st.button("➖", key="zoom_out", help="缩小"):
                st.session_state['chart_zoom'] = max(1, st.session_state['chart_zoom'] - 1)
        with ctrl2:
            zoom_labels = ["极小", "小", "中", "大", "极大"]
            st.caption(f"缩放比例：{zoom_labels[st.session_state['chart_zoom'] - 1]}  （共 {len(curr_df)} 只股票）")
        with ctrl3:
            if st.button("➕", key="zoom_in", help="放大"):
                st.session_state['chart_zoom'] = min(5, st.session_state['chart_zoom'] + 1)
        if ctrl4 is not None:
            with ctrl4:
                mode = st.radio("图表模式", ["单柱", "双柱"], horizontal=True,
                                index=0 if st.session_state['chart_mode'] == 'single' else 1,
                                key="chart_mode_radio")
                st.session_state['chart_mode'] = 'single' if mode == "单柱" else 'double'

        zoom_steps = [22, 38, 55, 75, 105]
        bar_w = zoom_steps[st.session_state['chart_zoom'] - 1]

        # 准备数据：按成交额降序，用 | 拼接双行标签（名称 + 代码）
        chart_df = curr_df[['证券名称', 'stock_code', 'amount_w', 'pct_chg']].copy()
        chart_df = chart_df.sort_values('amount_w', ascending=False).reset_index(drop=True)
        chart_df['rank'] = range(1, len(chart_df) + 1)
        chart_df['label'] = chart_df['证券名称'] + '|' + chart_df['stock_code']
        chart_df['amount_yi'] = chart_df['amount_w'] / 10000  # 万元 → 亿元
        total_stocks = len(chart_df)

        # 双柱模式下每组占 2 倍宽，单柱 1 倍
        is_double = (selected_sector != "ALL" and st.session_state['chart_mode'] == 'double')
        slots_per_bar = 2 if is_double else 1

        # ALL 模式：排名范围筛选（过滤显示哪段排名，图表内滚动条负责导航）
        if selected_sector == "ALL" and total_stocks > 1:
            rng_col1, rng_col2 = st.columns([3, 1])
            with rng_col1:
                rank_range = st.slider(
                    "🔢 显示排名范围（按成交额）",
                    min_value=1, max_value=total_stocks,
                    value=(1, total_stocks), step=1, key="rank_range"
                )
            with rng_col2:
                st.caption(f"排名 {rank_range[0]}~{rank_range[1]}，共 {rank_range[1]-rank_range[0]+1} 只")
            view_df = chart_df.iloc[rank_range[0]-1 : rank_range[1]].copy()
        else:
            view_df = chart_df.copy()

        view_order = view_df['label'].tolist()
        chart_width = max(80, len(view_df) * bar_w * slots_per_bar)

        axis_cfg = alt.Axis(
            labelAngle=-45,
            labelExpr="split(datum.value, '|')",
            labelLimit=120,
            title=None
        )
        common_tt = [
            alt.Tooltip('证券名称:N', title='名称'),
            alt.Tooltip('stock_code:N', title='代码'),
            alt.Tooltip('amount_yi:Q', title='成交额(亿元)', format=',.3f'),
            alt.Tooltip('pct_chg:Q', title='涨跌幅(%)', format='.2f'),
            alt.Tooltip('rank:Q', title='排名'),
        ]

        if not is_double:
            # 单柱模式（ALL 及 单板块单柱）
            chart = alt.Chart(view_df).mark_bar(color='#d62728').encode(
                x=alt.X('label:N', sort=view_order, axis=axis_cfg),
                y=alt.Y('amount_yi:Q', title='成交额 (亿元)'),
                tooltip=common_tt
            ).properties(width=alt.Step(bar_w * slots_per_bar), height=340)
            _render_scrollable_chart(chart, chart_width)

            # 单板块单柱：补充板块总计文字
            if selected_sector != "ALL":
                sector_total_w = sector_amounts.get(selected_sector, 0)
                # 兑底：如果 sector_amounts 尚未写入旧 JSON，用占比 × 全市场总额估算
                if sector_total_w == 0:
                    _srp = real_market_ratios.get(selected_sector, 0)
                    if _srp > 0 and total_market_yi > 0:
                        sector_total_w = _srp / 100 * total_market_yi * 10000
                if sector_total_w > 0:
                    all_shown_total = curr_df['amount_w'].sum()
                    st.caption(
                        f"📊 **板块总计** {sector_total_w/10000:.1f}亿 ｜ "
                        f"全部筛选股合计 {all_shown_total/10000:.2f}亿（占板块 {all_shown_total/sector_total_w*100:.1f}%）"
                    )
        else:
            # 双柱模式：灰色板块总计柱 + 红色个股柱并列
            # 灰色柱 = 当前板块的全部成交额（Sina 实时）
            sector_total_w = sector_amounts.get(selected_sector, 0)  # 万元
            # 兑底：旧格式 JSON 没有 sector_amounts，用占比推算
            if sector_total_w == 0:
                _srp = real_market_ratios.get(selected_sector, 0)
                if _srp > 0 and total_market_yi > 0:
                    sector_total_w = _srp / 100 * total_market_yi * 10000
            rows = []
            for _, row in view_df.iterrows():
                rows.append({'label': row['label'], '类型': '个股成交',
                             '成交额(亿元)': row['amount_yi'],
                             '证券名称': row['证券名称'],
                             'stock_code': row['stock_code'],
                             'pct_chg': row['pct_chg'], 'rank': row['rank']})
                if sector_total_w > 0:
                    rows.append({'label': row['label'], '类型': '板块总计',
                                 '成交额(亿元)': sector_total_w / 10000,
                                 '证券名称': row['证券名称'],
                                 'stock_code': row['stock_code'],
                                 'pct_chg': 0.0, 'rank': row['rank']})
            melt_df = pd.DataFrame(rows)
            clr_scale = alt.Scale(domain=['个股成交', '板块总计'], range=['#d62728', '#aaaaaa'])
            tt_double = [
                alt.Tooltip('证券名称:N', title='名称'),
                alt.Tooltip('stock_code:N', title='代码'),
                alt.Tooltip('类型:N', title='类型'),
                alt.Tooltip('成交额(亿元):Q', title='成交额(亿元)', format=',.3f'),
                alt.Tooltip('pct_chg:Q', title='涨跌幅(%)', format='.2f'),
                alt.Tooltip('rank:Q', title='排名'),
            ]
            chart = alt.Chart(melt_df).mark_bar().encode(
                x=alt.X('label:N', sort=view_order, axis=axis_cfg),
                y=alt.Y('成交额(亿元):Q', title='成交额 (亿元)'),
                color=alt.Color('类型:N', scale=clr_scale,
                                legend=alt.Legend(orient='top-right', title=None)),
                xOffset=alt.XOffset('类型:N'),
                tooltip=tt_double
            ).properties(width=alt.Step(bar_w * slots_per_bar), height=340)
            _render_scrollable_chart(chart, chart_width)
            if sector_total_w > 0:
                all_shown_total = curr_df['amount_w'].sum()
                st.caption(
                    f"📊 **板块总计** {sector_total_w/10000:.1f}亿 ｜ "
                    f"全部筛选股合计 {all_shown_total/10000:.2f}亿（占板块 {all_shown_total/sector_total_w*100:.1f}%）"
                )

        st.markdown("#### 🎯 头部集中度")
        half_count = max(1, len(curr_df) // 2)
        top_half_amount = curr_df.head(half_count)['amount_w'].sum()
        concentration = (top_half_amount / sector_amount_w * 100) if sector_amount_w > 0 else 0
        st.progress(concentration / 100, text=f"前 50% 股票吸金占比: {concentration:.1f}%")

with brief_col:
    st.markdown("#### 📝 全局大盘摘要")
    st.markdown("---")
    
    top_zt = market_summary.get("top_zt_sectors", [])
    top_zt_details = market_summary.get("top_zt_sector_details", {})
    top_vol = market_summary.get("top_vol_sectors", [])
    
    # 市场量能：实时从 Sina 板块加总计算，30s 缓存
    # 直接读取 volume_cache.json（去除装饰器缓存）
    with open(VOLUME_CACHE_PATH) as _f2:
        _vc2 = json.load(_f2)
    rt_total = _vc2.get('realtime_total_yi', 0)
    # 备用: 如果 volume_cache 为空则尝试实时获取
    if rt_total == 0:
        rt_total = get_realtime_sina_total()
    if rt_total > 0:
        # 兼容"昨全天"（周二~周五）和"上周五"（周一）两种格式
        yest_m = re.search(r"(?:昨全天|上周五)\s*(\d+)", volume_status)
        if yest_m:
            yest = float(yest_m.group(1))
            diff = rt_total - yest
            vst = "🔥 资金放量" if diff > 0 else "📉 资金缩量"
            # 动态读取对比标签（昨全天 / 上周五）
            compare_label = re.search(r"(昨全天|上周五)", volume_status)
            compare_label = compare_label.group(1) if compare_label else "昨全天"
            display_volume = f"{vst} (实时 {rt_total:.0f}亿 / {compare_label} {yest:.0f}亿)"
        else:
            display_volume = f"📊 实时成交 {rt_total:.0f}亿"
    else:
        display_volume = volume_status if volume_status else "数据拉取中..."
    st.markdown(f"**1. 📊 市场量能**: `{display_volume}`")
    st.markdown("**2. 🚀 市场主线排名 (Top 5)**:")
    
    c1, c2 = st.columns(2)
    with c1:
        st.caption("[情绪阵地：涨停家数]")
        if top_zt:
            for sector, count in top_zt:
                details = top_zt_details.get(sector, [])
                if details:
                    names = [d.get("name", d.get("code")) for d in details[:5]]
                    names_str = "、".join(names) + ("..." if len(details)>5 else "")
                    st.markdown(f"**{sector}** `{count}家` \n<span style='font-size:0.8em;color:gray;'>{names_str}</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"**{sector}** `{count}家`")
        else:
            st.text("暂无数据/休市中")
            
    with c2:
        st.caption("[机构阵地：成交金额]")
        if top_vol:
            for sector, amount in top_vol: st.text(f"{sector} | {amount:.0f}亿")
        else:
            st.text("数据拉取中...")
    
    st.markdown("---")
    st.markdown("**🌐 宏观先行指标**")
    
    st.markdown(f"**3. 💱 美元/离岸人民币**: `{macro.get('USD/CNH', '数据未更新')}`")
    st.markdown(f"**4. 🪙 COMEX 黄金指数**: `{macro.get('Global_GC', '数据未更新')}`")
    st.markdown(f"**5. 🛢️ NYMEX 原油指数**: `{macro.get('Global_CL', '数据未更新')}`")
    st.markdown(f"**6. 🏦 十年期国债主连**: `{macro.get('CN_Bond_T0', '数据未更新')}`")
    st.markdown(f"**7. 🏦 三十年期国债主连**: `{macro.get('CN_Bond_TL0', '数据未更新')}`")