import streamlit as st
import yfinance as yf
import pandas as pd
import time
import twstock
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
.summary-box {
    background: rgba(255, 255, 255, 0.1);
    padding: 20px; border-radius: 15px; border: 1px solid #00E5FF;
    margin-bottom: 20px;
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
        if len(code) == 4: mapping[f"{code}.TW"] = getattr(info, 'industry', '上市股')
    for code, info in twstock.tpex.items():
        if len(code) == 4: mapping[f"{code}.TWO"] = getattr(info, 'industry', '上櫃股')
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
            data = yf.download(chunk, period="150d", group_by='ticker', progress=False, threads=True)
            for t in chunk:
                try:
                    df = data[t].dropna() if len(chunk) > 1 else data.dropna()
                    if len(df) < 65: continue
                    c = df['Close'].iloc[-1]
                    v = df['Volume'].iloc[-1]
                    ma5 = df['Close'].rolling(5).mean().iloc[-1]
                    ma10 = df['Close'].rolling(10).mean().iloc[-1]
                    ma20 = df['Close'].rolling(20).mean().iloc[-1]
                    ma60 = df['Close'].rolling(60).mean().iloc[-1]
                    ma60_p = df['Close'].rolling(60).mean().iloc[-2]
                    v20_a = df['Volume'].rolling(20).mean().iloc[-1]
                    
                    if (max([ma5,ma10,ma20])-min([ma5,ma10,ma20]))/min([ma5,ma10,ma20]) <= 0.03 and \
                       ma60 > ma60_p and c > max([ma5,ma10,ma20,ma60]) and \
                       (c - ma5)/ma5 <= 0.05 and v > (v20_a * 1.5) and v >= 1000000:
                        qualified.append({
                            "代碼": t.split('.')[0], "全代碼": t, "產業": tickers_map.get(t),
                            "現價": round(c, 2), "成交量": int(v // 1000), "停損": round(ma60, 2), "停利": round(c*1.15, 2)
                        })
                except: continue
        except: continue
    progress.empty(); status.empty()
    return qualified

# --- 3. 登入/訂閱介面 ---
if 'login' not in st.session_state: st.session_state.login = False

if not st.session_state.login:
    st.title("🏹 從從容容飆股王")
    st.markdown("### 🏆 買在起漲點，不追高雷達")
    col1, col2 = st.columns(2)
    with col1: st.markdown("<div class='stock-card'><h3>🌙 月租版</h3><h1>$299</h1></div>", unsafe_allow_html=True)
    with col2: st.markdown("<div class='stock-card'><h3>☀️ 年費版</h3><h1>$2,990</h1></div>", unsafe_allow_html=True)
    with st.expander("💳 顯示付款資訊"):
        st.info("🏦 永豐銀行 (807) | 帳號：148-018-00054187\n\n轉帳後截圖聯繫 Line: 811162 將於30分鐘內開通。")
    user = st.text_input("👤 帳號")
    pwd = st.text_input("🔑 授權碼", type="password")
    if st.button("🚀 登入"):
        if pwd == "STOCK2026":
            res = supabase.table("users").select("*").eq("username", user).execute()
            u = res.data[0] if res.data else {"username": user, "balance": 1000000, "portfolio": {}}
            if not res.data: supabase.table("users").insert(u).execute()
            st.session_state.update({"login":True, "user":user, "bal":u['balance'], "port":u['portfolio']})
            st.rerun()

# --- 4. 主程式分頁 ---
else:
    tab1, tab2 = st.tabs(["🚀 飆股雷達", "💼 雲端模擬倉"])
    
    with tab1:
        if st.button("🔍 開始 1700 檔全量掃描"):
            res = run_full_scan(get_all_tickers())
            st.session_state.total_found = len(res)
            st.session_state.scan_res = res  # 移除 random.sample，顯示所有搜到的股票
        
        if 'scan_res' in st.session_state:
            st.success(f"🎯 掃描完成！共找到 {st.session_state.total_found} 檔符合條件標的")
            for s in st.session_state.scan_res:
                with st.container():
                    st.markdown(f"""
                    <div class='stock-card'>
                        <h3>{s['代碼']} - {s['產業']}</h3>
                        <p>💰 目前價格: <span class='price-tag'>${s['現價']}</span> | 📊 成交量: {s['成交量']} 張</p>
                        <p>🛑 停損點: {s['停損']} | 🎯 停利點: {s['停利']}</p>
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
                                st.session_state.port[tk] = st.session_state.port.get(tk, {'q':0, 'c':0})
                                st.session_state.port[tk]['q'] += qty
                                st.session_state.port[tk]['c'] += total_cost
                                supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                                st.success("交易成功！"); st.rerun()
                            else: st.error("餘額不足")

    with tab2:
        # 帳戶概況區塊
        total_market_value = 0
        total_cost_value = 0
        current_port_data = []

        # 先抓取所有持股目前的價格 (批量抓取加快速度)
        if st.session_state.port:
            with st.spinner('正在從 Yahoo Finance 刷新最新報價...'):
                tks = list(st.session_state.port.keys())
                data = yf.download(tks, period="1d", progress=False)
                
                for tk in tks:
                    d = st.session_state.port[tk]
                    try:
                        # 處理單檔與多檔下載格式差異
                        if len(tks) > 1:
                            now_p = float(data['Close'][tk].iloc[-1])
                        else:
                            now_p = float(data['Close'].iloc[-1])
                        
                        mkt_val = now_p * d['q'] * 1000
                        profit = mkt_val - d['c']
                        total_market_value += mkt_val
                        total_cost_value += d['c']
                        current_port_data.append({"tk": tk, "now_p": now_p, "profit": profit, "qty": d['q'], "cost": d['c']})
                    except:
                        st.warning(f"無法取得 {tk} 報價")

        unrealized_profit = total_market_value - total_cost_value
        unrealized_rate = (unrealized_profit / total_cost_value * 100) if total_cost_value > 0 else 0
        p_color = "profit-up" if unrealized_profit >= 0 else "profit-down"

        # 頂部統計面板
        st.markdown(f"""
        <div class='summary-box'>
            <h3 style='margin:0;'>📊 模擬倉帳戶概況</h3>
            <hr style='border-color:rgba(0,229,255,0.3);'>
            <p>💰 帳戶現金: <b>${st.session_state.bal:,.0f}</b></p>
            <p>股票總市值: <b>${total_market_value:,.0f}</b></p>
            <p>總未實現損益: <span class='{p_color}'>${unrealized_profit:,.0f} ({unrealized_rate:.2f}%)</span></p>
        </div>
        """, unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🔄 刷新損益金額"):
                st.rerun()
        with col_b:
            if st.button("⚠️ 重置 100 萬帳戶"):
                st.session_state.bal = 1000000
                st.session_state.port = {}
                supabase.table("users").update({"balance": 1000000, "portfolio": {}}).eq("username", st.session_state.user).execute()
                st.success("帳戶已重置！")
                st.rerun()

        st.divider()

        if current_port_data:
            for item in current_port_data:
                tk, now_p, profit, d_q, d_c = item['tk'], item['now_p'], item['profit'], item['qty'], item['cost']
                color = "profit-up" if profit >= 0 else "profit-down"
                
                with st.container():
                    st.markdown(f"""
                    <div class='stock-card'>
                        <h4>{tk.split('.')[0]} ({d_q} 張)</h4>
                        <p>損益金額: <span class='{color}'>${profit:,.0f}</span> ({ (profit/d_c)*100 :.2f}%)</p>
                        <p>成本價: {d_c/(d_q*1000):.2f} | 現價: {now_p:.2f}</p>
                    </div>""", unsafe_allow_html=True)
                    
                    with st.expander(f"💸 賣出 {tk.split('.')[0]}"):
                        s_qty = st.number_input("賣出張數", min_value=1, max_value=d_q, value=d_q, key=f"sq_{tk}")
                        est_back = s_qty * 1000 * now_p
                        st.markdown(f"**預計入帳金額： `${est_back:,.0f}`**")
                        if st.button(f"執行賣出 {s_qty} 張", key=f"sbtn_{tk}"):
                            st.session_state.bal += est_back
                            cost_of_sold = (s_qty / d_q) * d_c
                            st.session_state.port[tk]['q'] -= s_qty
                            st.session_state.port[tk]['c'] -= cost_of_sold
                            if st.session_state.port[tk]['q'] <= 0: del st.session_state.port[tk]
                            supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                            st.success("賣出成功！")
                            st.rerun()
        else:
            st.info("目前庫存空空如也")
