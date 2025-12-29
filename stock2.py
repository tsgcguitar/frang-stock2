import streamlit as st
import yfinance as yf
import pandas as pd
import sqlite3
import json
import time

# --- 1. 網頁基礎設定 ---
st.set_page_config(page_title="台股飆股雷達-多用戶實戰版", layout="wide")

# --- 2. 資料庫設定與函式 (多用戶版) ---
DB_FILE = "trading_app_v2.db"

def init_db():
    """初始化資料庫，建立 users 表格 (如果不存在)。"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        # 使用 username 作為唯一識別
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
    if not username: return 
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        portfolio_json = json.dumps(st.session_state.portfolio)
        cursor.execute("UPDATE users SET balance = ?, portfolio = ? WHERE username = ?",
                       (st.session_state.balance, portfolio_json, username))
        conn.commit()

# --- 初始化資料庫 ---
init_db()

# --- 3. 側邊欄：登入與帳戶管理 ---
VALID_KEYS = ["PREMIUM888", "STOCK2026", "FRANKVVIP"] 

with st.sidebar:
    st.header("🔐 用戶登入系統")
    
    # 登入介面
    if not st.session_state.get('is_logged_in'):
        input_user = st.text_input("設定您的帳號 (ID)", placeholder="例如: Kevin888")
        user_key = st.text_input("輸入授權碼", type="password")
        
        if st.button("登入 / 註冊"):
            if not input_user:
                st.error("請輸入帳號名稱")
            elif user_key not in VALID_KEYS:
                st.error("授權碼錯誤")
            else:
                # 登入成功
                st.session_state.current_user = input_user
                st.session_state.is_logged_in = True
                # 載入該用戶數據
                bal, port = get_user_data(input_user)
                st.session_state.balance = bal
                st.session_state.portfolio = port
                st.success(f"歡迎, {input_user}")
                st.rerun()
    
    # 登入後顯示資訊
    else:
        st.info(f"👤 當前用戶: {st.session_state.current_user}")
        st.divider()
        st.header("💰 帳戶餘額")
        st.metric("可用現金", f"${st.session_state.balance:,.0f}")
        
        if st.button("重置此帳戶"):
            st.session_state.balance = 1000000.0
            st.session_state.portfolio = {}
            save_user_data(st.session_state.current_user)
            st.success("資金已重置回 100 萬")
            time.sleep(1)
            st.rerun()
            
        if st.button("登出"):
            for key in ['balance', 'portfolio', 'current_user', 'is_logged_in', 'last_picks']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    st.divider()
    st.info("💡 模擬下單僅供交易邏輯驗證，非真實投資建議。")


# --- 4. 主程式邏輯 ---
st.title("🏹 台股全自動飆股雷達 (多用戶實戰版)")

if not st.session_state.get('is_logged_in'):
    st.warning("👈 請先在左側登入以啟用您的專屬交易帳戶。")
else:
    # 取得當前用戶變數，方便後續存檔使用
    current_user = st.session_state.current_user

    # --- 策略與掃描邏輯 (保留原本的演算法) ---
    @st.cache_data
    def get_extended_stock_list():
        # 鎖定熱門區段，避免掃描全台股太慢
        ranges = [range(1501, 1600), range(2301, 2499), range(2601, 2640), range(6101, 6299)]
        return [f"{i}.TW" for r in ranges for i in r]

    def get_industry_v2(ticker):
        try:
            code = int(ticker.split(".")[0])
            if code == 2330: return "半導體-晶圓代工"
            if 2301 <= code <= 2499: return "電子/半導體"
            if 1501 <= code <= 1599: return "電機/機電"
            return "其他/傳產"
        except: return "未知"

    @st.cache_data(ttl=3600) 
    def scan_breakout_pro():
        """
        核心演算法：
        1. 下載大量股票數據
        2. 篩選成交量 > 1000 張
        3. 計算均線糾結度 (Squeeze Ratio)
        4. 判斷價格是否突破且乖離率低
        """
        all_tickers = get_extended_stock_list()
        # 下載近期的數據
        data = yf.download(all_tickers, period="60d", group_by='ticker', progress=False, threads=True)
        results = []

        for ticker in all_tickers:
            try:
                df = data[ticker].dropna()
                if len(df) < 20: continue
                close = df['Close']
                curr_price, curr_vol = close.iloc[-1], df['Volume'].iloc[-1]

                # 條件1: 成交量 > 1000張 (1,000,000股)
                if curr_vol < 1000000: continue 

                ma5 = close.rolling(5).mean().iloc[-1]
                ma10 = close.rolling(10).mean().iloc[-1]
                ma20 = close.rolling(20).mean().iloc[-1]
                ma_list = [ma5, ma10, ma20]
                
                # 計算均線糾結度
                squeeze_ratio = (max(ma_list) - min(ma_list)) / min(ma_list)
                vol_ratio = curr_vol / df['Volume'].rolling(5).mean().iloc[-1]
                bias_5ma = (curr_price - ma5) / ma5

                # 條件2: 突破均線 + 均線糾結 < 3% + 乖離率 < 3.5%
                if curr_price > max(ma_list) and squeeze_ratio < 0.03 and bias_5ma < 0.035:
                    if vol_ratio > 3.0:
                        strategy = "🔥 爆量大突破"
                    elif squeeze_ratio < 0.015:
                        strategy = "💎 極致糾結噴發"
                    elif curr_price > ma20 and close.iloc[-2] <= ma20:
                        strategy = "🔄 底部翻揚"
                    else:
                        strategy = "✅ 穩定起漲"

                    results.append({
                        "代碼": ticker.replace(".TW", ""),
                        "產業": get_industry_v2(ticker),
                        "價格": round(curr_price, 2),
                        "成交量(張)": int(curr_vol / 1000),
                        "策略建議": strategy,
                        "建議停損點": round(min(ma_list) * 0.97, 2),
                        "建議停利點": round(curr_price * 1.15, 2),
                    })
            except: continue
        return sorted(results, key=lambda x: x['成交量(張)'], reverse=True)[:5] # 只取前5名

    @st.cache_data(ttl=60)
    def get_current_prices(tickers):
        """獲取即時價格"""
        prices = {}
        if not tickers: return prices
        data = yf.download(tickers, period="1d", progress=False)
        if len(tickers) == 1:
             prices[tickers[0].replace(".TW", "")] = data['Close'].iloc[-1]
        else:
            for ticker in tickers:
                try:
                    prices[ticker.replace(".TW", "")] = data['Close'][ticker].iloc[-1]
                except:
                    prices[ticker.replace(".TW", "")] = None
        return prices

    # --- UI 顯示區 ---
    tab1, tab2 = st.tabs(["🚀 今日飆股掃描", "💼 我的庫存損益"])

    with tab1:
        st.subheader("📊 全自動演算法選股")
        if st.button("🔍 啟動雷達 (掃描電機、電子、航運)"):
            with st.spinner('AI 分析線型與籌碼中...'):
                top_picks = scan_breakout_pro()
                st.session_state.last_picks = top_picks
        
        if 'last_picks' in st.session_state and st.session_state.last_picks:
            for stock in st.session_state.last_picks:
                with st.expander(f"📈 {stock['代碼']} - {stock['產業']} ({stock['策略建議']})"):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("目前價格", f"{stock['價格']:.2f}")
                    col2.metric("成交量", f"{stock['成交量(張)']} 張")
                    col3.metric("建議停損", f"{stock['建議停損點']:.2f}", delta_color="inverse")

                    # 買入介面
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        shares_to_buy = st.number_input(f"張數 ({stock['代碼']})", 1, 100, key=f"buy_{stock['代碼']}")
                    with c2:
                        total_cost = shares_to_buy * 1000 * stock['價格']
                        if st.button(f"買進", key=f"btn_{stock['代碼']}"):
                            if st.session_state.balance >= total_cost:
                                st.session_state.balance -= total_cost
                                code = stock['代碼']
                                
                                # 平均成本法
                                if code in st.session_state.portfolio:
                                    old_s, old_c = st.session_state.portfolio[code]
                                    new_s = old_s + shares_to_buy
                                    new_c = ((old_s * old_c * 1000) + total_cost) / (new_s * 1000)
                                    st.session_state.portfolio[code] = [new_s, new_c]
                                else:
                                    st.session_state.portfolio[code] = [shares_to_buy, stock['價格']]
                                
                                # 存入資料庫
                                save_user_data(current_user)
                                st.success(f"買入成功！扣除 ${total_cost:,.0f}")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("餘額不足")
        else:
            st.info("請點擊上方按鈕開始掃描。")

    with tab2:
        st.subheader("💎 庫存管理與即時損益")
        if not st.session_state.portfolio:
            st.info("目前沒有持股，請去掃描飆股！")
        else:
            # 準備資料
            codes_tw = [f"{c}.TW" for c in st.session_state.portfolio.keys()]
            with st.spinner("更新最新股價..."):
                current_prices = get_current_prices(codes_tw)
            
            portfolio_list = []
            total_value = 0
            
            for code, (shares, cost) in st.session_state.portfolio.items():
                curr_p = current_prices.get(code, cost) # 抓不到就用成本價
                mkt_val = shares * 1000 * curr_p
                cost_val = shares * 1000 * cost
                profit = mkt_val - cost_val
                ret = (profit / cost_val) * 100
                total_value += mkt_val
                
                portfolio_list.append({
                    "代碼": code,
                    "張數": shares,
                    "成本": f"{cost:.2f}",
                    "現價": f"{curr_p:.2f}",
                    "損益($)": f"{profit:,.0f}",
                    "報酬率(%)": f"{ret:.2f}%"
                })
            
            # 顯示表格
            df = pd.DataFrame(portfolio_list)
            def color_ret(val):
                color = 'red' if '-' not in val and val != '0.00%' else 'green'
                return f'color: {color}'
            st.dataframe(df.style.applymap(color_ret, subset=['報酬率(%)']), use_container_width=True)
            st.metric("庫存總市值", f"${total_value:,.0f}")

            st.divider()
            
            # --- 賣出功能區 ---
            st.subheader("📉 賣出股票")
            c1, c2, c3 = st.columns([1,1,1])
            with c1:
                sell_code = st.selectbox("選擇股票", list(st.session_state.portfolio.keys()))
            
            if sell_code:
                max_qty = st.session_state.portfolio[sell_code][0]
                with c2:
                    sell_qty = st.number_input("賣出張數", 1, max_qty)
                
                sell_p = current_prices.get(sell_code, 0)
                estimate_get = sell_qty * 1000 * sell_p
                
                with c3:
                    st.write(f"預估拿回: ${estimate_get:,.0f}")
                    if st.button("確認賣出", type="primary"):
                        st.session_state.balance += estimate_get
                        st.session_state.portfolio[sell_code][0] -= sell_qty
                        if st.session_state.portfolio[sell_code][0] == 0:
                            del st.session_state.portfolio[sell_code]
                        
                        # 存檔
                        save_user_data(current_user)
                        st.success("賣出成功！")
                        time.sleep(1)
                        st.rerun()
