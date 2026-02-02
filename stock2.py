import streamlit as st
import yfinance as yf
import pandas as pd
import random
import time
import twstock
from datetime import datetime, timedelta
from supabase import create_client, Client
import extra_streamlit_components as st_tags

# --- 初始化與連線邏輯 (維持不變) ---
def get_cookie_manager():
    if 'cookie_manager' not in st_tags.__dict__:
        return st_tags.CookieManager()
    return st_tags.CookieManager()

cookie_manager = get_cookie_manager()

SUPABASE_URL = "https://jhphmcbqtprfhvdkklps.supabase.co"
SUPABASE_KEY = "sb_publishable_qfe3kH2yYYXN_PI7KNCZMg_UJmcvJWE"
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("⚠️ 雲端資料庫連線中斷")

if not st.session_state.get('login'):
    saved_user = cookie_manager.get('saved_user')
    if saved_user:
        try:
            res = supabase.table("users").select("*").eq("username", saved_user).execute()
            if res.data:
                u = res.data[0]
                st.session_state.update({
                    "login": True, "user": saved_user, "bal": u['balance'], 
                    "port": u['portfolio'], "history": u.get('history', []),
                    "watchlist": u.get('watchlist', [])
                })
                st.rerun()
        except:
            pass

st.set_page_config(page_title="從從容容飆股王", layout="wide")
st.markdown("""
<style>
.stApp { background: linear-gradient(to bottom right, #001233, #000814); color: #FFFFFF; }
h1, h2, h3 { color: #00E5FF !important; text-shadow: 0 0 10px rgba(0, 229, 255, 0.4); }
[data-testid="stExpander"] { background-color: rgba(0, 20, 50, 0.9) !important; border: 1px solid #00E5FF !important; border-radius: 10px !important; }
[data-testid="stExpander"] summary { background-color: #001233 !important; color: #FFFFFF !important; border-radius: 10px 10px 0 0 !important; }
[data-testid="stExpander"] p, [data-testid="stNotificationContent"] p { color: #00E5FF !important; font-weight: 600 !important; text-shadow: 0 0 5px rgba(0, 229, 255, 0.3); }
a { color: #FFFFFF !important; text-decoration: underline !important; font-weight: 500; transition: 0.3s; }
a:hover { color: #00E5FF !important; text-shadow: 0 0 10px #00E5FF; }
label[data-testid="stWidgetLabel"] p { color: #FFFFFF !important; font-size: 1.1rem !important; font-weight: 600 !important; text-shadow: 1px 1px 2px rgba(0,0,0,0.5); }
.stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p { color: #FFFFFF !important; font-size: 18px !important; font-weight: 600 !important; }
.stock-card { background: rgba(0, 40, 80, 0.85); border: 2px solid #00B0FF; padding: 15px; border-radius: 12px; margin-bottom: 20px; }
.stButton>button { background: linear-gradient(to bottom, #00E5FF, #00B0FF); color: #001233 !important; font-weight: 800 !important; border-radius: 8px; }
.profit-up { color: #FF3D00 !important; font-size: 1.2em; font-weight: 900; }
.profit-down { color: #00E676 !important; font-size: 1.2em; font-weight: 900; }
</style>
""", unsafe_allow_html=True)

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
                    ma60_p = df['Close'].rolling(60).mean().iloc[-2]
                    v20_a = df['Volume'].rolling(20).mean().iloc[-1]
                    day_ret = (c - p_c) / p_c

                    if (
                        (max([ma5,ma10,ma20])-min([ma5,ma10,ma20]))/min([ma5,ma10,ma20]) <= 0.03 and 
                        ma60 > ma60_p and c > max([ma5,ma10,ma20,ma60]) and 
                        c > w_ma20 and 
                        v > (v20_a * 2.0) and 
                        day_ret >= 0.025 and 
                        v >= 2000000 
                    ):
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

# --- 3. 登入/註冊功能 (維持不變) ---
if 'login' not in st.session_state: st.session_state.login = False

if not st.session_state.login:
    st.title("🏹 從從容容飆股王")
    user = st.text_input("👤 帳號 (英數共4碼以上)").strip().lower()
    pwd = st.text_input("🔑 授權碼", type="password")
    c_login, c_reg = st.columns(2)
    with c_login:
        if st.button("🚀 登入系統"):
            if pwd == "STOCK2026":
                res = supabase.table("users").select("*").eq("username", user).execute()
                if res.data:
                    u = res.data[0]
                    st.session_state.update({"login": True, "user": user, "bal": u['balance'], "port": u['portfolio'], "history": u.get('history', []), "watchlist": u.get('watchlist', [])})
                    cookie_manager.set('saved_user', user, expires_at=datetime.now() + timedelta(days=30))
                    st.rerun()
    with c_reg:
        if st.button("📝 註冊帳號"):
            if len(user) >= 4 and pwd == "STOCK2026":
                res = supabase.table("users").select("*").eq("username", user).execute()
                if not res.data:
                    u = {"username": user, "balance": 1000000, "portfolio": {}, "history": [], "watchlist": []}
                    supabase.table("users").insert(u).execute()
                    st.success("註冊成功！")

# --- 4. 主程式分頁 ---
else:
    stat_col1, stat_col2 = st.columns([5, 1])
    stat_col1.markdown(f"👤 您好, **{st.session_state.user}** | 💰 餘額: `${st.session_state.bal:,.2f}`")
    with stat_col2:
        if st.button("🚪 登出", key="logout"):
            cookie_manager.delete('saved_user')
            st.session_state.clear(); st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["🚀 飆股雷達", "💼 雲端模擬倉", "📜 歷史損益", "⭐ 自選清單"])
    
    with tab1:
        if st.button("🔍 開始 1800 檔全量掃描"):
            st.session_state.scan_res = run_full_scan(get_all_tickers())
        
        if 'scan_res' in st.session_state:
            display_list = st.session_state.scan_res.copy()
            st.success(f"🎯 掃描完成！共找到 {len(display_list)} 檔符合條件標的")
            for s in display_list:
                with st.container():
                    # --- 修改 1: 移除 % 數顯示 ---
                    st.markdown(f"""
                    <div class='stock-card'>
                        <h3>{s['代碼']} - {s['產業']}</h3>
                        <p>💰 目前價格: <span class='price-tag'>${s['現價']}</span> | 📊 成交量: {s['成交量']} 張</p>
                        <p>🛑 動態停損(20MA): {s['停損']} | 🎯 預設停利: {s['停利']}</p>
                        <a href='https://www.wantgoo.com/stock/{s['代碼']}' target='_blank'>📈 查看線圖</a>
                    </div>""", unsafe_allow_html=True)
                    
                    with st.expander(f"🛒 買進 {s['代碼']}"):
                        # --- 修改 2: 支援零股 (小數點 3 位) ---
                        qty = st.number_input("購買股數 (張)", min_value=0.001, step=0.001, format="%.3f", key=f"q_{s['代碼']}")
                        total_cost = qty * 1000 * s['現價']
                        st.markdown(f"**預計買入總金額： `${total_cost:,.2f}`**")
                        if st.button(f"確認買進 {qty:.3f} 張", key=f"btn_{s['代碼']}"):
                            if st.session_state.bal >= total_cost:
                                st.session_state.bal -= total_cost
                                tk = s['全代碼']
                                st.session_state.port[tk] = st.session_state.port.get(tk, {'q':0.0, 'c':0.0, 'stop_loss': s['停損'], 'take_profit': s['停利']})
                                st.session_state.port[tk]['q'] += float(qty)
                                st.session_state.port[tk]['c'] += float(total_cost)
                                supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                                st.success("交易成功！"); st.rerun()
                            else: st.error("餘額不足")

    with tab2:
        total_unrealized_profit = 0
        if st.session_state.port:
            for tk, d in list(st.session_state.port.items()):
                try:
                    ticker_obj = yf.Ticker(tk)
                    hist = ticker_obj.history(period="65d")
                    now_p = hist['Close'].iloc[-1]
                    live_ma20 = hist['Close'].rolling(20).mean().iloc[-1]
                    cost_per_share = d['c'] / (d['q'] * 1000)
                    profit = (now_p * d['q'] * 1000) - d['c']
                    profit_rate = (profit / d['c']) * 100 if d['c'] > 0 else 0
                    total_unrealized_profit += profit
                    stock_id = tk.split('.')[0]
                    
                    color = "profit-up" if profit >= 0 else "profit-down"
                    st.markdown(f"""
                    <div class='stock-card'>
                        <h4>{stock_id} ({d['q']:.3f} 張)</h4>
                        <p>損益金額: <span class='{color}'>${profit:,.0f}</span> ({profit_rate:.2f}%)</p>
                        <p>成本價: {cost_per_share:.2f} | 現價: {now_p:.2f}</p>
                    </div>""", unsafe_allow_html=True)
                    
                    with st.expander(f"💸 賣出 {stock_id}"):
                        # --- 修改 3: 賣出支援零股 (小數點 3 位) ---
                        s_qty = st.number_input("賣出股數 (張)", min_value=0.001, max_value=float(d['q']), step=0.001, format="%.3f", key=f"sq_{tk}")
                        est_back = s_qty * 1000 * now_p
                        if st.button(f"執行賣出 {s_qty:.3f} 張", key=f"sbtn_{tk}"):
                            cost_of_sold = (s_qty / d['q']) * d['c']
                            realized_p = est_back - cost_of_sold
                            history_entry = {"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "month": datetime.now().strftime("%Y-%m"), "stock": stock_id, "qty": float(s_qty), "profit": float(realized_p)}
                            st.session_state.history.append(history_entry)
                            st.session_state.bal += est_back
                            st.session_state.port[tk]['q'] -= float(s_qty)
                            st.session_state.port[tk]['c'] -= float(cost_of_sold)
                            if st.session_state.port[tk]['q'] <= 0.0001: del st.session_state.port[tk]
                            supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port, "history": st.session_state.history}).eq("username", st.session_state.user).execute()
                            st.success("賣出成功！"); st.rerun()
                except: continue
            st.markdown(f"### 📈 總未實現損益: ${total_unrealized_profit:,.0f}")
        else: st.info("目前庫存空空如也")

    with tab3:
        if st.session_state.history:
            df_hist = pd.DataFrame(st.session_state.history)
            st.dataframe(df_hist[['date', 'stock', 'qty', 'profit']].sort_values('date', ascending=False), use_container_width=True)

    with tab4:
        # (自選清單維持原樣，僅顯示資訊)
        if st.session_state.get('watchlist'):
            for wt in st.session_state.watchlist:
                sid = wt.split('.')[0]
                st.markdown(f"<div class='stock-card'><h4>{wt}</h4></div>", unsafe_allow_html=True)
                if st.button(f"🗑️ 移除 {sid}", key=f"rem_{sid}"):
                    st.session_state.watchlist.remove(wt)
                    supabase.table("users").update({"watchlist": st.session_state.watchlist}).eq("username", st.session_state.user).execute()
                    st.rerun()
