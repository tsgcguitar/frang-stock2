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

# --- 2. 極速核心引擎 ---

@st.cache_data(ttl=86400)
def get_valid_tw_tickers():
    """取得有效股票代碼"""
    twse = twstock.twse
    tpex = twstock.tpex
    codes = []
    
    # 修正重點：info 是 namedtuple，必須用 info.type 讀取
    for code, info in twse.items():
        try:
            if info.type == '股票' and len(code) == 4:
                codes.append(f"{code}.TW")
        except: continue
            
    for code, info in tpex.items():
        try:
            if info.type == '股票' and len(code) == 4:
                codes.append(f"{code}.TWO")
        except: continue
            
    return codes

@st.cache_data(ttl=1800)
def fetch_and_scan_stocks(tickers):
    """大批量下載與運算"""
    qualified_list = []
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
            if len(batch) == 1: continue 
            downloaded_tickers = data.columns.levels[0] if isinstance(data.columns, pd.MultiIndex) else []
            
            for t in downloaded_tickers:
                try:
                    df = data[t].dropna()
                    if len(df) < 20: continue

                    close = float(df['Close'].iloc[-1])
                    vol = float(df['Volume'].iloc[-1])
                    
                    if vol < 1000000: continue # 量大於1000張
                    
                    ma5 = df['Close'].rolling(5).mean().iloc[-1]
                    ma10 = df['Close'].rolling(10).mean().iloc[-1]
                    ma20 = df['Close'].rolling(20).mean().iloc[-1]
                    
                    ma_list = [ma5, ma10, ma20]
                    max_ma = max(ma_list)
                    min_ma = min(ma_list)
                    
                    if (max_ma - min_ma) / min_ma > 0.03: continue # 糾結3%
                    if close <= max_ma: continue # 突破
                    if (close - ma5) / ma5 > 0.035: continue # 起漲點
                    
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

# --- 側邊欄 (更新文案) ---
with st.sidebar:
    st.title("⚡ 極速飆股雷達")
    
    if st.session_state.login:
        st.success(f"👤 {st.session_state.user}")
        st.metric("💰 模擬倉餘額", f"${st.session_state.bal:,.0f}")
        if st.button("登出系統"):
            st.session_state.clear()
            st.rerun()
    
    st.divider()
    st.markdown("### 關於此工具")
    st.info("""
    這是一款專為不喜歡追高但又想要買在起漲點的投資者設計的雷達。
    """)
    
    st.markdown("### 📢 操作小提醒")
    st.markdown("""
    1. **停損建議**：若收盤價跌破『建議停損點』(通常為均線群底端)，應果斷執行紀律。
    2. **量能門檻**：系統已過濾單日成交量小於 1000 張的冷門股，降低被操控風險。
    3. **產業連動**：若發現同一產業有多檔同時上榜，該族群為當日強勢主流。
    """)
    
    st.divider()
    st.warning("**訂閱問題 官方LINE: 811162**")

# --- 主流程 ---

if not st.session_state.login:
    st.title("🏹 台股全自動飆股雷達")
    
    # 訂閱資訊區塊 (更新文案)
    st.container(border=True)
    c1, c2 = st.columns(2)
    with c1:
        st.info("### 🌙 月租專業版\n**NT$ 199**")
    with c2:
        st.error("### ☀️ 年租尊榮版\n**NT$ 1,990**")
    
    if st.button("查看付款資訊 / 訂閱說明", use_container_width=True):
        st.markdown("""
        ### 匯款資訊
        - **銀行**：永豐銀行 (807)
        - **帳號**：148-018-00054187
        
        ---
        **🔔 開通方式**：
        訂閱後請截圖轉帳後5碼聯繫 **官方LINE: 811162**
        將於30分鐘內開通帳號。
        """)

    st.divider()
    
    # 登入介面
    st.subheader("🔐 會員登入")
    col_login, col_padding = st.columns([1, 1])
    with col_login:
        u = st.text_input("輸入帳號 (系統自動保存紀錄)")
        p = st.text_input("輸入授權碼", type="password")
        
        if st.button("登入雷達", type="primary", use_container_width=True):
            if p == "STOCK2026":
                if u:
                    bal, port = get_or_create_user(u)
                    st.session_state.login = True
                    st.session_state.user = u
                    st.session_state.bal = bal
                    st.session_state.port = port
                    st.rerun()
                else:
                    st.warning("請輸入您的帳號名稱")
            else:
                st.error("授權碼錯誤，請聯繫官方LINE開通。")

else:
    # --- 登入後介面 ---
    t1, t2 = st.tabs(["🚀 極速掃描", "💼 模擬倉"])
    
    # === Tab 1: 掃描 ===
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

    # === Tab 2: 模擬倉 (更新重點：顯示現價、分批賣出) ===
    with t2:
        st.subheader("📊 持股明細與損益")
        
        if not st.session_state.port:
            st.info("目前無持股，請前往掃描頁面挑選標的。")
        else:
            total_profit = 0
            
            for code, data in list(st.session_state.port.items()):
                qty = data['q']
                cost_total = data['c']
                avg_cost = cost_total / (qty * 1000)
                
                # 取得即時現價
                try: 
                    t_obj = yf.Ticker(f"{code}.TW")
                    curr_price = t_obj.fast_info.last_price
                    if not curr_price: 
                        t_obj = yf.Ticker(f"{code}.TWO")
                        curr_price = t_obj.fast_info.last_price
                except: 
                    curr_price = avg_cost # 抓失敗時的備案
                
                if not curr_price: curr_price = avg_cost
                
                # 計算損益
                market_value = curr_price * qty * 1000
                profit = market_value - cost_total
                profit_pct = (profit / cost_total) * 100
                total_profit += profit
                
                color = "red" if profit >= 0 else "green"
                
                # --- 持股卡片 UI ---
                with st.container(border=True):
                    # 分欄佈局：資訊 | 價格 | 賣出操作
                    col_info, col_price, col_action = st.columns([1.5, 1.5, 2])
                    
                    with col_info:
                        st.markdown(f"### **{code}**")
                        st.write(f"持倉: **{qty}** 張")
                        
                    with col_price:
                        st.write(f"均價: {avg_cost:.2f}")
                        st.markdown(f"現價: **{curr_price:.2f}**")
                        st.markdown(f"損益: :{color}[${profit:,.0f} ({profit_pct:.1f}%)]")
                    
                    with col_action:
                        # 分批賣出功能
                        sell_qty = st.number_input(f"賣出張數 ({code})", min_value=1, max_value=qty, key=f"sq_{code}")
                        
                        if st.button(f"賣出 {sell_qty} 張", key=f"sbtn_{code}"):
                            # 計算賣出金額
                            sell_value = sell_qty * 1000 * curr_price
                            
                            # 更新餘額
                            st.session_state.bal += sell_value
                            
                            # 更新持股
                            remaining_qty = qty - sell_qty
                            if remaining_qty == 0:
                                del st.session_state.port[code]
                            else:
                                # 依比例減少總成本 (維持平均成本不變)
                                remaining_cost = cost_total * (remaining_qty / qty)
                                st.session_state.port[code] = {
                                    'q': remaining_qty,
                                    'c': remaining_cost
                                }
                            
                            save_user_state(st.session_state.user, st.session_state.bal, st.session_state.port)
                            st.toast(f"已賣出 {sell_qty} 張 {code}，獲利結算！")
                            time.sleep(1); st.rerun()

            st.divider()
            st.markdown(f"### 🏆 總未實現損益: :{'red' if total_profit>=0 else 'green'}[${total_profit:,.0f}]")
            
            if st.button("⚠️ 重置帳戶 (清空所有資產)"):
                 save_user_state(st.session_state.user, 1000000.0, {})
                 st.session_state.bal = 1000000.0
                 st.session_state.port = {}
                 st.rerun()
