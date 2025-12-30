import streamlit as st
import yfinance as yf
import pandas as pd
import random
import time
import twstock
from supabase import create_client, Client

# --- 1. 初始化與 UI 介面設計 ---
st.set_page_config(page_title="從從容容飆股王", layout="wide")

st.markdown("""
<style>
.stApp { background: linear-gradient(to bottom right, #001233, #000814); color: #E0F7FA; }
.stMarkdown, .stText, p, li, span, label, div { color: #E6F7FF !important; }
h1, h2, h3 { color: #00E5FF !important; text-shadow: 0 0 8px rgba(0, 229, 255, 0.5); }
.stock-card {
    background: rgba(0, 30, 60, 0.75);
    border: 1px solid #00B0FF;
    box-shadow: 0 0 15px rgba(0, 176, 255, 0.3) inset;
    padding: 20px;
    border-radius: 12px;
    margin-bottom: 20px;
}
.stButton>button { background: linear-gradient(to bottom, #00B0FF, #0081CB); color: white !important; border-radius: 8px; width: 100%; }
.profit-up { color: #FF5252 !important; font-weight: bold; }
.profit-down { color: #00E676 !important; font-weight: bold; }
.metric-box { background: rgba(0, 229, 255, 0.1); padding: 10px; border-radius: 8px; border: 1px dashed #00E5FF; text-align: center; }
</style>
""", unsafe_allow_html=True)

SUPABASE_URL = "https://jhphmcbqtprfhvdkklps.supabase.co"
SUPABASE_KEY = "sb_publishable_qfe3kH2yYYXN_PI7KNCZMg_UJmcvJWE"
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("⚠️ 雲端資料庫連線中斷")

# --- 2. 核心邏輯 ---

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
    total = len(ticker_list)
    chunk_size = 50 
    
    for i in range(0, total, chunk_size):
        chunk = ticker_list[i : i + chunk_size]
        status.markdown(f"📡 正在掃描全台股: **第 {i} - {min(i+chunk_size, total)} 檔**")
        progress.progress(min(i / total, 1.0))
        try:
            data = yf.download(chunk, period="160d", group_by='ticker', progress=False, threads=True)
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
                    ma60_prev = df['Close'].rolling(60).mean().iloc[-2]
                    v20_avg = df['Volume'].rolling(20).mean().iloc[-1]
                    
                    short_mas = [ma5, ma10, ma20]
                    is_tangled = (max(short_mas) - min(short_mas)) / min(short_mas) <= 0.03
                    is_ma60_up = ma60 > ma60_prev
                    is_above = c > max(ma5, ma10, ma20, ma60)
                    is_near = (c - ma5) / ma5 <= 0.05
                    is_vol_up = v > (v20_avg * 1.5)
                    is_not_cold = v >= 1000000 

                    if is_tangled and is_ma60_up and is_above and is_near and is_vol_up and is_not_cold:
                        qualified.append({
                            "代碼": t.split('.')[0], 
                            "全代碼": t, # 記住 .TW 或 .TWO
                            "產業": tickers_map.get(t), 
                            "現價": round(c, 2),
                            "成交量": int(v // 1000), 
                            "建議停損": round(ma60, 2), 
                            "建議停利": round(c * 1.15, 2),
                            "策略建議": "短中均線糾結突破", 
                            "連結": f"https://www.wantgoo.com/stock/{t.split('.')[0]}"
                        })
                except: continue
            time.sleep(0.2)
        except: continue
            
    progress.empty()
    status.empty()
    return qualified

# --- 3. 登入邏輯 ---
if 'login' not in st.session_state:
    st.session_state.login = False

if not st.session_state.login:
    st.title("🏹 從從容容飆股王")
    user = st.text_input("👤 帳號")
    pwd = st.text_input("🔑 授權碼", type="password")
    if st.button("🚀 登入系統"):
        if pwd == "STOCK2026": 
            res = supabase.table("users").select("*").eq("username", user).execute()
            u_data = res.data[0] if res.data else {"username": user, "balance": 1000000, "portfolio": {}}
            if not res.data: supabase.table("users").insert(u_data).execute()
            st.session_state.update({"login":True, "user":user, "bal":u_data['balance'], "port":u_data['portfolio']})
            st.rerun()
else:
    tab1, tab2 = st.tabs(["🚀 飆股雷達", "💼 雲端模擬倉"])
    
    with tab1:
        if st.button("🔍 開始 1700 檔全量掃描"):
            all_m = get_all_tickers()
            res = run_full_scan(all_m)
            # 修正：紀錄總數並隨機抽樣
            st.session_state.total_found = len(res)
            st.session_state.scan_res = random.sample(res, min(5, len(res)))
        
        if 'scan_res' in st.session_state:
            st.markdown(f"<div class='metric-box'>🎯 掃描完成！全市場共有 <b>{st.session_state.total_found}</b> 檔符合條件，隨機精選 5 檔：</div><br>", unsafe_allow_html=True)
            for s in st.session_state.scan_res:
                st.markdown(f"""
                <div class='stock-card'>
                    <h4>{s['代碼']} - {s['產業']} | <span style='color:#00E5FF'>現價: ${s['現價']}</span></h4>
                    <p>📊 成交量: {s['成交量']} 張 | 🎯 停利: {s['建議停利']} | 🛑 停損: {s['建議停損']}</p>
                    <a href='{s['連結']}' target='_blank' style='color:#00E5FF'>📈 查看線圖</a>
                </div>""", unsafe_allow_html=True)
                
                if st.button(f"買進 {s['代碼']}", key=f"buy_{s['代碼']}"):
                    cost = 1000 * s['現價']
                    if st.session_state.bal >= cost:
                        st.session_state.bal -= cost
                        # 關鍵修正：存入全代碼 (含 .TW/.TWO)
                        st.session_state.port[s['全代碼']] = st.session_state.port.get(s['全代碼'], {'q':0, 'c':0})
                        st.session_state.port[s['全代碼']]['q'] += 1
                        st.session_state.port[s['全代碼']]['c'] += cost
                        supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                        st.success(f"成功買進 {s['代碼']}")
                        st.rerun()

    with tab2:
        st.subheader(f"💰 帳戶餘額: ${st.session_state.bal:,.0f}")
        if st.session_state.port:
            for full_ticker, d in list(st.session_state.port.items()):
                try:
                    # 使用存好的全代碼，報價保證成功
                    now_data = yf.download(full_ticker, period="1d", progress=False)
                    now_p = float(now_data['Close'].iloc[-1])
                    profit = (now_p * d['q'] * 1000) - d['c']
                    color = "profit-up" if profit >= 0 else "profit-down"
                    
                    st.markdown(f"""
                    <div class='stock-card'>
                        <b>{full_ticker.split('.')[0]}</b> ({d['q']} 張) | 損益: <span class='{color}'>${profit:,.0f}</span>
                        <p>成本: {d['c']/(d['q']*1000):.2f} | 現價: {now_p:.2f}</p>
                    </div>""", unsafe_allow_html=True)
                    
                    if st.button(f"賣出 {full_ticker.split('.')[0]}", key=f"sell_{full_ticker}"):
                        st.session_state.bal += (d['q'] * 1000 * now_p)
                        del st.session_state.port[full_ticker]
                        supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                        st.rerun()
                except:
                    st.error(f"❌ 報價伺服器繁忙，無法取得 {full_ticker} 報價")
        else:
            st.info("庫存為空。")
