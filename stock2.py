import streamlit as st
import yfinance as yf
import pandas as pd
import twstock
from datetime import datetime
from supabase import create_client, Client

# --- 1. 初始化與 UI 樣式 ---
st.set_page_config(page_title="從從容容飆股王", layout="wide")

st.markdown("""
<style>
.stApp { background: linear-gradient(to bottom right, #001233, #000814); color: #E0F7FA; }

/* 強力修正：下拉選單 (Selectbox) - 確保文字為白色，背景為深色 */
div[data-baseweb="select"] > div {
    background-color: #0d1117 !important; 
    color: #FFFFFF !important;
    border: 1px solid #00B0FF !important;
}
div[role="listbox"] { background-color: #0d1117 !important; }
div[role="option"] { color: #FFFFFF !important; background-color: #0d1117 !important; }
div[role="option"]:hover { background-color: #00B0FF !important; color: #000000 !important; }

/* 介面組件樣式 */
.stMarkdown, .stText, p, li, span, label, div { color: #FFFFFF !important; }
.stock-card {
    background: rgba(0, 40, 80, 0.85);
    border: 2px solid #00B0FF;
    padding: 20px; border-radius: 12px; margin-bottom: 20px;
}
.stButton>button {
    background: linear-gradient(to bottom, #00E5FF, #00B0FF);
    color: #001233 !important; font-weight: 800 !important;
}
.profit-up { color: #FF3D00 !important; font-weight: 900; }
.profit-down { color: #00E676 !important; font-weight: 900; }
</style>
""", unsafe_allow_html=True)

# Supabase 連線
SUPABASE_URL = "https://jhphmcbqtprfhvdkklps.supabase.co"
SUPABASE_KEY = "sb_publishable_qfe3kH2yYYXN_PI7KNCZMg_UJmcvJWE"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. 核心掃描功能 (簡化版以節省篇幅) ---
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
    for i in range(0, len(ticker_list), 100):
        chunk = ticker_list[i : i + 100]
        status.write(f"📡 掃描中: {i}/{len(ticker_list)}")
        progress.progress(min(i / len(ticker_list), 1.0))
        try:
            data = yf.download(chunk, period="100d", group_by='ticker', progress=False)
            for t in chunk:
                try:
                    df = data[t].dropna()
                    if len(df) < 60: continue
                    c = df['Close'].iloc[-1]
                    ma60 = df['Close'].rolling(60).mean().iloc[-1]
                    if c > ma60: # 簡化篩選邏輯
                        qualified.append({"代碼": t.split('.')[0], "全代碼": t, "產業": tickers_map.get(t), "現價": round(c, 2), "停損": round(ma60, 2)})
                except: continue
        except: continue
    status.empty(); progress.empty()
    return qualified

# --- 3. 登入/註冊介面 ---
if 'login' not in st.session_state: st.session_state.login = False

if not st.session_state.login:
    st.title("🏹 從從容容飆股王")
    user_input = st.text_input("👤 帳號 (4碼以上)").strip().lower()
    pwd_input = st.text_input("🔑 授權碼", type="password")
    
    if st.button("🚀 登入 / 註冊"):
        if len(user_input) < 4: st.warning("帳號需 4 碼以上")
        elif pwd_input != "STOCK2026": st.error("授權碼錯誤")
        else:
            res = supabase.table("users").select("*").eq("username", user_input).execute()
            if res.data:
                u = res.data[0]
                # 重要：確保從資料庫抓取到的資料正確存入 session
                st.session_state.update({
                    "login": True, "user": user_input, 
                    "bal": u.get('balance', 1000000), 
                    "port": u.get('portfolio', {}), 
                    "history": u.get('history', [])
                })
                st.success(f"歡迎回來 {user_input}")
            else:
                new_user = {"username": user_input, "balance": 1000000, "portfolio": {}, "history": []}
                supabase.table("users").insert(new_user).execute()
                st.session_state.update({"login": True, "user": user_input, "bal": 1000000, "port": {}, "history": []})
                st.success("註冊成功")
            st.rerun()

# --- 4. 主程式 ---
else:
    # --- 頂部工具列 (登出按鈕移至此處) ---
    t_col1, t_col2 = st.columns([5, 1])
    with t_col1:
        st.write(f"👤 當前用戶: **{st.session_state.user}** | 💰 餘額: `${st.session_state.bal:,.0f}`")
    with t_col2:
        if st.button("🚪 登出系統"):
            st.session_state.clear()
            st.rerun()

    tab1, tab2, tab3 = st.tabs(["🚀 飆股雷達", "💼 雲端模擬倉", "📊 歷史損益"])
    
    with tab1:
        if st.button("🔍 開始全量掃描"):
            st.session_state.scan_res = run_full_scan(get_all_tickers())
        if 'scan_res' in st.session_state:
            for s in st.session_state.scan_res:
                with st.container():
                    st.markdown(f"<div class='stock-card'><h3>{s['代碼']} - {s['產業']}</h3><p>現價: ${s['現價']} | 停損: {s['停損']}</p></div>", unsafe_allow_html=True)
                    if st.button(f"🛒 買進 1 張 {s['代碼']}", key=f"b_{s['代碼']}"):
                        cost = s['現價'] * 1000
                        if st.session_state.bal >= cost:
                            st.session_state.bal -= cost
                            tk = s['全代碼']
                            st.session_state.port[tk] = st.session_state.port.get(tk, {'q':0, 'c':0})
                            st.session_state.port[tk]['q'] += 1; st.session_state.port[tk]['c'] += cost
                            supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                            st.success("買進成功"); st.rerun()

    with tab2:
        st.button("🔄 刷新損益")
        if st.session_state.port:
            for tk, d in list(st.session_state.port.items()):
                try:
                    p = yf.Ticker(tk).history(period="1d")['Close'].iloc[-1]
                    unrealized = (p * d['q'] * 1000) - d['c']
                    st.markdown(f"<div class='stock-card'><h4>{tk}</h4><p>未實現損益: <span class='{'profit-up' if unrealized>=0 else 'profit-down'}'>${unrealized:,.0f}</span></p></div>", unsafe_allow_html=True)
                    if st.button(f"💸 賣出 {tk}", key=f"s_{tk}"):
                        income = d['q'] * 1000 * p
                        profit = income - d['c']
                        st.session_state.history.append({"date": datetime.now().strftime("%Y-%m-%d"), "tk": tk, "profit": profit})
                        st.session_state.bal += income
                        del st.session_state.port[tk]
                        supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port, "history": st.session_state.history}).eq("username", st.session_state.user).execute()
                        st.rerun()
                except: st.error(f"讀取 {tk} 失敗")
        else: st.info("目前無持股")

    with tab3:
        st.markdown("### 📊 歷史成交紀錄")
        if st.session_state.history:
            df = pd.DataFrame(st.session_state.history)
            months = sorted(pd.to_datetime(df['date']).dt.strftime('%Y-%m').unique().tolist(), reverse=True)
            sel_m = st.selectbox("📅 選擇月份", ["全部顯示"] + months)
            f_df = df if sel_m == "全部顯示" else df[pd.to_datetime(df['date']).dt.strftime('%Y-%m') == sel_m]
            st.table(f_df)
        else: st.info("尚無歷史紀錄")
