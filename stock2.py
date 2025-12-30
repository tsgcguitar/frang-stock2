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

# --- 2. 全新 UI：藍色高科技光感風格 (參考 cite: 8) ---
st.markdown("""
    <style>
    /* 整體背景 - 深藍科技漸層 */
    .stApp {
        background: linear-gradient(to bottom right, #001233, #000814);
        color: #E0F7FA; /* 亮青白色文字 */
    }

    /* 標題與選中分頁 - 發光青色 */
    h1, h2, h3, span, p, .stTabs [aria-selected="true"] {
        color: #00E5FF !important; /* 電光青 */
        text-shadow: 0 0 8px rgba(0, 229, 255, 0.4);
    }
    
    /* 未選中分頁顏色 */
    .stTabs [data-baseweb="tab"] { color: #577399; }

    /* 股票卡片 - 半透明藍色玻璃面板 + 發光邊框 */
    .stock-card {
        background: rgba(0, 30, 60, 0.75); /* 半透明深藍 */
        border: 1px solid #00B0FF; /* 亮藍邊框 */
        box-shadow: 0 0 15px rgba(0, 176, 255, 0.3) inset; /* 內部光暈 */
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 20px;
        backdrop-filter: blur(5px); /* 毛玻璃效果 */
    }

    /* 按鈕美化 - 藍色漸層光暈 */
    .stButton>button {
        background: linear-gradient(to bottom, #00B0FF, #0081CB);
        color: #FFFFFF !important;
        border: none;
        border-radius: 8px;
        font-weight: bold;
        transition: 0.3s;
        box-shadow: 0 0 10px rgba(0, 176, 255, 0.5);
    }
    .stButton>button:hover {
        background: linear-gradient(to bottom, #40CFFF, #00A5FF);
        box-shadow: 0 0 20px rgba(64, 207, 255, 0.8);
        transform: translateY(-2px);
    }

    /* 獲利與虧損 - 霓虹光感 */
    .profit-up { color: #FF3333 !important; text-shadow: 0 0 5px rgba(255, 51, 51, 0.6); } /* 霓虹紅 */
    .profit-down { color: #00FF66 !important; text-shadow: 0 0 5px rgba(0, 255, 102, 0.6); } /* 霓虹綠 */

    /* 輸入框優化 */
    [data-baseweb="input"] {
        background-color: rgba(0, 40, 80, 0.8) !important;
        border-color: #00B0FF !important;
        color: #00E5FF !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 核心功能函式 ---
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
    # 限制掃描數量以維持效能，若要全掃請將 [:300] 拿掉
    scan_limit = 300
    target_tickers = tickers[:scan_limit]
    
    for i, t in enumerate(target_tickers):
        status.markdown(f"📡 系統掃描中... **{t}** ({i+1}/{len(target_tickers)})")
        progress.progress((i+1) / len(target_tickers))
        try:
            df = yf.download(t, period="100d", progress=False).dropna()
            if len(df) < 60: continue
            
            close, vol = df['Close'].iloc[-1], df['Volume'].iloc[-1]
            ma5 = df['Close'].rolling(5).mean().iloc[-1]
            ma10 = df['Close'].rolling(10).mean().iloc[-1]
            ma20 = df['Close'].rolling(20).mean().iloc[-1]
            ma60 = df['Close'].rolling(60).mean().iloc[-1]
            avg_v20 = df['Volume'].rolling(20).mean().iloc[-1]
            
            mas = [ma5, ma10, ma20, ma60]
            # 規格邏輯檢查
            cond_tangle = (max(mas)-min(mas))/min(mas) <= 0.03
            cond_break = close > max(mas)
            cond_near = (close-ma5)/ma5 <= 0.05
            cond_vol = vol > avg_v20*1.5
            cond_min_vol = vol >= 1000000 # yfinance volume單位為股

            if cond_tangle and cond_break and cond_near and cond_vol and cond_min_vol:
                qualified.append({
                    "代碼": t.split('.')[0], "產業": info_map.get(t), "現價": round(close,2),
                    "成交量": int(vol//1000), "建議停損": round(ma60,2), "建議停利": round(close*1.15,2),
                    "策略": "均線糾結+爆量起漲", "連結": f"https://www.wantgoo.com/stock/{t.split('.')[0]}"
                })
        except: continue
    progress.empty()
    status.empty()
    return qualified

# --- 4. 登入前頁面 ---
if 'login' not in st.session_state or not st.session_state.login:
    st.title("🏹 從從容容飆股王")
    st.markdown("#### *專為不喜歡追高但又想要買在起漲點的投資者設計*")
    
    col1, col2 = st.columns(2)
    with col1: st.markdown("<div class='stock-card'><h3>🌙 月租版</h3><h1>$299</h1></div>", unsafe_allow_html=True)
    with col2: st.markdown("<div class='stock-card'><h3>☀️ 年費版</h3><h1>$2,990</h1><p>省2個月</p></div>", unsafe_allow_html=True)
    
    with st.expander("💳 顯示訂閱付款資訊"):
        st.write("🏦 永豐銀行 (807) | 帳號：148-018-00054187")
        st.info("轉帳後截圖聯繫 官方Line: 811162，將於30分鐘內開通。")

    st.divider()
    u = st.text_input("👤 帳號")
    p = st.text_input("🔑 授權碼", type="password")
    if st.button("🚀 登入系統"):
        if p == "STOCK2026":
            res = supabase.table("users").select("*").eq("username", u).execute()
            if res.data:
                bal, port = res.data[0]['balance'], res.data[0]['portfolio']
            else:
                bal, port = 1000000.0, {}
                supabase.table("users").insert({"username":u, "balance":bal, "portfolio":port}).execute()
            st.session_state.login, st.session_state.user, st.session_state.bal, st.session_state.port = True, u, bal, port
            st.rerun()
        else: st.error("授權碼錯誤")

# --- 5. 登入後頁面 ---
else:
    t1, t2 = st.tabs(["🚀 飆股雷達", "💼 雲端模擬倉"])
    
    with t1:
        if st.button("🔍 開始全量掃描"):
            m = get_stock_map()
            res = scan_logic(list(m.keys()), m)
            st.session_state.scan_res = random.sample(res, min(5, len(res)))
            st.success(f"掃描完成！共發現 {len(res)} 檔，隨機顯示 5 檔。")
        
        if 'scan_res' in st.session_state:
            for s in st.session_state.scan_res:
                st.markdown(f"""
                <div class='stock-card'>
                    <div style='display:flex; justify-content:space-between; align-items:center;'>
                        <span style='font-size:1.3em;'>{s['代碼']} - {s['產業']}</span>
                        <span style='font-size:1.5em; color:#00E5FF;'>${s['現價']}</span>
                    </div>
                    <hr style='border-color:#00B0FF; opacity:0.3;'>
                    <p>量: {s['成交量']}張 | 策略: {s['策略']}</p>
                    <p>🛑 停損: <span class='profit-up'>{s['建議停損']}</span> | 🎯 停利: <span class='profit-down'>{s['建議停利']}</span></p>
                    <a href='{s['連結']}' target='_blank' style='color:#00E5FF;'>🔗 查看 K 線圖</a>
                </div>""", unsafe_allow_html=True)
                
                b1, b2 = st.columns([1, 1])
                num = b1.number_input(f"張數", 1, 100, key=f"bn_{s['代碼']}")
                if b2.button(f"買進 {s['代碼']}", key=f"b_{s['代碼']}"):
                    cost = num * 1000 * s['現價']
                    if st.session_state.bal >= cost:
                        st.session_state.bal -= cost
                        p = st.session_state.port
                        p[s['代碼']] = p.get(s['代碼'], {'q':0, 'c':0})
                        p[s['代碼']]['q'] += num; p[s['代碼']]['c'] += cost
                        supabase.table("users").update({"balance": st.session_state.bal, "portfolio": p}).eq("username", st.session_state.user).execute()
                        st.toast(f"已買入 {s['代碼']}"); time.sleep(0.5); st.rerun()
                    else: st.error("餘額不足")

    with t2:
        st.subheader(f"💰 帳戶餘額: ${st.session_state.bal:,.0f}")
        if not st.session_state.port:
             st.info("暫無庫存")
        else:
            p_list = [f"{c}.TW" if ".TW" not in c else c for c in st.session_state.port.keys()]
            try: curr_data = yf.download(p_list, period="1d", progress=False)['Close']
            except: curr_data = pd.DataFrame()

            for code, d in list(st.session_state.port.items()):
                try:
                    if len(p_list) == 1: now_p = float(curr_data.iloc[-1])
                    else: now_p = float(curr_data[f"{code}.TW" if ".TW" not in code else code].iloc[-1])
                except: now_p = d['c'] / (d['q'] * 1000)

                profit = (now_p * d['q'] * 1000) - d['c']
                color = "profit-up" if profit < 0 else "profit-down" # 虧損紅/獲利綠
                
                st.markdown(f"""
                <div class='stock-card'>
                    <div style='display:flex; justify-content:space-between;'>
                        <b>{code} ({d['q']}張)</b>
                        <span class='{color}'>{'▼' if profit<0 else '▲'} ${abs(profit):,.0f}</span>
                    </div>
                    <p style='margin:0; opacity:0.8;'>現價: {now_p:.2f} | 成本: {d['c']/(d['q']*1000):.2f}</p>
                </div>""", unsafe_allow_html=True)
                
                if st.button(f"賣出 {code}", key=f"s_{code}"):
                    st.session_state.bal += (d['q'] * 1000 * now_p)
                    del st.session_state.port[code]
                    supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                    st.rerun()
