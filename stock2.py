import streamlit as st
import yfinance as yf
import pandas as pd
import random
import time
import twstock
from supabase import create_client, Client

# --- 1. 設定與金鑰 ---
st.set_page_config(page_title="從從容容飆股王", layout="wide")

SUPABASE_URL = "https://jhphmcbqtprfhvdkklps.supabase.co"
SUPABASE_KEY = "sb_publishable_qfe3kH2yYYXN_PI7KNCZMg_UJmcvJWE"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("⚠️ 雲端資料庫連線中斷")

# --- 2. 星際深藍金 UI (規格 10, 11) ---
st.markdown("""
    <style>
    .stApp { background-color: #050A18; color: #FFFFFF; }
    .stock-card { 
        background: linear-gradient(145deg, #0A122A, #050A18);
        border: 1px solid #F3C351; padding: 20px; border-radius: 12px; margin-bottom: 20px;
    }
    h1, h2, h3 { color: #F3C351 !important; }
    .stButton>button { background: #F3C351; color: #050A18 !important; font-weight: bold; border-radius: 8px; }
    .profit-up { color: #FF4D4D; } .profit-down { color: #00E676; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 核心功能函式 (規格 1, 2, 3) ---
@st.cache_data(ttl=86400)
def get_stock_map():
    mapping = {}
    for code, info in twstock.twse.items():
        if len(code) == 4: mapping[f"{code}.TW"] = getattr(info, 'industry', '上市股')
    for code, info in twstock.tpex.items():
        if len(code) == 4: mapping[f"{code}.TWO"] = getattr(info, 'industry', '上櫃股')
    return mapping

def scan_logic(tickers, info_map):
    qualified = []
    status = st.empty()
    progress = st.progress(0)
    for i, t in enumerate(tickers[:300]): # 測試階段先掃300檔，正式可拿掉限制
        status.text(f"📡 掃描中: {t}")
        progress.progress(i / 300)
        try:
            df = yf.download(t, period="100d", progress=False).dropna()
            if len(df) < 60: continue
            
            close, vol = df['Close'].iloc[-1], df['Volume'].iloc[-1]
            ma5, ma10, ma20, ma60 = df['Close'].rolling(5).mean().iloc[-1], df['Close'].rolling(10).mean().iloc[-1], df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(60).mean().iloc[-1]
            avg_v20 = df['Volume'].rolling(20).mean().iloc[-1]
            
            mas = [ma5, ma10, ma20, ma60]
            if (max(mas)-min(mas))/min(mas) <= 0.03 and close > max(mas) and (close-ma5)/ma5 <= 0.05 and vol > avg_v20*1.5 and vol >= 1000000:
                qualified.append({
                    "代碼": t.split('.')[0], "產業": info_map.get(t), "現價": round(close,2),
                    "成交量": int(vol//1000), "建議停損": round(ma60,2), "建議停利": round(close*1.15,2),
                    "策略": "均線糾結+爆量起漲", "連結": f"https://www.wantgoo.com/stock/{t.split('.')[0]}"
                })
        except: continue
    return qualified

# --- 4. 登入前頁面 (規格 10, 11) ---
if 'login' not in st.session_state or not st.session_state.login:
    st.title("🏹 從從容容飆股王")
    st.markdown("#### *專為不喜歡追高但又想要買在起漲點的投資者設計*")
    
    col1, col2 = st.columns(2)
    with col1: st.markdown("<div class='stock-card'><h3>月租 $299</h3></div>", unsafe_allow_html=True)
    with col2: st.markdown("<div class='stock-card'><h3>年費 $2,990</h3><p>省2個月</p></div>", unsafe_allow_html=True)
    
    with st.expander("💳 顯示訂閱付款資訊"):
        st.write("🏦 永豐銀行 (807) | 帳號：148-018-00054187")
        st.info("轉帳後截圖聯繫 官方Line: 811162，將於30分鐘內開通。")

    u = st.text_input("帳號")
    p = st.text_input("授權碼", type="password")
    if st.button("登入系統"):
        if p == "STOCK2026": # 預設授權碼
            res = supabase.table("users").select("*").eq("username", u).execute()
            if res.data:
                bal, port = res.data[0]['balance'], res.data[0]['portfolio']
            else:
                bal, port = 1000000.0, {}
                supabase.table("users").insert({"username":u, "balance":bal, "portfolio":port}).execute()
            st.session_state.login, st.session_state.user, st.session_state.bal, st.session_state.port = True, u, bal, port
            st.rerun()

# --- 5. 登入後頁面 (規格 4, 5, 7, 8, 9) ---
else:
    t1, t2 = st.tabs(["🚀 飆股雷達", "💼 雲端模擬倉"])
    
    with t1:
        if st.button("🔍 開始全量掃描"):
            m = get_stock_map()
            res = scan_logic(list(m.keys()), m)
            st.session_state.scan_res = random.sample(res, min(5, len(res)))
        
        if 'scan_res' in st.session_state:
            for s in st.session_state.scan_res:
                st.markdown(f"<div class='stock-card'><h4>{s['代碼']} - {s['產業']} | ${s['現價']}</h4><p>量: {s['成交量']}張 | 策略: {s['策略']}</p><p>🛑 停損: {s['建議停損']} | 🎯 停利: {s['建議停利']}</p><a href='{s['連結']}'>📈 看線圖</a></div>", unsafe_allow_html=True)
                if st.button(f"買進 {s['代碼']}", key=f"b_{s['代碼']}"):
                    cost = 1000 * s['現價']
                    if st.session_state.bal >= cost:
                        st.session_state.bal -= cost
                        p = st.session_state.port
                        p[s['代碼']] = p.get(s['代碼'], {'q':0, 'c':0})
                        p[s['代碼']]['q'] += 1; p[s['代碼']]['c'] += cost
                        supabase.table("users").update({"balance": st.session_state.bal, "portfolio": p}).eq("username", st.session_state.user).execute()
                        st.toast(f"已買入 {s['代碼']}"); time.sleep(0.5); st.rerun()

    with t2:
        st.subheader(f"💰 餘額: ${st.session_state.bal:,.0f}")
        for code, d in list(st.session_state.port.items()):
            now_p = float(yf.download(f"{code}.TW", period="1d", progress=False)['Close'].iloc[-1])
            profit = (now_p * d['q'] * 1000) - d['c']
            color = "profit-up" if profit >= 0 else "profit-down"
            st.markdown(f"<div class='stock-card'><b>{code}</b> | {d['q']}張 | 損益: <span class='{color}'>${profit:,.0f}</span></div>", unsafe_allow_html=True)
            if st.button(f"賣出 {code}", key=f"s_{code}"):
                st.session_state.bal += (d['q'] * 1000 * now_p)
                del st.session_state.port[code]
                supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                st.rerun()
