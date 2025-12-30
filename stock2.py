import streamlit as st
import yfinance as yf
import pandas as pd
import random
import time
import twstock
from supabase import create_client, Client

# --- 1. 初始化與 UI 介面設計 ---
st.set_page_config(page_title="從從容容飆股王", layout="wide")

# 藍色高科技風格 CSS
st.markdown("""
<style>
.stApp {
    background: linear-gradient(to bottom right, #001233, #000814);
    color: #E0F7FA;
}
.stMarkdown, .stText, p, li, span, label, div {
    color: #E6F7FF !important;
}
h1, h2, h3 {
    color: #00E5FF !important;
    text-shadow: 0 0 8px rgba(0, 229, 255, 0.5);
}
.stTabs [aria-selected="true"] {
    color: #00E5FF !important;
}
.stock-card {
    background: rgba(0, 30, 60, 0.75);
    border: 1px solid #00B0FF;
    box-shadow: 0 0 15px rgba(0, 176, 255, 0.3) inset;
    padding: 20px;
    border-radius: 12px;
    margin-bottom: 20px;
}
.stButton>button {
    background: linear-gradient(to bottom, #00B0FF, #0081CB);
    color: white !important;
    border-radius: 8px;
    width: 100%;
}
.profit-up { color: #FF5252 !important; font-weight: bold; }
.profit-down { color: #00E676 !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# 資料庫連線
SUPABASE_URL = "https://jhphmcbqtprfhvdkklps.supabase.co"
SUPABASE_KEY = "sb_publishable_qfe3kH2yYYXN_PI7KNCZMg_UJmcvJWE"
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("⚠️ 雲端資料庫連線中斷")

# --- 2. 核心邏輯：批量掃描與策略判斷 ---

@st.cache_data(ttl=86400)
def get_all_tickers():
    """抓取全台股代碼"""
    mapping = {}
    for code, info in twstock.twse.items():
        if len(code) == 4: mapping[f"{code}.TW"] = getattr(info, 'industry', '上市股')
    for code, info in twstock.tpex.items():
        if len(code) == 4: mapping[f"{code}.TWO"] = getattr(info, 'industry', '上櫃股')
    return mapping

def run_full_scan(tickers_map):
    """執行全量掃描 (優化版：分批下載 + 修正糾結邏輯)"""
    qualified = []
    status = st.empty()
    progress = st.progress(0)
    
    ticker_list = list(tickers_map.keys())
    total = len(ticker_list)
    chunk_size = 50  # 每 50 檔一批，避免過度請求
    
    for i in range(0, total, chunk_size):
        chunk = ticker_list[i : i + chunk_size]
        status.markdown(f"📡 正在掃描全台股: **第 {i} - {min(i+chunk_size, total)} 檔** (總計 {total})")
        progress.progress(min(i / total, 1.0))
        
        try:
            # 批量下載數據
            data = yf.download(chunk, period="160d", group_by='ticker', progress=False, threads=True)
            
            for t in chunk:
                try:
                    df = data[t].dropna() if len(chunk) > 1 else data.dropna()
                    if len(df) < 65: continue
                    
                    # 計算指標
                    c = df['Close'].iloc[-1]
                    v = df['Volume'].iloc[-1]
                    ma5 = df['Close'].rolling(5).mean().iloc[-1]
                    ma10 = df['Close'].rolling(10).mean().iloc[-1]
                    ma20 = df['Close'].rolling(20).mean().iloc[-1]
                    ma60 = df['Close'].rolling(60).mean().iloc[-1]
                    ma60_prev = df['Close'].rolling(60).mean().iloc[-2]
                    v20_avg = df['Volume'].rolling(20).mean().iloc[-1]
                    
                    # --- 策略條件 (規格調整) ---
                    # 1. 均線糾結：僅計算 5, 10, 20MA，落差 3% 內
                    short_mas = [ma5, ma10, ma20]
                    is_tangled = (max(short_mas) - min(short_mas)) / min(short_mas) <= 0.03
                    
                    # 2. 趨勢確認：60MA 方向向上，且股價站在所有均線之上
                    is_ma60_up = ma60 > ma60_prev
                    is_above = c > max(ma5, ma10, ma20, ma60)
                    
                    # 3. 買點捕捉：離 5MA 不超過 5% (避免過度追高)
                    is_near = (c - ma5) / ma5 <= 0.05
                    
                    # 4. 量能與流動性：今日量 > 20日均量 1.5倍，且成交量需超過 1000張 (1000000股)
                    is_vol_up = v > (v20_avg * 1.5)
                    is_not_cold = v >= 1000000 

                    if is_tangled and is_ma60_up and is_above and is_near and is_vol_up and is_not_cold:
                        qualified.append({
                            "代碼": t.split('.')[0], 
                            "產業": tickers_map.get(t), 
                            "現價": round(c, 2),
                            "成交量": int(v // 1000), 
                            "建議停損": round(ma60, 2), 
                            "建議停利": round(c * 1.15, 2),
                            "策略建議": "短中均線糾結突破 + 季線支撐向上", 
                            "連結": f"https://www.wantgoo.com/stock/{t.split('.')[0]}"
                        })
                except:
                    continue
            time.sleep(0.3) # 微小延遲保護 API
        except:
            continue
            
    progress.empty()
    status.empty()
    return qualified

# --- 3. 登入邏輯與權限控制 ---
if 'login' not in st.session_state:
    st.session_state.login = False

if not st.session_state.login:
    st.title("🏹 從從容容飆股王")
    st.markdown("### 🏆 買在起漲點，不追高雷達")
    
    col_a, col_b = st.columns(2)
    with col_a: st.markdown("<div class='stock-card'><h3>🌙 月租版</h3><h1>$299</h1></div>", unsafe_allow_html=True)
    with col_b: st.markdown("<div class='stock-card'><h3>☀️ 年費版</h3><h1>$2,990</h1><p>省2個月</p></div>", unsafe_allow_html=True)
    
    with st.expander("💳 點擊查看付款資訊"):
        st.write("🏦 永豐銀行 (807) | 帳號：148-018-00054187")
        st.info("轉帳後截圖聯繫 官方Line: 811162，將於30分鐘內開通。")

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
            st.error("授權碼錯誤，請聯繫客服")

# --- 4. 主功能頁面 ---
else:
    tab1, tab2 = st.tabs(["🚀 飆股雷達", "💼 雲端模擬倉"])
    
    with tab1:
        st.info("💡 邏輯：5/10/20MA 糾結 + 60MA 向上 + 今日爆量突破")
        if st.button("🔍 開始 1700 檔全量掃描 (預計 1-2 分鐘)"):
            all_m = get_all_tickers()
            res = run_full_scan(all_m)
            st.session_state.scan_res = random.sample(res, min(5, len(res)))
            if not res: 
                st.warning("今日全市場無符合「短中糾結突破」標的，建議等候大盤壓縮或盤整。")
        
        if 'scan_res' in st.session_state:
            for s in st.session_state.scan_res:
                with st.container():
                    st.markdown(f"""
                    <div class='stock-card'>
                        <h4>{s['代碼']} - {s['產業']} | <span style='color:#00E5FF'>現價: ${s['現價']}</span></h4>
                        <p>📊 成交量: {s['成交量']} 張 | 💡 {s['策略建議']}</p>
                        <p>🛑 建議停損: {s['建議停損']} (跌破季線) | 🎯 建議停利: {s['建議停利']}</p>
                        <a href='{s['連結']}' target='_blank' style='color:#00E5FF'>📈 查看詳細線圖</a>
                    </div>""", unsafe_allow_html=True)
                    
                    if st.button(f"模擬買進 1張 {s['代碼']}", key=f"buy_{s['代碼']}"):
                        cost = 1000 * s['現價']
                        if st.session_state.bal >= cost:
                            st.session_state.bal -= cost
                            st.session_state.port[s['代碼']] = st.session_state.port.get(s['代碼'], {'q':0, 'c':0})
                            st.session_state.port[s['代碼']]['q'] += 1
                            st.session_state.port[s['代碼']]['c'] += cost
                            supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                            st.success(f"成功買進 {s['代碼']}")
                            st.rerun()
                        else: st.error("餘額不足")

    with tab2:
        st.subheader(f"💰 帳戶餘額: ${st.session_state.bal:,.0f}")
        if st.session_state.port:
            for code, d in list(st.session_state.port.items()):
                try:
                    now_data = yf.download(f"{code}.TW" if int(code)<5000 else f"{code}.TWO", period="1d", progress=False)
                    now_p = float(now_data['Close'].iloc[-1])
                    profit = (now_p * d['q'] * 1000) - d['c']
                    color = "profit-up" if profit > 0 else "profit-down"
                    
                    st.markdown(f"""
                    <div class='stock-card'>
                        <b>{code}</b> ({d['q']} 張) | 損益: <span class='{color}'>${profit:,.0f}</span>
                        <p>成本: {d['c']/(d['q']*1000):.2f} | 現價: {now_p:.2f}</p>
                    </div>""", unsafe_allow_html=True)
                    
                    if st.button(f"賣出 {code}", key=f"sell_{code}"):
                        st.session_state.bal += (d['q'] * 1000 * now_p)
                        del st.session_state.port[code]
                        supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                        st.rerun()
                except:
                    st.write(f"暫時無法取得 {code} 即時報價")
        else:
            st.info("目前庫存空空如也。")
