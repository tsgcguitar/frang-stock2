import streamlit as st
import yfinance as yf
import pandas as pd
import random
import time
import twstock
from datetime import datetime
from supabase import create_client, Client

# --- 1. 初始化與 UI 樣式強化 ---
st.set_page_config(page_title="從從容容飆股王", layout="wide")

st.markdown("""
<style>
.stApp { background: linear-gradient(to bottom right, #001233, #000814); color: #E0F7FA; }
.stMarkdown, .stText, p, li, span, label, div { color: #FFFFFF !important; font-weight: 500; }
h1, h2, h3 { color: #00E5FF !important; text-shadow: 0 0 10px rgba(0, 229, 255, 0.6); }
.stock-card {
    background: rgba(0, 40, 80, 0.85);
    border: 2px solid #00B0FF;
    box-shadow: 0 0 20px rgba(0, 176, 255, 0.4);
    padding: 25px; border-radius: 15px; margin-bottom: 25px;
}
.stButton>button {
    background: linear-gradient(to bottom, #00E5FF, #00B0FF);
    color: #001233 !important;
    font-weight: 800 !important;
    border-radius: 8px; width: 100%; height: 50px;
}
.profit-up { color: #FF3D00 !important; font-size: 1.2em; font-weight: 900; }
.profit-down { color: #00E676 !important; font-size: 1.2em; font-weight: 900; }
.price-tag { color: #FFFF00 !important; font-size: 1.1em; }
.logout-btn>button {
    background: #FF5252 !important; color: white !important; height: 35px !important;
}
div[data-baseweb="popover"], 
div[data-baseweb="menu"],
div[role="listbox"] {
    background-color: #000814 !important;
    border: 1px solid #00B0FF !important;
}
div[data-baseweb="popover"] ul {
    background-color: #000814 !important;
}
div[role="option"] {
    background-color: #000814 !important;
    color: #FFFFFF !important;
}
div[role="option"]:hover, 
div[role="option"][aria-selected="true"] {
    background-color: #00E5FF !important;
    color: #000000 !important;
}
/* 2. 重點修正：隱藏表格標題篩選功能 (防止出現白色選單) */
/* 鎖定表格標題區塊，不讓它彈出篩選框 */
[data-testid="stDataFrameColHeader"] button {
    display: none !important;
}

/* 3. 強制修正表格右上角工具列 (下載、全螢幕等) */
[data-testid="stElementToolbar"] {
    background-color: #001233 !important;
    border: 1px solid #00E5FF !important;
    border-radius: 5px;
    padding: 2px;
}
/* 強制修正表格工具列 (右上角那塊) 的顏色 */
div[data-testid="stDataTableDynamicUpdateCursor"] button,
div[data-testid="stElementToolbar"] {
    background-color: rgba(0, 40, 80, 0.9) !important; /* 深藍色背景 */
    border: 1px solid #00E5FF !important; /* 加入青色邊框 */
    color: #FFFFFF !important; /* 文字/圖標變白色 */
}
/* 強制修正右上角工具列背景 */
[data-testid="stElementToolbar"] {
    background-color: #001233 !important;
    border: 1px solid #00E5FF !important;
    border-radius: 5px;
}
[data-testid="stElementToolbar"] button {
    color: #00E5FF !important;
}

/* 下拉選單修正 */
div[data-baseweb="popover"], div[role="listbox"] {
    background-color: #000814 !important;
    border: 1px solid #00B0FF !important;
}
/* 修正滑鼠移上去時的顏色 */
div[data-testid="stElementToolbar"] button:hover {
    background-color: #00E5FF !important;
    color: #001233 !important;
}
/* 1. 修正表格篩選選單 (Filter Menu) 與 搜尋框 */
/* 這是針對點擊表格欄位後跳出的篩選視窗 */
div[data-testid="stDataFrameResizer"] + div, 
div[data-baseweb="popover"] {
    background-color: #001233 !important;
    border: 1px solid #00E5FF !important;
}
/* 針對 DataFrame 內建工具欄的特定修正 */
[data-testid="stDataFrameToolbar"] {
    background-color: transparent !important;
}
div[data-baseweb="select"] > div:nth-child(1) {
    background-color: #001233 !important;
}
input {
    color: #00E5FF !important;
    -webkit-text-fill-color: #00E5FF !important;
}
input::placeholder {
    color: rgba(255, 255, 255, 0.5) !important;
}
</style>
""", unsafe_allow_html=True)

# Supabase 連線
SUPABASE_URL = "https://jhphmcbqtprfhvdkklps.supabase.co"
SUPABASE_KEY = "sb_publishable_qfe3kH2yYYXN_PI7KNCZMg_UJmcvJWE"
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("⚠️ 雲端資料庫連線中斷")

# --- 2. 核心功能函數 ---
@st.cache_data(ttl=86400)
def get_all_tickers():
    mapping = {}
    for code, info in twstock.twse.items():
        if len(code) == 4: mapping[f"{code}.TW"] = f"{code} {getattr(info, 'name', '')} ({getattr(info, 'industry', '上市股')})"
    for code, info in twstock.tpex.items():
        if len(code) == 4: mapping[f"{code}.TWO"] = f"{code} {getattr(info, 'name', '')} ({getattr(info, 'industry', '上櫃股')})"
    return mapping
def run_full_scan(tickers_map):
    qualified = []
    status = st.empty()
    progress = st.progress(0)
    ticker_list = list(tickers_map.keys())
    chunk_size = 50 
    
    for i in range(0, len(ticker_list), chunk_size):
        chunk = ticker_list[i : i + chunk_size]
        status.markdown(f"📡 正在掃描 (突破均線糾結強勢策略): **{i}/{len(ticker_list)}** 檔")
        progress.progress(min(i / len(ticker_list), 1.0))
        try:
            # 修改點：抓取更長的週期以計算週線 (150d -> 250d)
            data = yf.download(chunk, period="250d", group_by='ticker', progress=False, threads=True)
            for t in chunk:
                try:
                    df = data[t].dropna() if len(chunk) > 1 else data.dropna()
                    if len(df) < 100: continue
                    
                    # --- A. 增加週線判斷數據 ---
                    # 重新取樣成週線 (W) 並計算週 20MA
                    df_weekly = df['Close'].resample('W').last()
                    w_ma20 = df_weekly.rolling(20).mean().iloc[-1]
                    
                    # 日線數據
                    c = df['Close'].iloc[-1]
                    p_c = df['Close'].iloc[-2] # 前一日收盤價
                    v = df['Volume'].iloc[-1]
                    ma5, ma10, ma20, ma60 = df['Close'].rolling(5).mean().iloc[-1], df['Close'].rolling(10).mean().iloc[-1], df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(60).mean().iloc[-1]
                    ma60_p = df['Close'].rolling(60).mean().iloc[-2]
                    v20_a = df['Volume'].rolling(20).mean().iloc[-1]
                    
                    # 計算漲幅
                    day_ret = (c - p_c) / p_c

                    # --- 修改後的條件判斷 ---
                    if (
                        # 1. 基本糾結與多頭排列 (原本條件)
                        (max([ma5,ma10,ma20])-min([ma5,ma10,ma20]))/min([ma5,ma10,ma20]) <= 0.03 and 
                        ma60 > ma60_p and c > max([ma5,ma10,ma20,ma60]) and 
                        
                        # 2. 修改點 A：必須站在週 20MA 之上 (林恩如核心：長線趨勢)
                        c > w_ma20 and 
                        
                        # 3. 修改點 B：爆量 2 倍 + 漲幅 > 2.5%
                        v > (v20_a * 2.0) and 
                        day_ret >= 0.025 and 
                        
                        v >= 2000000 # 基本量能過濾
                    ):
                        
                        industry_name = tickers_map.get(t).split('(')[-1].replace(')', '')
                        
                        # --- 修改點 C：停損線切換為 日 20MA (強勢股守則) ---
                        dynamic_stop = ma20 
                        
                        qualified.append({
                            "代碼": t.split('.')[0], "全代碼": t, "產業": industry_name,
                            "現價": round(c, 2), "成交量": int(v // 2000), 
                            "停損": round(dynamic_stop, 2), "停利": round(c*1.2, 2),
                            "週20MA": round(w_ma20, 2)
                        })
                except: continue
        except: continue
    progress.empty(); status.empty()
    return qualified

# --- 3. 登入/註冊功能與介面 ---
if 'login' not in st.session_state: st.session_state.login = False

if not st.session_state.login:
    st.title("🏹 從從容容飆股王")
    st.markdown("### 🏆 買在起漲點，不追高雷達")
    col1, col2 = st.columns(2)
    with col1: st.markdown("<div class='stock-card'><h3>🌙 月租版</h3><h1>$399</h1></div>", unsafe_allow_html=True)
    with col2: st.markdown("<div class='stock-card'><h3>☀️ 年費版</h3><h1>$2,990</h1></div>", unsafe_allow_html=True)
    with st.expander("💳 顯示付款資訊"):
        st.info("🏦 永豐銀行 (807) | 帳號：148-018-00054187\n\n轉帳後截圖聯繫 Line: 811162 將於30分鐘內開通。")
    
    user = st.text_input("👤 帳號 (英數共4碼以上)").strip().lower()
    pwd = st.text_input("🔑 授權碼", type="password")
    
    c_login, c_reg = st.columns(2)
    
    with c_login:
        if st.button("🚀 登入系統"):
            if pwd != "STOCK2026":
                st.error("授權碼 請聯繫Line: 811162開通")
            else:
                res = supabase.table("users").select("*").eq("username", user).execute()
                if res.data:
                    u = res.data[0]
                    st.session_state.update({
                        "login": True, "user": user, "bal": u['balance'], 
                        "port": u['portfolio'], "history": u.get('history', []),
                        "watchlist": u.get('watchlist', [])
                    })
                    st.rerun()
                else:
                    st.error("此帳號尚未註冊，請先輸入帳號並點擊註冊")

    with c_reg:
        if st.button("📝 註冊帳號"):
            if len(user) < 4:
                st.warning("帳號長度需為 4 碼以上")
            elif pwd != "STOCK2026":
                st.error("授權碼 請聯繫Line: 811162開通")
            else:
                res = supabase.table("users").select("*").eq("username", user).execute()
                if res.data:
                    st.warning("已有此會員帳號")
                else:
                    u = {"username": user, "balance": 1000000, "portfolio": {}, "history": [], "watchlist": []}
                    supabase.table("users").insert(u).execute()
                    st.success("註冊成功！請直接點擊登入")

# --- 4. 主程式分頁 ---
else:
    stat_col1, stat_col2 = st.columns([5, 1])
    stat_col1.markdown(f"👤 您好, **{st.session_state.user}** | 💰 餘額: `${st.session_state.bal:,.0f}`")
    with stat_col2:
        if st.button("🚪 登出", key="logout"):
            st.session_state.clear()
            st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["🚀 飆股雷達", "💼 雲端模擬倉", "📜 歷史損益", "⭐ 自選清單"])
    
    with tab1:
        if st.button("🔍 開始 1800 檔全量掃描"):
            res = run_full_scan(get_all_tickers())
            st.session_state.scan_res = res 
        
        if 'scan_res' in st.session_state:
            sort_col1, sort_col2 = st.columns([1, 2])
            with sort_col1:
                sort_opt = st.selectbox("🔃 排序方式", ["預設", "現價 (高→低)", "現價 (低→高)", "成交量 (大→小)", "按產業"])
            
            display_list = st.session_state.scan_res.copy()
            if sort_opt == "現價 (高→低)": display_list.sort(key=lambda x: x['現價'], reverse=True)
            elif sort_opt == "現價 (低→高)": display_list.sort(key=lambda x: x['現價'])
            elif sort_opt == "成交量 (大→小)": display_list.sort(key=lambda x: x['成交量'], reverse=True)
            elif sort_opt == "按產業": display_list.sort(key=lambda x: x['產業'])

            st.success(f"🎯 掃描完成！共找到 {len(display_list)} 檔符合條件標的 (停損取 20MA)")
            
            for s in display_list:
                with st.container():
                    st.markdown(f"""
                    <div class='stock-card'>
                        <h3>{s['代碼']} - {s['產業']}</h3>
                        <p>💰 目前價格: <span class='price-tag'>${s['現價']}</span> | 📊 成交量: {s['成交量']} 張</p>
                        <p>🛑 動態停損(20MA): {s['停損']} | 🎯 預設停利: {s['停利']}</p>
                        <a href='https://www.wantgoo.com/stock/{s['代碼']}' target='_blank'>📈 查看線圖</a>
                    </div>""", unsafe_allow_html=True)
                    
                    with st.expander(f"🛒 買進 {s['代碼']}"):
                        qty = st.number_input("購買張數", min_value=1, value=1, key=f"q_{s['代碼']}")
                        total_cost = qty * 1000 * s['現價']
                        st.markdown(f"**預計買入總金額： `${total_cost:,.0f}`**")
                        if st.button(f"確認買進 {qty} 張", key=f"btn_{s['代碼']}"):
                            if st.session_state.bal >= total_cost:
                                st.session_state.bal -= total_cost
                                tk = s['全代碼']
                                st.session_state.port[tk] = st.session_state.port.get(tk, {'q':0, 'c':0, 'stop_loss': s['停損'], 'take_profit': s['停利']})
                                st.session_state.port[tk]['q'] += qty
                                st.session_state.port[tk]['c'] += total_cost
                                supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                                st.success("交易成功！"); st.rerun()
                            else: st.error("餘額不足")

    with tab2:
        total_unrealized_profit = 0
        col_bal, col_reset = st.columns([3, 1])
        col_bal.markdown(f"### 💰 帳戶餘額: `${st.session_state.bal:,.0f}`")
        if col_reset.button("⚠️ 重置 100 萬"):
            st.session_state.bal = 1000000
            st.session_state.port = {}
            st.session_state.history = []
            supabase.table("users").update({"balance": 1000000, "portfolio": {}, "history": []}).eq("username", st.session_state.user).execute()
            st.rerun()

        if st.button("🔄 刷新即時損益金額"):
            st.rerun()

        if st.session_state.port:
            for tk, d in list(st.session_state.port.items()):
                try:
                    ticker_obj = yf.Ticker(tk)
                    hist = ticker_obj.history(period="65d")
                    now_p = hist['Close'].iloc[-1]
                    
                    # 計算即時的 20MA 與 60MA
                    live_ma20 = hist['Close'].rolling(20).mean().iloc[-1]
                    live_ma60 = hist['Close'].rolling(60).mean().iloc[-1]
                    
                    cost_per_share = d['c'] / (d['q'] * 1000)
                    profit = (now_p * d['q'] * 1000) - d['c']
                    profit_rate = (profit / d['c']) * 100
                    total_unrealized_profit += profit
                    
                    stock_id = tk.split('.')[0]
                    # 停損參考買入時的設定值，但也顯示即時 MA 供參考
                    sl_val = d.get('stop_loss', max(live_ma20, live_ma60))
                    tp_val = d.get('take_profit', cost_per_share * 1.2)

                    if now_p <= sl_val:
                        st.error(f"⚠️ 股票代號 \"{stock_id}\" 已低於停損位 {sl_val:.2f}，建議賣出")
                    
                    color = "profit-up" if profit >= 0 else "profit-down"
                    st.markdown(f"""
                    <div class='stock-card'>
                        <h4>{stock_id} ({d['q']} 張)</h4>
                        <p>損益金額: <span class='{color}'>${profit:,.0f}</span> ({profit_rate:.2f}%)</p>
                        <p>成本價: {cost_per_share:.2f} | 現價: {now_p:.2f}</p>
                        <p>📊 即時 20MA: {live_ma20:.2f} | 60MA: {live_ma60:.2f}</p>
                        <p>🛑 買入停損: {sl_val:.2f} | 🎯 預設停利: {tp_val:.2f}</p>
                        <a href='https://www.wantgoo.com/stock/{stock_id}' target='_blank'>📈 查看即時線圖</a>
                    </div>""", unsafe_allow_html=True)
                    
                    with st.expander(f"💸 賣出 {stock_id}"):
                        s_qty = st.number_input("賣出張數", min_value=1, max_value=d['q'], value=d['q'], key=f"sq_{tk}")
                        est_back = s_qty * 1000 * now_p
                        st.markdown(f"**預計入帳金額： `${est_back:,.0f}`**")
                        if st.button(f"執行賣出 {s_qty} 張", key=f"sbtn_{tk}"):
                            cost_of_sold = (s_qty / d['q']) * d['c']
                            realized_p = est_back - cost_of_sold
                            history_entry = {
                                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "month": datetime.now().strftime("%Y-%m"),
                                "stock": stock_id, "qty": s_qty, "profit": realized_p
                            }
                            st.session_state.history.append(history_entry)
                            st.session_state.bal += est_back
                            st.session_state.port[tk]['q'] -= s_qty
                            st.session_state.port[tk]['c'] -= cost_of_sold
                            if st.session_state.port[tk]['q'] <= 0: del st.session_state.port[tk]
                            supabase.table("users").update({
                                "balance": st.session_state.bal, 
                                "portfolio": st.session_state.port,
                                "history": st.session_state.history
                            }).eq("username", st.session_state.user).execute()
                            st.success("賣出成功！"); st.rerun()
                except Exception as e:
                    st.warning(f"正在更新 {tk} 數據中...")

            st.divider()
            sum_color = "profit-up" if total_unrealized_profit >= 0 else "profit-down"
            st.markdown(f"### 📈 總未實現損益: <span class='{sum_color}'>${total_unrealized_profit:,.0f}</span>", unsafe_allow_html=True)
        else:
            st.info("目前庫存空空如也")

    with tab3:
        st.markdown("### 📊 已實現損益歷史")
        if st.session_state.history:
            df_hist = pd.DataFrame(st.session_state.history)
            month_list = ["全部"] + sorted(list(df_hist['month'].unique()), reverse=True)
            sel_month = st.selectbox("📅 篩選月份", month_list)
            view_df = df_hist if sel_month == "全部" else df_hist[df_hist['month'] == sel_month]
            total_realized = view_df['profit'].sum()
            summary_color = "#FF3D00" if total_realized >= 0 else "#00E676"
            st.markdown(f"#### 💰 該期間總已實現損益: <span style='color:{summary_color}'>${total_realized:,.0f}</span>", unsafe_allow_html=True)
            st.dataframe(view_df[['date', 'stock', 'qty', 'profit']].sort_values('date', ascending=False), use_container_width=True)
        else:
            st.info("尚無歷史成交紀錄")

    with tab4:
        st.markdown("### ⭐ 個人追蹤清單")
        tickers_map = get_all_tickers()
        c1, c2 = st.columns([3, 1])
        with c1:
            selected_stock = st.selectbox("🔍 搜尋並加入股票代號", options=list(tickers_map.keys()), 
                                        format_func=lambda x: tickers_map.get(x))
        with c2:
            st.write(" ")
            if st.button("➕ 加入自選"):
                if 'watchlist' not in st.session_state: st.session_state.watchlist = []
                if selected_stock not in st.session_state.watchlist:
                    st.session_state.watchlist.append(selected_stock)
                    supabase.table("users").update({"watchlist": st.session_state.watchlist}).eq("username", st.session_state.user).execute()
                    st.rerun()
                else:
                    st.toast("已在清單中")
        st.divider()
        if st.session_state.get('watchlist'):
            for wt in st.session_state.watchlist:
                sid = wt.split('.')[0]
                sinfo = tickers_map.get(wt, sid)
                with st.container():
                    st.markdown(f"""
                    <div class='stock-card' style='padding: 15px;'>
                        <div style='display: flex; justify-content: space-between; align-items: center;'>
                            <div>
                                <h4 style='margin:0;'>{sinfo}</h4>
                                <a href='https://www.wantgoo.com/stock/{sid}' target='_blank'>📈 查看線圖</a>
                            </div>
                        </div>
                    </div>""", unsafe_allow_html=True)
                    if st.button(f"🗑️ 移除 {sid}", key=f"rem_{sid}"):
                        st.session_state.watchlist.remove(wt)
                        supabase.table("users").update({"watchlist": st.session_state.watchlist}).eq("username", st.session_state.user).execute()
                        st.rerun()
        else:
            st.info("您的自選清單目前是空的")
