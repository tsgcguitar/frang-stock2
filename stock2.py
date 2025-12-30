import streamlit as st
import yfinance as yf
import pandas as pd
import random
import time
import twstock
from supabase import create_client, Client

# --- 1. 初始化與 UI ---
st.set_page_config(page_title="從從容容飆股王", layout="wide")

# 藍色高科技風格 CSS
st.markdown("""
    <style>
    .stApp { background: linear-gradient(to bottom right, #001233, #000814); color: #E0F7FA; }
    h1, h2, h3, .stTabs [aria-selected="true"] { color: #00E5FF !important; text-shadow: 0 0 8px rgba(0, 229, 255, 0.4); }
    .stock-card {
        background: rgba(0, 30, 60, 0.75); border: 1px solid #00B0FF;
        box-shadow: 0 0 15px rgba(0, 176, 255, 0.3) inset; padding: 20px; border-radius: 12px; margin-bottom: 20px;
    }
    .stButton>button { background: linear-gradient(to bottom, #00B0FF, #0081CB); color: white !important; border-radius: 8px; }
    .profit-up { color: #FF3333 !important; } .profit-down { color: #00FF66 !important; }
    </style>
    """, unsafe_allow_html=True)

SUPABASE_URL = "https://jhphmcbqtprfhvdkklps.supabase.co"
SUPABASE_KEY = "sb_publishable_qfe3kH2yYYXN_PI7KNCZMg_UJmcvJWE"
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("⚠️ 雲端資料庫連線中斷")

# --- 2. 核心邏輯 (規格 1, 2) ---
@st.cache_data(ttl=86400)
def get_all_tickers():
    """抓取全台股 1700+ 檔代碼"""
    mapping = {}
    # 上市
    for code, info in twstock.twse.items():
        if len(code) == 4:
            mapping[f"{code}.TW"] = getattr(info, 'industry', '上市股')
    # 上櫃
    for code, info in twstock.tpex.items():
        if len(code) == 4:
            mapping[f"{code}.TWO"] = getattr(info, 'industry', '上櫃股')
    return mapping

def run_full_scan(tickers_map):
    qualified = []
    status = st.empty()
    progress = st.progress(0)
    
    ticker_list = list(tickers_map.keys())
    total = len(ticker_list)
    
    # 開始全量掃描 (規格 1)
    for i, t in enumerate(ticker_list):
        if i % 20 == 0: # 每 20 檔更新一次介面，節省效能
            status.markdown(f"📡 正在掃描全台股: **{t}** ({i}/{total})")
            progress.progress(i / total)
            
        try:
            # 抓取足夠計算 60MA 的資料
            df = yf.download(t, period="150d", progress=False).dropna()
            if len(df) < 60: continue # 排除新股 (規格 2)
            
            # 取最新數據
            c = df['Close'].iloc[-1]
            v = df['Volume'].iloc[-1]
            ma5 = df['Close'].rolling(5).mean().iloc[-1]
            ma10 = df['Close'].rolling(10).mean().iloc[-1]
            ma20 = df['Close'].rolling(20).mean().iloc[-1]
            ma60 = df['Close'].rolling(60).mean().iloc[-1]
            v20_avg = df['Volume'].rolling(20).mean().iloc[-1]
            
            # 判斷邏輯 (規格 2)
            mas = [ma5, ma10, ma20, ma60]
            # 1. 均線糾結落差 3% 內
            is_tangled = (max(mas) - min(mas)) / min(mas) <= 0.03
            # 2. 股價站上所有均線
            is_above = c > max(mas)
            # 3. 離 5MA 不超過 5% (剛起漲)
            is_near = (c - ma5) / ma5 <= 0.05
            # 4. 今日量 > 20日均量 * 1.5
            is_vol_up = v > (v20_avg * 1.5)
            # 5. 過濾冷門股 (成交量 > 1000張)
            is_not_cold = v >= 1000000 

            if is_tangled and is_above and is_near and is_vol_up and is_not_cold:
                qualified.append({
                    "代碼": t.split('.')[0], "產業": tickers_map.get(t), "現價": round(c, 2),
                    "成交量": int(v // 1000), "建議停損": round(ma60, 2), "建議停利": round(c * 1.15, 2),
                    "策略建議": "均線糾結強勢突破", "連結": f"https://www.wantgoo.com/stock/{t.split('.')[0]}"
                })
        except:
            continue
            
    progress.empty()
    status.empty()
    return qualified

# --- 3. 登入邏輯 (規格 3, 10, 11) ---
if 'login' not in st.session_state:
    st.session_state.login = False

if not st.session_state.login:
    st.title("🏹 從從容容飆股王")
    st.markdown("### 🏆 買在起漲點，不追高雷達")
    
    # 規格 10: 訂閱方案
    c1, c2 = st.columns(2)
    with c1: st.markdown("<div class='stock-card'><h3>🌙 月租版</h3><h1>$299</h1></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div class='stock-card'><h3>☀️ 年費版</h3><h1>$2,990</h1><p>省2個月</p></div>", unsafe_allow_html=True)
    
    # 規格 11: 付款資訊
    with st.expander("💳 點擊查看付款資訊"):
        st.write("🏦 永豐銀行 (807) | 帳號：148-018-00054187")
        st.info("轉帳後截圖聯繫 官方Line: 811162，將於30分鐘內開通。")

    user = st.text_input("👤 帳號")
    pwd = st.text_input("🔑 授權碼", type="password")
    if st.button("🚀 登入"):
        if pwd == "STOCK2026": # 範例授權碼
            res = supabase.table("users").select("*").eq("username", user).execute()
            if res.data:
                u_data = res.data[0]
            else:
                u_data = {"username": user, "balance": 1000000, "portfolio": {}}
                supabase.table("users").insert(u_data).execute()
            
            st.session_state.update({"login":True, "user":user, "bal":u_data['balance'], "port":u_data['portfolio']})
            st.rerun()

# --- 4. 主功能分頁 (規格 4-9) ---
else:
    tab1, tab2 = st.tabs(["🚀 飆股雷達", "💼 雲端模擬倉"])
    
    with tab1:
        if st.button("🔍 開始 1700 檔全量掃描 (需時較久)"):
            all_m = get_all_tickers()
            res = run_full_scan(all_m)
            # 規格 8: 每次只吐 5 檔
            st.session_state.scan_res = random.sample(res, min(5, len(res)))
            if not res: st.warning("今日全市場無符合「糾結突破」之股票，建議放寬條件或等待盤勢壓縮。")
        
        if 'scan_res' in st.session_state:
            for s in st.session_state.scan_res:
                st.markdown(f"""
                <div class='stock-card'>
                    <h4>{s['代碼']} - {s['產業']} | <span style='color:#00E5FF'>現價: ${s['現價']}</span></h4>
                    <p>📊 成交量: {s['成交量']} 張 | 💡 {s['策略建議']}</p>
                    <p>🛑 建議停損: {s['建議停損']} (跌破60MA) | 🎯 建議停利: {s['建議停利']}</p>
                    <a href='{s['連結']}' target='_blank' style='color:#00E5FF'>📈 查看詳細線圖</a>
                </div>""", unsafe_allow_html=True)
                
                if st.button(f"買進 {s['代碼']}", key=f"buy_{s['代碼']}"):
                    cost = 1000 * s['現價']
                    if st.session_state.bal >= cost:
                        st.session_state.bal -= cost
                        st.session_state.port[s['代碼']] = st.session_state.port.get(s['代碼'], {'q':0, 'c':0})
                        st.session_state.port[s['代碼']]['q'] += 1
                        st.session_state.port[s['代碼']]['c'] += cost
                        supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                        st.success(f"成功買進 {s['代碼']} 1張")
                        st.rerun()
                    else: st.error("餘額不足")

    with tab2:
        st.subheader(f"💰 帳戶餘額: ${st.session_state.bal:,.0f}")
        # 規格 7: 重新抓取目前股價
        if st.session_state.port:
            for code, d in list(st.session_state.port.items()):
                now_p = float(yf.download(f"{code}.TW", period="1d", progress=False)['Close'].iloc[-1])
                profit = (now_p * d['q'] * 1000) - d['c']
                color = "profit-up" if profit > 0 else "profit-down"
                
                st.markdown(f"""
                <div class='stock-card'>
                    <b>{code}</b> ({d['q']} 張) | 當前損益: <span class='{color}'>${profit:,.0f}</span>
                    <p>成本: {d['c']/(d['q']*1000):.2f} | 現價: {now_p:.2f}</p>
                </div>""", unsafe_allow_html=True)
                
                if st.button(f"賣出 {code}", key=f"sell_{code}"):
                    st.session_state.bal += (d['q'] * 1000 * now_p)
                    del st.session_state.port[code]
                    supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                    st.rerun()
        else:
            st.info("目前庫存空空如也，快去雷達找飆股吧！")
