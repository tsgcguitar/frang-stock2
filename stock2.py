import streamlit as st
import yfinance as yf
import pandas as pd
import random
import time
import twstock
from supabase import create_client, Client

# --- 1. 系統與雲端資料庫設定 ---
st.set_page_config(page_title="從從容容飆股王", layout="wide", page_icon="💹")

# Supabase 設定 (請確保 Table 有 username, balance, portfolio 三個欄位)
SUPABASE_URL = "https://jhphmcbqtprfhvdkklps.supabase.co"
SUPABASE_KEY = "sb_publishable_qfe3kH2yYYXN_PI7KNCZMg_UJmcvJWE"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("⚠️ 雲端資料庫連線失敗")

# --- UI 風格優化 ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #E0E0E0; }
    .stock-card { 
        background-color: #161B22; border: 1px solid #30363D; 
        padding: 20px; border-radius: 12px; margin-bottom: 15px; 
    }
    .profit-up { color: #FF4B4B; font-weight: bold; } /* 紅色漲 */
    .profit-down { color: #00D084; font-weight: bold; } /* 綠色跌 */
    .metric-box { background: #1f2937; padding: 15px; border-radius: 10px; margin: 10px 0; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 雲端資料庫邏輯 ---
def get_or_create_user(username):
    res = supabase.table("users").select("*").eq("username", username).execute()
    if res.data:
        return res.data[0]['balance'], res.data[0]['portfolio']
    else:
        default_bal, default_port = 1000000.0, {}
        supabase.table("users").insert({"username": username, "balance": default_bal, "portfolio": default_port}).execute()
        return default_bal, default_port

def save_user_state(username, bal, port):
    supabase.table("users").update({"balance": bal, "portfolio": port}).eq("username", username).execute()

# --- 3. 核心選股引擎 ---
@st.cache_data(ttl=86400)
def get_all_tickers():
    # 抓取全台股清單 (上市+上櫃)
    tickers = [f"{c}.TW" for c in twstock.twse.keys() if len(c)==4]
    tickers += [f"{c}.TWO" for c in twstock.tpex.keys() if len(c)==4]
    return tickers

def scan_logic(tickers):
    qualified = []
    progress = st.progress(0)
    status = st.empty()
    
    # 批次處理以提升速度
    batch_size = 50
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        status.text(f"🚀 掃描中... {i}/{len(tickers)}")
        progress.progress(i / len(tickers))
        
        try:
            # 下載 80 天資料確保有足夠均線計算空間
            data = yf.download(batch, period="80d", group_by='ticker', threads=True, progress=False)
            for t in batch:
                try:
                    df = data[t].dropna() if len(batch) > 1 else data.dropna()
                    if len(df) < 65: continue 
                    
                    closes = df['Close']
                    vols = df['Volume']
                    
                    # 計算均線
                    ma5, ma10, ma20 = closes.rolling(5).mean().iloc[-1], closes.rolling(10).mean().iloc[-1], closes.rolling(20).mean().iloc[-1]
                    ma60, ma60_prev = closes.rolling(60).mean().iloc[-1], closes.rolling(60).mean().iloc[-2]
                    
                    # 篩選條件
                    ma_list = [ma5, ma10, ma20]
                    tangle_gap = (max(ma_list) - min(ma_list)) / min(ma_list)
                    
                    cond_tangle = tangle_gap <= 0.03            # 1. 5/10/20MA 糾結 3%
                    cond_ma60_up = ma60 > ma60_prev            # 2. 60MA 方向向上
                    cond_break = closes.iloc[-1] > max(ma_list + [ma60]) # 3. 站上所有均線
                    cond_near = (closes.iloc[-1] - ma5) / ma5 <= 0.05    # 4. 離5MA 5%內
                    cond_vol = vols.iloc[-1] > vols.rolling(20).mean().iloc[-1] * 1.5 # 5. 量增 1.5 倍
                    cond_min_vol = vols.iloc[-1] >= 1000000    # 6. 基本量 1000 張
                    
                    if cond_tangle and cond_ma60_up and cond_break and cond_near and cond_vol and cond_min_vol:
                        qualified.append({
                            "代碼": t.split('.')[0],
                            "現價": round(closes.iloc[-1], 2),
                            "成交量": int(vols.iloc[-1] // 1000),
                            "建議停損": round(ma60, 2),
                            "建議停利": round(closes.iloc[-1] * 1.15, 2),
                            "連結": f"https://www.wantgoo.com/stock/{t.split('.')[0]}"
                        })
                except: continue
        except: continue
    progress.empty(); status.empty()
    return qualified

# --- 4. 介面流程 ---
if 'login' not in st.session_state: st.session_state.login = False

with st.sidebar:
    st.title("從從容容飆股王")
    if st.session_state.login:
        st.success(f"👤 會員：{st.session_state.user}")
        
        # 計算總損益以顯示在餘額下方
        total_p = st.session_state.get('last_total_profit', 0)
        p_color = "#FF4B4B" if total_p >= 0 else "#00D084"
        
        st.markdown(f"""
        <div class='metric-box'>
            <small>💰 模擬倉餘額</small><br>
            <span style='font-size:20px; font-weight:bold;'>${st.session_state.bal:,.0f}</span><br>
            <small>📈 總未實現損益</small><br>
            <span style='color:{p_color}; font-weight:bold;'>${total_p:,.0f}</span>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("安全登出"):
            st.session_state.clear()
            st.rerun()

if not st.session_state.login:
    # --- 訂閱頁面 ---
    st.title("🏹 尋找下一檔起漲黑馬")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<div class='stock-card' style='text-align:center;'><h3>🌙 月租版</h3><h2>NT$ 299</h2></div>", unsafe_allow_html=True)
    with col2:
        st.markdown("<div class='stock-card' style='text-align:center; border-color:#FF4B4B;'><h3>☀️ 年租版</h3><h2>NT$ 2,990</h2><p>(省2個月)</p></div>", unsafe_allow_html=True)
    
    if st.button("💳 點我查看匯款與訂閱資訊", type="primary"):
        st.info("🏦 **永豐銀行 (807)** | 帳號：**148-018-00054187**\n\n📩 請截圖轉帳後5碼聯繫 **官方LINE: 811162**")

    st.divider()
    u = st.text_input("輸入帳號 (自訂名稱)")
    p = st.text_input("輸入授權碼", type="password")
    if st.button("啟動雷達"):
        if p == "STOCK2026" and u:
            bal, port = get_or_create_user(u)
            st.session_state.update({"login": True, "user": u, "bal": bal, "port": port})
            st.rerun()
        else: st.error("授權碼錯誤")

else:
    # --- 登入後主程式 ---
    t1, t2 = st.tabs(["🚀 飆股雷達掃描", "💼 雲端模擬倉"])
    
    with t1:
        if st.button("🔍 開始掃描全台股 (需時約 1-2 分鐘)", type="primary"):
            all_t = get_all_tickers()
            res = scan_logic(all_t)
            st.session_state.scan_res = random.sample(res, min(5, len(res))) if res else []
            if not res: st.warning("今日暫無符合條件股票")
        
        if 'scan_res' in st.session_state:
            for s in st.session_state.scan_res:
                with st.container(border=True):
                    st.markdown(f"### {s['代碼']} | 現價: {s['現價']} | 量: {s['成交量']}張")
                    st.markdown(f"🛑 停損: {s['建議停損']} | 🎯 停利: {s['建議停利']} | [📈 看線圖]({s['連結']})")
                    
                    c1, c2 = st.columns([1, 1])
                    num = c1.number_input("購買張數", 1, 100, key=f"buy_n_{s['代碼']}")
                    if c2.button(f"確認買進 {s['代碼']}", key=f"btn_b_{s['代碼']}"):
                        cost = num * 1000 * s['現價']
                        if st.session_state.bal >= cost:
                            st.session_state.bal -= cost
                            p = st.session_state.port
                            # 更新持股邏輯 (攤平計算)
                            existing = p.get(s['代碼'], {'q': 0, 'c': 0})
                            p[s['代碼']] = {'q': existing['q'] + num, 'c': existing['c'] + cost}
                            save_user_state(st.session_state.user, st.session_state.bal, p)
                            st.toast(f"✅ 已買進 {s['代碼']} {num} 張")
                            time.sleep(1); st.rerun()
                        else: st.error("餘額不足")

    with t2:
        st.subheader("📊 持股與損益 (點擊刷新可獲取最新價)")
        if st.button("🔄 刷新即時損益金額"): st.rerun()
        
        if not st.session_state.port:
            st.info("目前尚無持股")
        else:
            total_unrealized = 0
            # 批次下載目前持股價格
            codes = [f"{c}.TW" if len(c)==4 else c for c in st.session_state.port.keys()]
            price_data = yf.download(codes, period="1d", progress=False)['Close']
            
            for code, data in list(st.session_state.port.items()):
                try:
                    # 處理單檔與多檔價格回傳格式不同問題
                    current_p = float(price_data[f"{code}.TW"].iloc[-1]) if len(codes) > 1 else float(price_data.iloc[-1])
                except: current_p = data['c']/(data['q']*1000) # 抓不到則用成本
                
                mkt_val = current_p * data['q'] * 1000
                profit = mkt_val - data['c']
                total_unrealized += profit
                p_rate = (profit / data['c']) * 100
                
                with st.container(border=True):
                    col_info, col_act = st.columns([3, 1])
                    color = "profit-up" if profit >= 0 else "profit-down"
                    col_info.markdown(f"""
                    **{code}** ({data['q']} 張)  
                    現價: **{current_p:.2f}** | 成本: {data['c']/(data['q']*1000):.2f}  
                    損益: <span class='{color}'>${profit:,.0f} ({p_rate:.2f}%)</span>
                    """, unsafe_allow_html=True)
                    
                    s_num = col_act.number_input("張數", 1, data['q'], key=f"s_n_{code}")
                    if col_act.button(f"賣出", key=f"s_b_{code}"):
                        sell_val = s_num * 1000 * current_p
                        st.session_state.bal += sell_val
                        if s_num == data['q']:
                            del st.session_state.port[code]
                        else:
                            # 按比例扣除成本
                            ratio = (data['q'] - s_num) / data['q']
                            st.session_state.port[code]['q'] -= s_num
                            st.session_state.port[code]['c'] *= ratio
                        save_user_state(st.session_state.user, st.session_state.bal, st.session_state.port)
                        st.success(f"賣出成功，入帳 ${sell_val:,.0f}")
                        time.sleep(1); st.rerun()
            
            st.session_state.last_total_profit = total_unrealized
            st.divider()
            if st.button("⚠️ 重置帳戶 (100萬初始狀態)"):
                save_user_state(st.session_state.user, 1000000.0, {})
                st.rerun()
