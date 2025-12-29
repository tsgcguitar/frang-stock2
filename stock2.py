import streamlit as st
import yfinance as yf
import pandas as pd
import sqlite3
import json
import time

# --- 1. 網頁配置 ---
st.set_page_config(page_title="台股飆股雷達-帳戶實戰版", layout="wide")

# --- 2. 資料庫核心邏輯 (確保永久儲存) ---
DB_FILE = "user_accounts_v1.db"

def init_db():
    """初始化資料庫，建立用戶表"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                balance REAL,
                portfolio TEXT,
                last_login TEXT
            )
        """)
        conn.commit()

def load_or_create_user(username):
    """登入時加載數據，若無此帳號則建立新帳號"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance, portfolio FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        
        if row:
            # 現有帳戶：讀取最後儲存的金額與庫存
            return row[0], json.loads(row[1])
        else:
            # 新開戶：給予初始 100 萬
            init_bal = 1000000.0
            init_port = {}
            cursor.execute("INSERT INTO users (username, balance, portfolio) VALUES (?, ?, ?)",
                           (username, init_bal, json.dumps(init_port)))
            conn.commit()
            return init_bal, init_port

def sync_to_db():
    """將目前的 Session 狀態即時寫入資料庫"""
    if 'current_user' in st.session_state and st.session_state.is_logged_in:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = ?, portfolio = ? WHERE username = ?",
                           (st.session_state.balance, 
                            json.dumps(st.session_state.portfolio), 
                            st.session_state.current_user))
            conn.commit()

@st.cache_data(ttl=3600)
def get_stock_name(ticker):
    try:
        return yf.Ticker(ticker).info.get('shortName', ticker)
    except:
        return ticker

# --- 3. 核心策略掃描 (全台股批量) ---
def run_scanner():
    """掃描邏輯：均線糾結 + 帶量突破 + 剛起漲"""
    # 範例代碼清單 (實際可擴展至所有代碼)
    tickers = [f"{i}.TW" for i in range(2301, 2390)] + [f"{i}.TW" for i in range(2601, 2620)] + ["2330.TW", "2454.TW"]
    
    results = []
    found = 0
    # 批量下載數據
    data = yf.download(tickers, period="40d", group_by='ticker', progress=False)
    
    for ticker in tickers:
        try:
            df = data[ticker].dropna()
            if len(df) < 20: continue
            
            # 指標計算
            ma5 = df['Close'].rolling(5).mean().iloc[-1]
            ma10 = df['Close'].rolling(10).mean().iloc[-1]
            ma20 = df['Close'].rolling(20).mean().iloc[-1]
            close = df['Close'].iloc[-1]
            vol = df['Volume'].iloc[-1] / 1000
            
            # 邏輯判斷
            ma_list = [ma5, ma10, ma20]
            gap = (max(ma_list) - min(ma_list)) / min(ma_list)
            
            # 條件：量>1000, 糾結<3%, 站上均線, 離5MA<3.5%
            if vol > 1000 and gap < 0.03 and close > max(ma_list) and (close - ma5)/ma5 < 0.035:
                results.append({
                    "代碼": ticker.split('.')[0],
                    "名稱": get_stock_name(ticker),
                    "現價": round(close, 2),
                    "成交量": int(vol),
                    "停損價": round(min(ma_list), 2),
                    "停利價": round(close * 1.1, 2)
                })
                found += 1
            if found >= 5: break
        except:
            continue
    return results

# --- 4. 介面呈現 ---
init_db()

with st.sidebar:
    st.title("🔐 會員中心")
    if 'is_logged_in' not in st.session_state:
        st.session_state.is_logged_in = False

    if not st.session_state.is_logged_in:
        user_id = st.text_input("輸入您的個人 ID")
        pwd = st.text_input("輸入授權碼", type="password")
        if st.button("登入 / 開戶"):
            if pwd in ["PREMIUM888", "FRANKVVIP"]:
                bal, port = load_or_create_user(user_id)
                st.session_state.current_user = user_id
                st.session_state.balance = bal
                st.session_state.portfolio = port
                st.session_state.is_logged_in = True
                st.rerun()
            else:
                st.error("授權碼無效")
    else:
        st.success(f"使用者：{st.session_state.current_user}")
        st.metric("當前可用資金", f"${st.session_state.balance:,.0f}")
        if st.button("登出系統"):
            st.session_state.clear()
            st.rerun()

# 主功能區
if st.session_state.is_logged_in:
    tab1, tab2 = st.tabs(["🚀 飆股雷達掃描", "💼 我的永續庫存"])
    
    with tab1:
        if st.button("🔍 開始全台股掃描 (遵照突破糾結策略)"):
            with st.spinner("雷達掃描中..."):
                st.session_state.scan_results = run_scanner()
        
        if 'scan_results' in st.session_state:
            for stock in st.session_state.scan_results:
                with st.expander(f"📈 {stock['代碼']} {stock['名稱']} - 現價 {stock['現價']}"):
                    c1, c2 = st.columns(2)
                    c1.write(f"成交量：{stock['成交量']} 張")
                    c1.write(f"建議停損：{stock['停損價']}")
                    
                    qty = c2.number_input("購買張數", 1, 50, key=f"buy_{stock['代碼']}")
                    cost = qty * 1000 * stock['現價']
                    
                    if c2.button(f"確認買入 {stock['名稱']}", key=f"btn_{stock['代碼']}"):
                        if st.session_state.balance >= cost:
                            # 扣款
                            st.session_state.balance -= cost
                            # 更新庫存
                            code = stock['代碼']
                            old_qty, old_cost = st.session_state.portfolio.get(code, [0, 0])
                            new_qty = old_qty + qty
                            new_avg_cost = ((old_qty * old_cost) + cost) / new_qty
                            st.session_state.portfolio[code] = [new_qty, new_avg_cost]
                            
                            # --- 重點：立刻同步到資料庫 ---
                            sync_to_db()
                            st.success(f"已成功買入，扣除 ${cost:,.0f}。資料已永久儲存至您的帳號！")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("金額不足")

    with tab2:
        st.subheader(f"📊 {st.session_state.current_user} 的個人帳戶資產")
        if not st.session_state.portfolio:
            st.info("目前無持股。")
        else:
            # 顯示庫存表
            df_port = []
            for code, (q, c) in st.session_state.portfolio.items():
                df_port.append({"代碼": code, "張數": q, "平均成本": round(c, 2)})
            st.table(df_port)
            
            if st.button("⚠️ 清空重置帳戶 (慎用)"):
                st.session_state.balance = 1000000.0
                st.session_state.portfolio = {}
                sync_to_db()
                st.rerun()
else:
    st.title("🏹 台股全自動飆股雷達")
    st.info("請於左側登入您的專屬 ID 以開啟掃描功能與模擬帳戶。")
