import streamlit as st
import yfinance as yf
import pandas as pd
import sqlite3
import json
import random
import time
import twstock
from datetime import datetime

# --- 1. 系統設定與資料庫 ---
st.set_page_config(page_title="台股全量飆股雷達 (極速版)", layout="wide", page_icon="⚡")
DB_FILE = "trading_radar_opt.db"

def init_db():
    """初始化資料庫"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                balance REAL,
                portfolio TEXT
            )
        """)

def get_or_create_user(username):
    """取得用戶資料，若不存在則自動建立 (預設100萬)"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        row = cursor.execute("SELECT balance, portfolio FROM users WHERE username = ?", (username,)).fetchone()
        
        if row:
            try:
                port = json.loads(row[1])
            except:
                port = {}
            return row[0], port
        else:
            # 自動建立新用戶
            default_bal = 1000000.0
            default_port = "{}"
            cursor.execute("INSERT INTO users VALUES (?, ?, ?)", (username, default_bal, default_port))
            conn.commit()
            return default_bal, {}

def save_user_state(username, bal, port):
    """儲存用戶狀態"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("UPDATE users SET balance = ?, portfolio = ? WHERE username = ?", (bal, json.dumps(port), username))

# --- 2. 極速核心引擎 (修復版) ---

@st.cache_data(ttl=86400)
def get_valid_tw_tickers():
    """
    修正版：使用 .type 讀取屬性，避免 TypeError
    """
    twse = twstock.twse
    tpex = twstock.tpex
    
    codes = []
    
    # 修正重點：info 是 namedtuple，必須用 info.type 讀取
    for code, info in twse.items():
        try:
            if info.type == '股票' and len(code) == 4:
                codes.append(f"{code}.TW")
        except:
            continue
            
    for code, info in tpex.items():
        try:
            if info.type == '股票' and len(code) == 4:
                codes.append(f"{code}.TWO")
        except:
            continue
            
    return codes

@st.cache_data(ttl=1800)
def fetch_and_scan_stocks(tickers):
    """大批量下載與運算"""
    qualified_list = []
    
    # 分批下載，每批 300 檔
    chunk_size = 300
    chunks = [tickers[i:i + chunk_size] for i in range(0, len(tickers), chunk_size)]
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_chunks = len(chunks)
    
    for i, batch in enumerate(chunks):
        status_text.text(f"🚀 正在光速掃描第 {i+1}/{total_chunks} 批股票... ({len(batch)} 檔)")
        progress_bar.progress((i) / total_chunks)
        
        try:
            data = yf.download(batch, period="40d", group_by='ticker', threads=True, progress=False)
            
            # yfinance 結構處理
            if len(batch) == 1: continue 
            downloaded_tickers = data.columns.levels[0] if isinstance(data.columns, pd.MultiIndex) else []
            
            for t in downloaded_tickers:
                try:
                    df = data[t].dropna()
                    if len(df) < 20: continue

                    close = float(df['Close'].iloc[-1])
                    vol = float(df['Volume'].iloc[-1])
                    
                    # 1. 成交量 > 1000張 (100萬股)
                    if vol < 1000000: continue
                    
                    ma5 = df['Close'].rolling(5).mean().iloc[-1]
                    ma10 = df['Close'].rolling(10).mean().iloc[-1]
                    ma20 = df['Close'].rolling(20).mean().iloc[-1]
                    
                    ma_list = [ma5, ma10, ma20]
                    max_ma = max(ma_list)
                    min_ma = min(ma_list)
                    
                    # 2. 均線糾結 (3%)
                    if (max_ma - min_ma) / min_ma > 0.03: continue
                    
                    # 3. 突破所有均線
                    if close <= max_ma: continue
                    
                    # 4. 起漲點 (離 5MA 不超過 3.5%)
                    if (close - ma5) / ma5 > 0.035: continue
                    
                    stock_id = t.split('.')[0]
                    qualified_list.append({
                        "代碼": stock_id,
                        "現價": round(close, 2),
                        "成交量": int(vol // 1000),
                        "建議停損": round(min_ma * 0.98, 2),
                        "建議停利": round(close * 1.15, 2),
                        "策略建議": "均線糾結突破",
                        "連結": f"https://www.wantgoo.com/stock/{stock_id}"
                    })
                except: continue
        except: continue
            
    progress_bar.progress(1.0)
    status_text.empty()
    return qualified_list

# --- 3. UI 介面 ---
init_db()

if 'login' not in st.session_state: st.session_state.login = False
if 'bal' not in st.session_state: st.session_state.bal = 1000000.0
if 'port' not in st.session_state: st.session_state.port = {}

# 側邊欄
with st.sidebar:
    st.title("⚡ 極速飆股雷達")
    if st.session_state.login:
        st.success(f"👤 {st.session_state.user}")
        st.metric("💰 餘額", f"${st.session_state.bal:,.0f}")
        if st.button("登出"):
            st.session_state.clear()
            st.rerun()
    st.divider()
    st.info("訂閱官方LINE: 811162")

# 主流程
if not st.session_state.login:
    st.title("🏹 台股全自動飆股雷達 (加速版)")
    col1, col2 = st.columns(2)
    with col1:
        st.info("### 🌙 月租 NT$ 199")
    with col2:
        st.error("### ☀️ 年租 NT$ 1,990")
        
    if st.button("查看付款資訊", use_container_width=True):
        st.warning("銀行：永豐銀行 (807) | 帳號：148-018-00054187")

    st.divider()
    
    # 簡化登入介面
    st.subheader("🔐 會員登入")
    u = st.text_input("請輸入您的帳號 (系統自動記錄)")
    p = st.text_input("請輸入授權碼", type="password")
    
    if st.button("登入系統", type="primary", use_container_width=True):
        if p == "STOCK2026":
            if u:
                bal, port = get_or_create_user(u)
                st.session_state.login = True
                st.session_state.user = u
                st.session_state.bal = bal
                st.session_state.port = port
                st.rerun()
            else:
                st.warning("請輸入帳號名稱以利保存紀錄")
        else:
            st.error("授權碼錯誤！請聯繫管理員。")

else:
    t1, t2 = st.tabs(["🚀 極速掃描", "💼 模擬倉"])
    
    with t1:
        st.write("### ⚡ 全台股即時掃描")
        if st.button("開始全量掃描", type="primary"):
            with st.spinner("正在讀取證交所最新清單..."):
                all_tickers = get_valid_tw_tickers()
                st.toast(f"已載入 {len(all_tickers)} 檔有效股票", icon="✅")
            
            results = fetch_and_scan_stocks(all_tickers)
            
            if len(results) > 5:
                st.session_state.scan_res = random.sample(results, 5)
                st.success(f"掃描完畢！共發現 {len(results)} 檔，隨機顯示 5 檔。")
            else:
                st.session_state.scan_res = results
                if not results: st.warning("今日無符合條件標的")
                else: st.success("掃描完畢！")

        if 'scan_res' in st.session_state:
            for s in st.session_state.scan_res:
                with st.expander(f"🔥 {s['代碼']} | ${s['現價']} | 糾結突破", expanded=True):
                    c1, c2 = st.columns(2)
                    c1.write(f"量: {s['成交量']}張")
                    c1.write(f"停損: {s['建議停損']} | 停利: {s['建議停利']}")
                    c1.markdown(f"[線圖連結]({s['連結']})")
                    
                    buy_n = c2.number_input("張數", 1, 10, key=f"b_{s['代碼']}")
                    cost = buy_n * 1000 * s['現價']
                    c2.write(f"總價: ${cost:,.0f}")
                    if c2.button(f"買進 {s['代碼']}", key=f"btn_{s['代碼']}"):
                        if st.session_state.bal >= cost:
                            st.session_state.bal -= cost
                            old = st.session_state.port.get(s['代碼'], {'q':0, 'c':0})
                            st.session_state.port[s['代碼']] = {
                                'q': old['q'] + buy_n,
                                'c': old['c'] + cost
                            }
                            save_user_state(st.session_state.user, st.session_state.bal, st.session_state.port)
                            st.toast("買入成功！")
                            time.sleep(1); st.rerun()
                        else: st.error("餘額不足")

    with t2:
        st.subheader("持股明細")
        if not st.session_state.port: st.info("空倉")
        else:
            total_profit = 0
            for c, v in list(st.session_state.port.items()):
                try: 
                    curr = yf.Ticker(f"{c}.TW").fast_info.last_price
                    if not curr: curr = yf.Ticker(f"{c}.TWO").fast_info.last_price
                except: curr = v['c'] / (v['q']*1000)
                
                if not curr: curr = v['c'] / (v['q']*1000)
                
                mkt_val = curr * v['q'] * 1000
                profit = mkt_val - v['c']
                pct = (profit / v['c']) * 100
                total_profit += profit
                
                color = "red" if profit >= 0 else "green"
                
                with st.container(border=True):
                    col1, col2, col3 = st.columns([2,2,1])
                    col1.write(f"**{c}** {v['q']}張")
                    col1.write(f"均價: {v['c']/(v['q']*1000):.1f}")
                    col2.markdown(f"損益: :{color}[${profit:,.0f} ({pct:.1f}%)]")
                    if col3.button("賣", key=f"s_{c}"):
                        st.session_state.bal += mkt_val
                        del st.session_state.port[c]
                        save_user_state(st.session_state.user, st.session_state.bal, st.session_state.port)
                        st.rerun()
            
            st.divider()
            st.markdown(f"### 總損益: :{'red' if total_profit>0 else 'green'}[${total_profit:,.0f}]")
            if st.button("重置帳戶"):
                 save_user_state(st.session_state.user, 1000000.0, {})
                 st.session_state.bal = 1000000.0
                 st.session_state.port = {}
                 st.rerun()
