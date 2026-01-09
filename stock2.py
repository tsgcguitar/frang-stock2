import streamlit as st
import yfinance as yf
import pandas as pd
import twstock
from datetime import datetime
from supabase import create_client, Client

# --- 1. 初始化與終極 UI 樣式 (完全取代舊版) ---
st.set_page_config(page_title="從從容容飆股王", layout="wide")

st.markdown("""
<style>
/* 全域背景 */
.stApp { background: linear-gradient(to bottom right, #001233, #000814); color: #E0F7FA; }
.stMarkdown, .stText, p, li, span, label, div { color: #FFFFFF !important; font-weight: 500; }
h1, h2, h3 { color: #00E5FF !important; text-shadow: 0 0 10px rgba(0, 229, 255, 0.6); }

/* 徹底封鎖表格標題點擊 (防止彈出白色選單) */
[data-testid="stDataFrameColHeader"] { pointer-events: none !important; }

/* 解決 Tab 4 與表格內的白色區塊問題 (Popover/Menu) */
div[data-baseweb="popover"], 
div[data-baseweb="menu"], 
div[role="listbox"],
ul[role="listbox"],
div[data-testid="stTooltipHoverTarget"] + div {
    background-color: #001233 !important;
    background: #001233 !important;
    border: 2px solid #00E5FF !important;
}
div[role="option"], li[role="option"] {
    background-color: #001233 !important;
    color: #FFFFFF !important;
}
div[role="option"]:hover, li[role="option"]:hover {
    background-color: #00E5FF !important;
    color: #001233 !important;
}

/* 修正表格右上角工具列 */
[data-testid="stElementToolbar"] {
    background-color: #001233 !important;
    border: 1px solid #00E5FF !important;
    border-radius: 5px;
}
[data-testid="stElementToolbar"] button { color: #00E5FF !important; }

/* 股票卡片與按鈕 */
.stock-card {
    background: rgba(0, 40, 80, 0.85);
    border: 2px solid #00B0FF;
    padding: 20px; border-radius: 12px; margin-bottom: 20px;
}
.stButton>button {
    background: linear-gradient(to bottom, #00E5FF, #00B0FF);
    color: #001233 !important;
    font-weight: 800 !important;
}
.profit-up { color: #FF3D00 !important; font-size: 1.2em; font-weight: 900; }
.profit-down { color: #00E676 !important; font-size: 1.2em; font-weight: 900; }
.price-tag { color: #FFFF00 !important; font-size: 1.1em; }
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
        status.markdown(f"📡 正在掃描: **{i}/{len(ticker_list)}** 檔")
        progress.progress(min(i / len(ticker_list), 1.0))
        try:
            data = yf.download(chunk, period="250d", group_by='ticker', progress=False, threads=True)
            for t in chunk:
                try:
                    df = data[t].dropna() if len(chunk) > 1 else data.dropna()
                    if len(df) < 100: continue
                    df_weekly = df['Close'].resample('W').last()
                    w_ma20 = df_weekly.rolling(20).mean().iloc[-1]
                    c = df['Close'].iloc[-1]
                    p_c = df['Close'].iloc[-2]
                    v = df['Volume'].iloc[-1]
                    ma5, ma10, ma20, ma60 = df['Close'].rolling(5).mean().iloc[-1], df['Close'].rolling(10).mean().iloc[-1], df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(60).mean().iloc[-1]
                    v20_a = df['Volume'].rolling(20).mean().iloc[-1]
                    day_ret = (c - p_c) / p_c

                    if ((max([ma5,ma10,ma20])-min([ma5,ma10,ma20]))/min([ma5,ma10,ma20]) <= 0.03 and 
                        c > max([ma5,ma10,ma20,ma60]) and c > w_ma20 and 
                        v > (v20_a * 2.0) and day_ret >= 0.025 and v >= 2000000):
                        
                        industry_name = tickers_map.get(t).split('(')[-1].replace(')', '')
                        qualified.append({
                            "代碼": t.split('.')[0], "全代碼": t, "產業": industry_name,
                            "現價": round(c, 2), "成交量": int(v // 2000), 
                            "停損": round(ma20, 2), "停利": round(c*1.2, 2)
                        })
                except: continue
        except: continue
    progress.empty(); status.empty()
    return qualified

# --- 3. 登入系統 ---
if 'login' not in st.session_state: st.session_state.login = False

if not st.session_state.login:
    st.title("🏹 從從容容飆股王")
    user = st.text_input("👤 帳號 (英數共4碼以上)").strip().lower()
    pwd = st.text_input("🔑 授權碼", type="password")
    c_login, c_reg = st.columns(2)
    
    if c_login.button("🚀 登入系統"):
        if pwd == "STOCK2026":
            res = supabase.table("users").select("*").eq("username", user).execute()
            if res.data:
                u = res.data[0]
                st.session_state.update({"login": True, "user": user, "bal": u['balance'], "port": u['portfolio'], "history": u.get('history', []), "watchlist": u.get('watchlist', [])})
                st.rerun()
            else: st.error("帳號未註冊")
        else: st.error("授權碼錯誤")
    
    if c_reg.button("📝 註冊帳號"):
        if len(user) >= 4 and pwd == "STOCK2026":
            u = {"username": user, "balance": 1000000, "portfolio": {}, "history": [], "watchlist": []}
            supabase.table("users").insert(u).execute()
            st.success("註冊成功！")

# --- 4. 主程式分頁 ---
else:
    stat_col1, stat_col2 = st.columns([5, 1])
    stat_col1.markdown(f"👤 **{st.session_state.user}** | 💰 餘額: `${st.session_state.bal:,.0f}`")
    if stat_col2.button("🚪 登出"):
        st.session_state.clear(); st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["🚀 飆股雷達", "💼 雲端模擬倉", "📜 歷史損益", "⭐ 自選清單"])
    
    with tab1:
        if st.button("🔍 開始掃描"):
            st.session_state.scan_res = run_full_scan(get_all_tickers())
        if 'scan_res' in st.session_state:
            for s in st.session_state.scan_res:
                with st.container():
                    st.markdown(f"<div class='stock-card'><h3>{s['代碼']} - {s['產業']}</h3><p>現價: <span class='price-tag'>${s['現價']}</span></p></div>", unsafe_allow_html=True)
                    if st.button(f"🛒 買進 {s['代碼']}", key=f"buy_{s['代碼']}"):
                        cost = 1000 * s['現價']
                        if st.session_state.bal >= cost:
                            st.session_state.bal -= cost
                            tk = s['全代碼']
                            st.session_state.port[tk] = st.session_state.port.get(tk, {'q':0, 'c':0})
                            st.session_state.port[tk]['q'] += 1
                            st.session_state.port[tk]['c'] += cost
                            supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                            st.success("買入成功"); st.rerun()

    with tab2:
        if st.session_state.port:
            for tk, d in list(st.session_state.port.items()):
                now_p = yf.Ticker(tk).history(period="1d")['Close'].iloc[-1]
                profit = (now_p * d['q'] * 1000) - d['c']
                st.markdown(f"<div class='stock-card'><h4>{tk}</h4><p>損益: ${profit:,.0f}</p></div>", unsafe_allow_html=True)
                if st.button(f"💸 賣出 {tk}", key=f"sell_{tk}"):
                    st.session_state.bal += (d['q'] * 1000 * now_p)
                    st.session_state.history.append({"date": datetime.now().strftime("%Y-%m-%d"), "month": datetime.now().strftime("%Y-%m"), "stock": tk, "qty": d['q'], "profit": profit})
                    del st.session_state.port[tk]
                    supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port, "history": st.session_state.history}).eq("username", st.session_state.user).execute()
                    st.rerun()
        else: st.info("無庫存")

    with tab3:
        st.markdown("### 📊 已實現損益歷史")
        if st.session_state.history:
            df_hist = pd.DataFrame(st.session_state.history)
            # 強制轉換為整數避免 .9994
            df_hist['profit'] = df_hist['profit'].apply(lambda x: round(float(x), 0))
            
            month_list = ["全部"] + sorted(list(df_hist['month'].unique()), reverse=True)
            sel_month = st.selectbox("📅 篩選月份", month_list)
            view_df = df_hist if sel_month == "全部" else df_hist[df_hist['month'] == sel_month]
            
            total_realized = view_df['profit'].sum()
            st.markdown(f"#### 💰 總已實現損益: ${total_realized:,.0f}")
            
            st.dataframe(
                view_df[['date', 'stock', 'qty', 'profit']].sort_values('date', ascending=False), 
                use_container_width=True, hide_index=True,
                column_config={"profit": st.column_config.NumberColumn("損益", format="$%d")}
            )
        else: st.info("尚無歷史")

    with tab4:
        st.markdown("### ⭐ 自選清單")
        t_map = get_all_tickers()
        sel = st.selectbox("🔍 搜尋股票", options=list(t_map.keys()), format_func=lambda x: t_map.get(x))
        if st.button("➕ 加入"):
            if sel not in st.session_state.watchlist:
                st.session_state.watchlist.append(sel)
                supabase.table("users").update({"watchlist": st.session_state.watchlist}).eq("username", st.session_state.user).execute()
                st.rerun()
