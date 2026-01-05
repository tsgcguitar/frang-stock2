import streamlit as st
import yfinance as yf
import pandas as pd
import twstock
from datetime import datetime
from supabase import create_client, Client

# --- 1. 初始化與 UI 樣式 (精準調整下拉選單顏色) ---
st.set_page_config(page_title="從從容容飆股王", layout="wide")

st.markdown("""
<style>
/* 整體背景 */
.stApp { background: linear-gradient(to bottom right, #001233, #000814); color: #E0F7FA; }

/* 強力修正：下拉選單 (Selectbox) 本體與文字顏色 */
div[data-baseweb="select"] > div {
    background-color: #0d1117 !important; 
    color: #FFFFFF !important;
    border: 1px solid #00B0FF !important;
}

/* 修正下拉選單展開後的選項清單 */
div[role="listbox"] {
    background-color: #0d1117 !important;
}
div[role="option"] {
    color: #FFFFFF !important;
    background-color: #0d1117 !important;
}
div[role="option"]:hover {
    background-color: #00B0FF !important;
    color: #000000 !important;
}

/* 標題與卡片 */
.stMarkdown, .stText, p, li, span, label, div { color: #FFFFFF !important; font-weight: 500; }
h1, h2, h3 { color: #FFFFFF !important; text-shadow: 0 0 10px rgba(0, 229, 255, 0.6); }
.stock-card {
    background: rgba(0, 40, 80, 0.85);
    border: 2px solid #00B0FF;
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
        if len(code) == 4: mapping[f"{code}.TW"] = getattr(info, 'industry', '上市股')
    for code, info in twstock.tpex.items():
        if len(code) == 4: mapping[f"{code}.TWO"] = getattr(info, 'industry', '上櫃股')
    return mapping

def run_full_scan(tickers_map):
    qualified = []
    status = st.empty(); progress = st.progress(0)
    ticker_list = list(tickers_map.keys())
    for i in range(0, len(ticker_list), 50):
        chunk = ticker_list[i : i + 50]
        status.markdown(f"📡 正在掃描: **{i}/{len(ticker_list)}** 檔")
        progress.progress(min(i / len(ticker_list), 1.0))
        try:
            data = yf.download(chunk, period="150d", group_by='ticker', progress=False, threads=True)
            for t in chunk:
                try:
                    df = data[t].dropna() if len(chunk) > 1 else data.dropna()
                    if len(df) < 65: continue
                    c = df['Close'].iloc[-1]; v = df['Volume'].iloc[-1]
                    ma5, ma10, ma20, ma60 = df['Close'].rolling(5).mean().iloc[-1], df['Close'].rolling(10).mean().iloc[-1], df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(60).mean().iloc[-1]
                    ma60_p = df['Close'].rolling(60).mean().iloc[-2]
                    v20_a = df['Volume'].rolling(20).mean().iloc[-1]
                    if (max([ma5,ma10,ma20])-min([ma5,ma10,ma20]))/min([ma5,ma10,ma20]) <= 0.03 and ma60 > ma60_p and c > max([ma5,ma10,ma20,ma60]) and (c - ma5)/ma5 <= 0.05 and v > (v20_a * 1.5) and v >= 1000000:
                        qualified.append({"代碼": t.split('.')[0], "全代碼": t, "產業": tickers_map.get(t), "現價": round(c, 2), "成交量": int(v // 1000), "停損": round(ma60, 2), "停利": round(c*1.15, 2)})
                except: continue
        except: continue
    progress.empty(); status.empty()
    return qualified

# --- 3. 登入/註冊介面 ---
if 'login' not in st.session_state: st.session_state.login = False

if not st.session_state.login:
    st.title("🏹 從從容容飆股王")
    st.markdown("### 🏆 買在起漲點，不追高雷達")
    user_input = st.text_input("👤 帳號 (請輸入4碼以上英文或數字)").strip().lower() # 大小寫視為相同
    pwd_input = st.text_input("🔑 授權碼", type="password")
    
    if st.button("🚀 登入 / 註冊"):
        if len(user_input) < 4:
            st.warning("帳號格式錯誤：需要 4 碼以上")
        elif pwd_input != "STOCK2026":
            st.error("授權碼 請聯繫Line: 811162開通")
        else:
            # 檢查會員是否已存在
            res = supabase.table("users").select("*").eq("username", user_input).execute()
            if res.data:
                u = res.data[0]
                st.session_state.update({
                    "login": True, "user": user_input, 
                    "bal": u.get('balance', 1000000), 
                    "port": u.get('portfolio', {}), 
                    "history": u.get('history', [])
                })
                st.success(f"歡迎回來，{user_input}！")
            else:
                # 新註冊會員
                new_user = {"username": user_input, "balance": 1000000, "portfolio": {}, "history": []}
                supabase.table("users").insert(new_user).execute()
                st.session_state.update({"login": True, "user": user_input, "bal": 1000000, "port": {}, "history": []})
                st.success("註冊成功！已為您開通雲端帳戶")
            st.rerun()

# --- 4. 主程式 ---
else:
    # 登出功能放在側邊欄
    with st.sidebar:
        st.write(f"👤 當前用戶: **{st.session_state.user}**")
        if st.button("🚪 登出系統"):
            st.session_state.clear()
            st.rerun()

    tab1, tab2, tab3 = st.tabs(["🚀 飆股雷達", "💼 雲端模擬倉", "📊 歷史損益"])
    
    with tab1:
        if st.button("🔍 開始 1700 檔全量掃描"):
            res = run_full_scan(get_all_tickers())
            st.session_state.total_found = len(res); st.session_state.scan_res = res
        if 'scan_res' in st.session_state:
            st.success(f"🎯 掃描完成！共找到 {st.session_state.total_found} 檔標的")
            for s in st.session_state.scan_res:
                with st.container():
                    st.markdown(f"<div class='stock-card'><h3>{s['代碼']} - {s['產業']}</h3><p>💰 目前價格: <span class='price-tag'>${s['現價']}</span> | 📊 成交量: {s['成交量']} 張</p><p>🛑 停損點: {s['停損']} | 🎯 停利點: {s['停利']}</p><a href='https://www.wantgoo.com/stock/{s['代碼']}' target='_blank'>📈 查看線圖</a></div>", unsafe_allow_html=True)
                    with st.expander(f"🛒 買進 {s['代碼']}"):
                        qty = st.number_input("購買張數", min_value=1, value=1, key=f"q_{s['代碼']}")
                        total_cost = qty * 1000 * s['現價']
                        if st.button(f"確認買進 {qty} 張", key=f"btn_{s['代碼']}"):
                            if st.session_state.bal >= total_cost:
                                st.session_state.bal -= total_cost
                                tk = s['全代碼']
                                st.session_state.port[tk] = st.session_state.port.get(tk, {'q':0, 'c':0})
                                st.session_state.port[tk]['q'] += qty; st.session_state.port[tk]['c'] += total_cost
                                supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                                st.success("交易成功！"); st.rerun()
                            else: st.error("餘額不足")

    with tab2:
        st.button("🔄 點擊刷新即時股價與損益")
        total_unrealized = 0
        col_bal, col_reset = st.columns([3, 1])
        col_bal.markdown(f"### 💰 帳戶餘額: `${st.session_state.bal:,.0f}`")
        if col_reset.button("⚠️ 重置 100 萬"):
            st.session_state.update({"bal": 1000000, "port": {}, "history": []})
            supabase.table("users").update({"balance": 1000000, "portfolio": {}, "history": []}).eq("username", st.session_state.user).execute()
            st.rerun()

        if st.session_state.port:
            for tk, d in list(st.session_state.port.items()):
                try:
                    ticker_obj = yf.Ticker(tk); hist = ticker_obj.history(period="65d")
                    now_p = hist['Close'].iloc[-1]; ma60_val = hist['Close'].rolling(60).mean().iloc[-1]
                    profit = (now_p * d['q'] * 1000) - d['c']; profit_pct = (profit / d['c']) * 100
                    total_unrealized += profit
                    
                    if now_p <= ma60_val: st.error(f"⚠️ 股票代號 \"{tk.split('.')[0]}\" 已達系統停損點位")
                    if profit_pct >= 15: st.warning(f"🎊 股票代號 \"{tk.split('.')[0]}\" 已賺超過 15%")

                    st.markdown(f"<div class='stock-card'><h4>{tk.split('.')[0]} ({d['q']} 張)</h4><p>損益: <span class='{'profit-up' if profit>=0 else 'profit-down'}'>${profit:,.0f}</span> ({profit_pct:.2f}%)</p><p>成本: {d['c']/(d['q']*1000):.2f} | 現價: {now_p:.2f}</p></div>", unsafe_allow_html=True)
                    
                    with st.expander(f"💸 賣出 {tk.split('.')[0]}"):
                        s_qty = st.number_input("賣出張數", min_value=1, max_value=d['q'], value=d['q'], key=f"sq_{tk}")
                        if st.button(f"執行賣出 {s_qty} 張", key=f"sbtn_{tk}"):
                            est_back = s_qty * 1000 * now_p
                            cost_of_sold = (s_qty / d['q']) * d['c']
                            realized_profit = est_back - cost_of_sold
                            
                            new_record = {"date": datetime.now().strftime("%Y-%m-%d"), "tk": tk.split('.')[0], "profit": realized_profit}
                            st.session_state.history.append(new_record)
                            
                            st.session_state.bal += est_back
                            st.session_state.port[tk]['q'] -= s_qty; st.session_state.port[tk]['c'] -= cost_of_sold
                            if st.session_state.port[tk]['q'] <= 0: del st.session_state.port[tk]
                            
                            supabase.table("users").update({
                                "balance": st.session_state.bal, 
                                "portfolio": st.session_state.port, 
                                "history": st.session_state.history
                            }).eq("username", st.session_state.user).execute()
                            st.success("賣出成功！"); st.rerun()
                except: continue
            st.divider(); st.markdown(f"### 📈 總未實現損益: <span class='{'profit-up' if total_unrealized>=0 else 'profit-down'}'>${total_unrealized:,.0f}</span>", unsafe_allow_html=True)
        else: st.info("目前庫存空空如也")

    with tab3:
        st.markdown("### 📊 已實現損益查詢")
        if st.session_state.history:
            df_hist = pd.DataFrame(st.session_state.history)
            df_hist['date'] = pd.to_datetime(df_hist['date'])
            
            months = sorted(df_hist['date'].dt.strftime('%Y-%m').unique().tolist(), reverse=True)
            selected_month = st.selectbox("📅 選擇查詢月份", ["全部顯示"] + months)
            
            filtered_df = df_hist if selected_month == "全部顯示" else df_hist[df_hist['date'].dt.strftime('%Y-%m') == selected_month]
            
            st.markdown(f"#### 💰 累計盈虧: `${filtered_df['profit'].sum():,.0f}`")
            # 格式化日期顯示
            display_df = filtered_df.copy()
            display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
            st.table(display_df.sort_values(by='date', ascending=False))
        else:
            st.info("尚無歷史成交紀錄")
