import streamlit as st
import yfinance as yf
import pandas as pd
import json
import random
import time
import twstock
from supabase import create_client, Client

# --- 1. 系統與雲端資料庫設定 ---
st.set_page_config(page_title="從從容容飆股王", layout="wide", page_icon="💹")

# 請替換成您的 Supabase 資訊 (建議放入 .streamlit/secrets.toml)
SUPABASE_URL = "https://jhphmcbqtprfhvdkklps.supabase.co"
SUPABASE_KEY = "sb_publishable_qfe3kH2yYYXN_PI7KNCZMg_UJmcvJWE"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("⚠️ 雲端資料庫連線失敗，請檢查金鑰設定。")

# --- UI 風格優化 (深色專業風) ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #E0E0E0; }
    .stButton>button { border-radius: 8px; font-weight: bold; width: 100%; }
    .stock-card { 
        background-color: #161B22; border: 1px solid #30363D; 
        padding: 20px; border-radius: 12px; margin-bottom: 15px; 
    }
    .profit-up { color: #FF4B4B; font-weight: bold; }
    .profit-down { color: #00D084; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 雲端資料庫邏輯 ---
def get_or_create_user(username):
    res = supabase.table("users").select("*").eq("username", username).execute()
    if res.data:
        return res.data[0]['balance'], res.data[0]['portfolio']
    else:
        default_bal = 1000000.0
        default_port = {}
        supabase.table("users").insert({"username": username, "balance": default_bal, "portfolio": default_port}).execute()
        return default_bal, default_port

def save_user_state(username, bal, port):
    supabase.table("users").update({"balance": bal, "portfolio": port}).eq("username", username).execute()

# --- 3. 核心選股引擎 ---
@st.cache_data(ttl=86400)
def get_stock_map():
    mapping = {}
    for code, info in twstock.twse.items():
        if len(code) == 4: mapping[f"{code}.TW"] = info.industry
    for code, info in twstock.tpex.items():
        if len(code) == 4: mapping[f"{code}.TWO"] = info.industry
    return mapping

def scan_logic(tickers, info_map):
    qualified = []
    progress = st.progress(0)
    status = st.empty()
    
    # 每次掃描 100 檔避免逾時
    batch_size = 100
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        status.text(f"🚀 正在掃描台股精華... ({i}/{len(tickers)})")
        progress.progress(i / len(tickers))
        
        try:
            data = yf.download(batch, period="100d", group_by='ticker', threads=True, progress=False)
            for t in batch:
                try:
                    df = data[t].dropna()
                    if len(df) < 60: continue # 需求 2: 排除資料不足
                    
                    last_close = df['Close'].iloc[-1]
                    last_vol = df['Volume'].iloc[-1]
                    avg_vol_20 = df['Volume'].rolling(20).mean().iloc[-1]
                    
                    # 均線計算
                    ma5 = df['Close'].rolling(5).mean().iloc[-1]
                    ma10 = df['Close'].rolling(10).mean().iloc[-1]
                    ma20 = df['Close'].rolling(20).mean().iloc[-1]
                    ma60 = df['Close'].rolling(60).mean().iloc[-1]
                    
                    ma_list = [ma5, ma10, ma20, ma60]
                    max_ma, min_ma = max(ma_list), min_ma(ma_list)
                    
                    # 篩選條件 (需求 2)
                    cond_tangle = (max_ma - min_ma) / min_ma <= 0.03 # 均線糾結 3%
                    cond_break = last_close > max_ma                 # 站上所有均線
                    cond_near = (last_close - ma5) / ma5 <= 0.05    # 離5MA不超過5%
                    cond_vol = last_vol > avg_vol_20 * 1.5         # 量增 1.5 倍
                    cond_min_vol = last_vol >= 1000000             # 基本量 1000 張

                    if cond_tangle and cond_break and cond_near and cond_vol and cond_min_vol:
                        sid = t.split('.')[0]
                        qualified.append({
                            "代碼": sid, "產業": info_map.get(t, "其他"),
                            "現價": round(last_close, 2), "成交量": int(last_vol // 1000),
                            "建議停損": round(ma60, 2), "建議停利": round(last_close * 1.15, 2),
                            "策略建議": "四線糾結+量能爆發", "連結": f"https://www.wantgoo.com/stock/{sid}"
                        })
                except: continue
        except: continue
    progress.empty()
    status.empty()
    return qualified

# --- 4. UI 流程 ---

# 登入狀態檢查
if 'login' not in st.session_state: st.session_state.login = False

with st.sidebar:
    st.title("從從容容飆股王")
    if st.session_state.login:
        st.success(f"👤 會員：{st.session_state.user}")
        st.metric("💰 模擬倉餘額", f"${st.session_state.bal:,.0f}")
        if st.button("安全登出"):
            st.session_state.clear()
            st.rerun()
    st.divider()
    st.info("📢 **操作小提醒**\n1. 跌破60MA(季線)果斷停損。\n2. 5%內起漲點追蹤。\n3. 量增1.5倍確認主力表態。")

if not st.session_state.login:
    # --- 登入前頁面 (需求 10, 11) ---
    st.title("🏹 尋找下一檔翻倍黑馬")
    st.markdown("#### *「專為不追高，只買起漲點的投資者設計」*")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""<div style='border:1px solid #30363D; padding:20px; border-radius:10px; text-align:center;'>
                    <h3>🌙 月租專業版</h3><h2>NT$ 299</h2></div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("""<div style='border:1px solid #FF4B4B; padding:20px; border-radius:10px; text-align:center;'>
                    <h3>☀️ 年租尊榮版</h3><h2>NT$ 2,990</h2><p>(省下 2 個月)</p></div>""", unsafe_allow_html=True)
    
    if st.button("💳 點我查看匯款與訂閱開通資訊"):
        st.success("🏦 **匯款資訊**：永豐銀行 (807) | 帳號：148-018-00054187")
        st.info("📩 **開通方式**：截圖轉帳後5碼聯繫 **官方LINE: 811162**，30分鐘內開通。")

    st.divider()
    st.subheader("🔐 會員登入")
    u = st.text_input("輸入帳號")
    p = st.text_input("輸入授權碼", type="password")
    if st.button("啟動雷達", type="primary"):
        if p == "STOCK2026" and u:
            bal, port = get_or_create_user(u)
            st.session_state.login, st.session_state.user = True, u
            st.session_state.bal, st.session_state.port = bal, port
            st.rerun()
        else: st.error("授權碼錯誤，請聯繫客服。")

else:
    # --- 登入後頁面 ---
    t1, t2 = st.tabs(["🚀 極速飆股掃描", "💼 雲端模擬倉"])
    
    with t1:
        if st.button("🔍 開始全量掃描 (需時較久)", type="primary"):
            imap = get_stock_map()
            res = scan_logic(list(imap.keys()), imap)
            st.session_state.scan_res = random.sample(res, min(5, len(res)))
            st.success(f"掃描完成！符合條件共 {len(res)} 檔，系統隨機推薦 5 檔。")
        
        if 'scan_res' in st.session_state:
            for s in st.session_state.scan_res:
                st.markdown(f"""<div class='stock-card'>
                    <h3 style='margin:0;'>{s['代碼']} - {s['產業']} | ${s['現價']}</h3>
                    <p>量: {s['成交量']}張 | {s['策略建議']}</p>
                    <p>🛑 建議停損: {s['建議停損']} | 🎯 建議停利: {s['建議停利']}</p>
                    <a href='{s['連結']}' target='_blank'>📈 查看線圖</a>
                </div>""", unsafe_allow_html=True)
                
                b_col1, b_col2 = st.columns([1, 1])
                num = b_col1.number_input(f"張數 ({s['代碼']})", 1, 50, key=f"n_{s['代碼']}")
                if b_col2.button(f"買進 {s['代碼']}", key=f"b_{s['代碼']}"):
                    cost = num * 1000 * s['現價']
                    if st.session_state.bal >= cost:
                        st.session_state.bal -= cost
                        # 更新持股
                        p = st.session_state.port
                        p[s['代碼']] = p.get(s['代碼'], {'q':0, 'c':0})
                        p[s['代['代碼']]['q'] += num
                        p[s['代碼']]['c'] += cost
                        save_user_state(st.session_state.user, st.session_state.bal, p)
                        st.toast("雲端同步買入成功！")
                        time.sleep(0.5); st.rerun()
                    else: st.error("餘額不足")

    with t2:
        st.subheader("📊 即時損益監控")
        if not st.session_state.port:
            st.info("目前無持股。")
        else:
            total_profit = 0
            # 需求 7: 重新抓取目前股價
            p_list = list(st.session_state.port.keys())
            curr_prices = yf.download([f"{c}.TW" for c in p_list], period="1d", progress=False)['Close']
            
            for code, d in st.session_state.port.items():
                try:
                    now_p = float(curr_prices[f"{code}.TW"].iloc[-1]) if len(p_list)>1 else float(curr_prices.iloc[-1])
                except: now_p = d['c']/(d['q']*1000)
                
                mkt_val = now_p * d['q'] * 1000
                profit = mkt_val - d['c']
                total_profit += profit
                p_rate = (profit / d['c']) * 100
                color = "profit-up" if profit >= 0 else "profit-down"
                
                with st.container(border=True):
                    c_i, c_p, c_a = st.columns([1, 1.5, 1])
                    c_i.markdown(f"**{code}**\n\n{d['q']} 張")
                    c_p.markdown(f"現價: **{now_p:.2f}** (成本: {d['c']/(d['q']*1000):.2f})")
                    c_p.markdown(f"損益: <span class='{color}'>${profit:,.0f} ({p_rate:.2f}%)</span>", unsafe_allow_html=True)
                    
                    s_num = c_a.number_input("賣出張數", 1, d['q'], key=f"sq_{code}")
                    if c_a.button(f"賣出 {code}", key=f"sb_{code}"):
                        sell_get = s_num * 1000 * now_p
                        st.session_state.bal += sell_get
                        if s_num == d['q']: del st.session_state.port[code]
                        else:
                            ratio = (d['q'] - s_num) / d['q']
                            st.session_state.port[code]['q'] -= s_num
                            st.session_state.port[code]['c'] *= ratio
                        save_user_state(st.session_state.user, st.session_state.bal, st.session_state.port)
                        st.rerun()
            
            st.divider()
            st.markdown(f"### 🏆 總計未實現損益: <span class='{'profit-up' if total_profit>=0 else 'profit-down'}'>${total_profit:,.0f}</span>", unsafe_allow_html=True)
            if st.button("⚠️ 重置雲端帳戶"):
                save_user_state(st.session_state.user, 1000000.0, {})
                st.rerun()

