import streamlit as st
import yfinance as yf
import pandas as pd
import sqlite3
import json
import time

# --- 1. 網頁基礎設定 ---
st.set_page_config(page_title="台股飆股雷達-多用戶版", layout="wide")

# --- 2. 資料庫設定與函式 (多用戶版) ---
DB_FILE = "trading_app.db"

def init_db():
    """初始化資料庫，建立 users 表格 (如果不存在)。"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        # 修改：使用 username 作為唯一識別
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                balance REAL NOT NULL,
                portfolio TEXT NOT NULL
            )
        """)
        conn.commit()

def get_user_data(username):
    """取得特定用戶的資料，如果是新用戶則自動建立初始資金。"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance, portfolio FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        
        if row:
            # 舊用戶：回傳資料
            return row[0], json.loads(row[1])
        else:
            # 新用戶：建立初始資料 (100萬)
            initial_balance = 1000000.0
            initial_portfolio = {}
            cursor.execute("INSERT INTO users (username, balance, portfolio) VALUES (?, ?, ?)",
                           (username, initial_balance, json.dumps(initial_portfolio)))
            conn.commit()
            return initial_balance, initial_portfolio

def save_user_data(username):
    """儲存特定用戶的資料。"""
    if not username: return # 防止空用戶名寫入
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        portfolio_json = json.dumps(st.session_state.portfolio)
        cursor.execute("UPDATE users SET balance = ?, portfolio = ? WHERE username = ?",
                       (st.session_state.balance, portfolio_json, username))
        conn.commit()

# --- 初始化 ---
init_db()

# --- 3. 側邊欄：登入與帳戶切換 ---
VALID_KEYS = ["PREMIUM888", "STOCK2026", "FRANKVVIP"] 

with st.sidebar:
    st.header("🔐 用戶登入")
    
    # 1. 輸入帳號名稱 (這就是區分每個人的關鍵)
    input_user = st.text_input("請輸入您的代號/帳號", placeholder="例如: Tony001")
    # 2. 輸入授權碼 (付費驗證)
    user_key = st.text_input("請輸入授權碼", type="password")
    
    # 驗證邏輯
    is_key_valid = user_key in VALID_KEYS
    
    # 登入按鈕
    if st.button("登入 / 載入帳戶"):
        if not input_user:
            st.error("請輸入帳號名稱！")
        elif not is_key_valid:
            st.error("授權碼錯誤！")
        else:
            # 登入成功：載入該用戶資料
            st.session_state.current_user = input_user
            st.session_state.is_logged_in = True
            # 載入資料庫數據
            bal, port = get_user_data(input_user)
            st.session_state.balance = bal
            st.session_state.portfolio = port
            st.success(f"歡迎回來, {input_user}！")
            st.rerun()

    st.divider()

    # 顯示帳戶資訊 (只有登入後才顯示)
    if st.session_state.get('is_logged_in'):
        st.info(f"當前用戶: {st.session_state.current_user}")
        st.header("💰 帳戶餘額")
        st.metric("可用現金", f"${st.session_state.balance:,.0f}")
        
        if st.button("重置此帳戶"):
            st.session_state.balance = 1000000.0
            st.session_state.portfolio = {}
            save_user_data(st.session_state.current_user)
            st.rerun()
        
        if st.button("登出"):
            # 清除 Session 狀態
            keys_to_clear = ['balance', 'portfolio', 'current_user', 'is_logged_in', 'last_picks']
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

# --- 4. 主程式邏輯 (只有登入後才看得到) ---
st.title("🏹 台股全自動飆股雷達 (多用戶實戰版)")

if not st.session_state.get('is_logged_in'):
    st.warning("👈 請先在左側輸入「帳號」與「授權碼」進行登入。")
    st.info("提示：不同的帳號會擁有獨立的資金與持倉紀錄。")
else:
    # 為了方便，這裡定義當前用戶變數
    current_user = st.session_state.current_user
    
    # --- 策略與功能 (與之前相同，加上儲存邏輯) ---
    @st.cache_data
    def get_extended_stock_list():
        ranges = [range(1501, 1600), range(2301, 2499), range(2601, 2640), range(6101, 6299)]
        return [f"{i}.TW" for r in ranges for i in r]

    @st.cache_data(ttl=3600) 
    def scan_breakout_pro():
        # (這裡省略掃描邏輯，與上一版相同，為了版面整潔)
        # 實際使用請把上一版的 scan_breakout_pro 貼回來
        # 這裡用假資料模擬掃描結果，讓你能直接測試資料庫功能
        return [
            {"代碼": "2330", "產業": "半導體", "價格": 580.0, "成交量(張)": 50000, "策略建議": "🔥 爆量大突破", "建議停損點": 560, "建議停利點": 650},
            {"代碼": "2603", "產業": "航運", "價格": 120.5, "成交量(張)": 150000, "策略建議": "💎 極致糾結", "建議停損點": 115, "建議停利點": 140}
        ]

    @st.cache_data(ttl=60)
    def get_current_prices(tickers):
        data = yf.download(tickers, period="1d", progress=False)
        prices = {}
        if len(tickers) == 1:
             prices[tickers[0].replace(".TW", "")] = data['Close'].iloc[-1]
        else:
            for ticker in tickers:
                try:
                    prices[ticker.replace(".TW", "")] = data['Close'][ticker].iloc[-1]
                except:
                    prices[ticker.replace(".TW", "")] = None
        return prices

    # --- UI 顯示 ---
    tab1, tab2 = st.tabs(["🚀 今日精選標的", "💼 我的模擬持倉"])

    with tab1:
        if st.button("🔍 開始全自動掃描"):
            with st.spinner('分析中...'):
                # 實際使用請替換回真正的掃描函式
                st.session_state.last_picks = scan_breakout_pro() 
        
        if 'last_picks' in st.session_state:
            for stock in st.session_state.last_picks:
                with st.expander(f"📈 {stock['代碼']} ({stock['策略建議']})"):
                    st.metric("目前價格", stock['價格'])
                    
                    # 買入 UI
                    shares = st.number_input(f"張數 ({stock['代碼']})", 1, 100, key=f"b_{stock['代碼']}")
                    cost = shares * 1000 * stock['價格']
                    
                    if st.button(f"買入 {stock['代碼']}", key=f"btn_{stock['代碼']}"):
                        if st.session_state.balance >= cost:
                            st.session_state.balance -= cost
                            code = stock['代碼']
                            
                            # 平均成本邏輯
                            if code in st.session_state.portfolio:
                                old_s, old_c = st.session_state.portfolio[code]
                                new_s = old_s + shares
                                new_c = ((old_s * old_c) + (shares * stock['價格'])) / new_s
                                st.session_state.portfolio[code] = [new_s, new_c]
                            else:
                                st.session_state.portfolio[code] = [shares, stock['價格']]
                            
                            # *** 重要：買入後立刻存入該使用者的資料庫 ***
                            save_user_data(current_user)
                            st.success(f"已買入！剩餘資金: ${st.session_state.balance:,.0f}")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("資金不足")

    with tab2:
        if not st.session_state.portfolio:
            st.info("尚無持倉")
        else:
            # 顯示持倉 (這裡簡化顯示，重點在資料庫驗證)
            for code, (shares, cost) in st.session_state.portfolio.items():
                st.write(f"📌 **{code}**: {shares} 張 | 成本: {cost:.2f}")
            
            st.divider()
            
            # 賣出邏輯
            col1, col2 = st.columns(2)
            with col1:
                sell_code = st.selectbox("賣出股票", list(st.session_state.portfolio.keys()))
            
            if sell_code:
                max_s = st.session_state.portfolio[sell_code][0]
                sell_qty = st.number_input("賣出張數", 1, max_s, key="sell_qty")
                
                # 這裡為了演示，假設現價等於成本價 (實際請用 get_current_prices)
                curr_price = st.session_state.portfolio[sell_code][1] 
                earn = sell_qty * 1000 * curr_price

                if st.button("確認賣出"):
                    st.session_state.balance += earn
                    st.session_state.portfolio[sell_code][0] -= sell_qty
                    if st.session_state.portfolio[sell_code][0] == 0:
                        del st.session_state.portfolio[sell_code]
                    
                    # *** 重要：賣出後立刻存入該使用者的資料庫 ***
                    save_user_data(current_user)
                    st.success("賣出成功！資料已儲存")
                    time.sleep(1)
                    st.rerun()
