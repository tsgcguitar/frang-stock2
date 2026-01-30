import streamlit as st
import yfinance as yf
import pandas as pd
import random
import time
import twstock
from datetime import datetime, timedelta
from supabase import create_client, Client
import extra_streamlit_components as st_tags

# --- 初始化 Cookie 管理器 ---
def get_cookie_manager():
    if 'cookie_manager' not in st_tags.__dict__:
        return st_tags.CookieManager()
    return st_tags.CookieManager()

cookie_manager = get_cookie_manager()

# Supabase 連線資訊
SUPABASE_URL = "https://jhphmcbqtprfhvdkklps.supabase.co"
SUPABASE_KEY = "sb_publishable_qfe3kH2yYYXN_PI7KNCZMg_UJmcvJWE"
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("⚠️ 雲端資料庫連線中斷")

# 1. 自動登入邏輯
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

# --- 1. UI 樣式強化 (維持原樣) ---
st.set_page_config(page_title="從從容容飆股王", layout="wide")
st.markdown("""
<style>
.stApp { background: linear-gradient(to bottom right, #001233, #000814); color: #FFFFFF; }
h1, h2, h3 { color: #00E5FF !important; text-shadow: 0 0 10px rgba(0, 229, 255, 0.4); }
[data-testid="stExpander"] { background-color: rgba(0, 20, 50, 0.9) !important; border: 1px solid #00E5FF !important; border-radius: 10px !important; }
[data-testid="stExpander"] summary { background-color: #001233 !important; color: #FFFFFF !important; border-radius: 10px 10px 0 0 !important; }
[data-testid="stExpander"] p, [data-testid="stNotificationContent"] p { color: #00E5FF !important; font-weight: 600 !important; }
a { color: #FFFFFF !important; text-decoration: underline !important; font-weight: 500; }
a:hover { color: #00E5FF !important; text-shadow: 0 0 10px #00E5FF; }
label[data-testid="stWidgetLabel"] p { color: #FFFFFF !important; font-size: 1.1rem !important; font-weight: 600 !important; }
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

                    if ((max([ma5,ma10,ma20])-min([ma5,ma10,ma20]))/min([ma5,ma10,ma20]) <= 0.03 and 
                        ma60 > ma60_p and c > max([ma5,ma10,ma20,ma60]) and 
                        c > w_ma20 and v > (v20_a * 2.0) and day_ret >= 0.025 and v >= 2000000):
                        industry_name = tickers_map.get(t).split('(')[-1].replace(')', '')
                        qualified.append({
                            "代碼": t.split('.')[0], "全代碼": t, "產業": industry_name,
                            "現價": round(c, 2), "成交量": int(v // 2000), 
                            "停損": round(ma20, 2), "停利": round(c*1.2, 2),
                            "漲幅": round(day_ret * 100, 2)
                        })
                except: continue
        except: continue
    progress.empty(); status.empty()
    return qualified

# --- 3. 登入/註冊功能 (維持原樣) ---
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
            if pwd != "STOCK2026": st.error("授權碼錯誤")
            else:
                res = supabase.table("users").select("*").eq("username", user).execute()
                if res.data:
                    u = res.data[0]
                    st.session_state.update({"login": True, "user": user, "bal": u['balance'], "port": u['portfolio'], "history": u.get('history', []), "watchlist": u.get('watchlist', [])})
                    cookie_manager.set('saved_user', user, expires_at=datetime.now() + timedelta(days=30))
                    st.rerun()
                else: st.error("帳號未註冊")

    with c_reg:
        if st.button("📝 註冊帳號"):
            if len(user) < 4: st.warning("帳號過短")
            elif pwd != "STOCK2026": st.error("授權碼錯誤")
            else:
                res = supabase.table("users").select("*").eq("username", user).execute()
                if res.data: st.warning("帳號已存在")
                else:
                    u = {"username": user, "balance": 1000000, "portfolio": {}, "history": [], "watchlist": []}
                    supabase.table("users").insert(u).execute()
                    st.success("註冊成功！")

# --- 4. 主程式分頁 ---
else:
    stat_col1, stat_col2 = st.columns([5, 1])
    stat_col1.markdown(f"👤 您好, **{st.session_state.user}** | 💰 餘額: `${st.session_state.bal:,.0f}`")
    with stat_col2:
        if st.button("🚪 登出"):
            cookie_manager.delete('saved_user')
            st.session_state.clear(); st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["🚀 飆股雷達", "💼 雲端模擬倉", "📜 歷史損益", "⭐ 自選清單"])
    
    # --- Tab 1: 飆股雷達 (新增零股買入功能) ---
    with tab1:
        if st.button("🔍 開始 1800 檔全量掃描"):
            st.session_state.scan_res = run_full_scan(get_all_tickers())
        
        if 'scan_res' in st.session_state:
            sort_opt = st.selectbox("🔃 排序方式", ["預設", "現價 (高→低)", "現價 (低→高)", "成交量 (大→小)", "按產業"])
            display_list = sorted(st.session_state.scan_res, key=lambda x: x['現價'], reverse=(sort_opt=="現價 (高→低)"))
            
            for s in display_list:
                pct_color = "profit-up" if s['漲幅'] >= 0 else "profit-down"
                st.markdown(f"""
                <div class='stock-card'>
                    <h3>{s['代碼']} - {s['產業']}</h3>
                    <p>💰 目前價格: ${s['現價']} (<span class='{pct_color}'>{s['漲幅']:+.2f}%</span>) | 📊 成交量: {s['成交量']} 張</p>
                    <a href='https://www.wantgoo.com/stock/{s['代碼']}' target='_blank'>📈 查看線圖</a>
                </div>""", unsafe_allow_html=True)
                
                with st.expander(f"🛒 買進 {s['代碼']} (支援零股)"):
                    c1, c2 = st.columns(2)
                    buy_lots = c1.number_input("購買張數", min_value=0, value=1, step=1, key=f"bl_{s['代碼']}")
                    buy_shares = c2.number_input("購買股數 (零股)", min_value=0, max_value=999, value=0, step=1, key=f"bs_{s['代碼']}")
                    
                    total_buy_shares = (buy_lots * 1000) + buy_shares
                    total_cost = total_buy_shares * s['現價']
                    st.markdown(f"**預計買入總股數： `{total_buy_shares}` 股 | 總金額： `${total_cost:,.0f}`**")
                    
                    if st.button(f"確認買進", key=f"btn_{s['代碼']}"):
                        if total_buy_shares <= 0: st.error("請輸入購買數量")
                        elif st.session_state.bal >= total_cost:
                            st.session_state.bal -= total_cost
                            tk = s['全代碼']
                            # port[tk]['q'] 現在代表總股數
                            st.session_state.port[tk] = st.session_state.port.get(tk, {'q':0, 'c':0, 'stop_loss': s['停損'], 'take_profit': s['take_profit'] if 'take_profit' in s else s['現價']*1.2})
                            st.session_state.port[tk]['q'] += total_buy_shares
                            st.session_state.port[tk]['c'] += total_cost
                            supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                            st.success("交易成功！"); st.rerun()
                        else: st.error("餘額不足")

    # --- Tab 2: 雲端模擬倉 (新增零股賣出與張/股顯示) ---
    with tab2:
        if st.button("🔄 刷新即時數據"): st.rerun()
        
        if st.session_state.port:
            total_unrealized_profit = 0
            for tk, d in list(st.session_state.port.items()):
                try:
                    ticker_obj = yf.Ticker(tk)
                    now_p = ticker_obj.history(period="1d")['Close'].iloc[-1]
                    # 股數換算顯示
                    display_lots = d['q'] // 1000
                    display_shares = d['q'] % 1000
                    
                    avg_cost_per_share = d['c'] / d['q']
                    profit = (now_p * d['q']) - d['c']
                    profit_rate = (profit / d['c']) * 100
                    total_unrealized_profit += profit
                    
                    color = "profit-up" if profit >= 0 else "profit-down"
                    st.markdown(f"""
                    <div class='stock-card'>
                        <h4>{tk.split('.')[0]} (持有：{display_lots} 張 {display_shares} 股)</h4>
                        <p>損益金額: <span class='{color}'>${profit:,.0f}</span> ({profit_rate:.2f}%)</p>
                        <p>平均成本: {avg_cost_per_share:.2f} | 目前現價: {now_p:.2f}</p>
                    </div>""", unsafe_allow_html=True)
                    
                    with st.expander(f"💸 賣出 {tk.split('.')[0]}"):
                        c1, c2 = st.columns(2)
                        # 計算最大可賣張數與股數
                        max_lots = d['q'] // 1000
                        max_odd_shares = d['q'] % 1000
                        
                        sell_lots = c1.number_input("賣出張數", min_value=0, max_value=max_lots, value=max_lots, key=f"sl_{tk}")
                        # 零股賣出限制：如果賣張數小於最大張數，零股可以到999；如果是最後一張，則不能超過剩餘零股
                        sell_shares = c2.number_input("賣出股數", min_value=0, max_value=999, value=0, key=f"ss_{tk}")
                        
                        total_sell_shares = (sell_lots * 1000) + sell_shares
                        
                        if total_sell_shares > d['q']:
                            st.error(f"超過持有總數 (目前持有 {d['q']} 股)")
                        else:
                            est_back = total_sell_shares * now_p
                            st.markdown(f"**預計入帳金額： `${est_back:,.0f}`**")
                            if st.button(f"執行賣出", key=f"sbtn_{tk}"):
                                cost_of_sold = (total_sell_shares / d['q']) * d['c']
                                history_entry = {
                                    "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    "month": datetime.now().strftime("%Y-%m"),
                                    "stock": tk.split('.')[0], "qty_shares": total_sell_shares, 
                                    "profit": est_back - cost_of_sold
                                }
                                st.session_state.history.append(history_entry)
                                st.session_state.bal += est_back
                                st.session_state.port[tk]['q'] -= total_sell_shares
                                st.session_state.port[tk]['c'] -= cost_of_sold
                                if st.session_state.port[tk]['q'] <= 0: del st.session_state.port[tk]
                                supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port, "history": st.session_state.history}).eq("username", st.session_state.user).execute()
                                st.success("賣出成功！"); st.rerun()
                except: continue
            st.markdown(f"### 📈 總未實現損益: ${total_unrealized_profit:,.0f}")
        else: st.info("目前無持股")

    # --- Tab 3 & 4: 維持原本邏輯 ---
    with tab3:
        if st.session_state.history:
            st.dataframe(pd.DataFrame(st.session_state.history).sort_values('date', ascending=False), use_container_width=True)
        else: st.info("尚無紀錄")
        
    with tab4:
        st.markdown("### ⭐ 個人追蹤清單")
        tickers_map = get_all_tickers()
        selected_stock = st.selectbox("🔍 搜尋股票", options=list(tickers_map.keys()), format_func=lambda x: tickers_map.get(x))
        if st.button("➕ 加入自選"):
            if selected_stock not in st.session_state.watchlist:
                st.session_state.watchlist.append(selected_stock)
                supabase.table("users").update({"watchlist": st.session_state.watchlist}).eq("username", st.session_state.user).execute()
                st.rerun()
        for wt in st.session_state.get('watchlist', []):
            st.write(f"📌 {tickers_map.get(wt)}")
