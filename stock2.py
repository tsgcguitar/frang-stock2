import streamlit as st
import yfinance as yf
import pandas as pd
import sqlite3
import json
import time

# --- 1. 網頁基礎設定 ---
st.set_page_config(page_title="台股飆股雷達-付費實戰版", layout="wide")

# --- 2. 資料庫設定與函式 ---
DB_FILE = "trading_account.db"

def init_db():
    """初始化資料庫，如果表格不存在則建立。"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        # 建立一個表格來儲存帳戶狀態 (只有一筆紀錄)
        # portfolio 欄位將以 JSON 字串形式儲存
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_state (
                id INTEGER PRIMARY KEY,
                balance REAL NOT NULL,
                portfolio TEXT NOT NULL
            )
        """)
        # 檢查是否有初始紀錄，沒有的話就插入一筆
        cursor.execute("SELECT COUNT(*) FROM account_state WHERE id = 1")
        if cursor.fetchone()[0] == 0:
            initial_portfolio = json.dumps({}) # 初始空持倉
            cursor.execute("INSERT INTO account_state (id, balance, portfolio) VALUES (?, ?, ?)",
                           (1, 1000000.0, initial_portfolio))
            conn.commit()

def load_account_data():
    """從資料庫載入帳戶餘額和持倉到 session_state。"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance, portfolio FROM account_state WHERE id = 1")
        balance, portfolio_json = cursor.fetchone()
        st.session_state.balance = balance
        st.session_state.portfolio = json.loads(portfolio_json)

def save_account_data():
    """將 session_state 中的帳戶狀態儲存回資料庫。"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        portfolio_json = json.dumps(st.session_state.portfolio)
        cursor.execute("UPDATE account_state SET balance = ?, portfolio = ? WHERE id = 1",
                       (st.session_state.balance, portfolio_json))
        conn.commit()

# --- 3. 帳戶與驗證系統 (Sidebar) ---

# 初始化資料庫
init_db()

# 如果 session_state 中沒有資料，就從資料庫載入
if 'balance' not in st.session_state:
    load_account_data()

# --- 🔑 付費驗證系統 ---
VALID_KEYS = ["PREMIUM888", "STOCK2026", "FRANKVVIP"]

with st.sidebar:
    st.header("🔐 會員登入")
    user_key = st.text_input("請輸入授權碼", type="password")
    is_authenticated = user_key in VALID_KEYS

    if is_authenticated:
        st.success("專業實戰版已解鎖")
    elif user_key != "":
        st.error("授權碼錯誤")

    st.divider()
    st.header("💰 模擬帳戶餘額")
    st.metric("可用現金", f"${st.session_state.balance:,.2f}") # 顯示到小數點後兩位

    if st.button("重置帳戶"):
        st.session_state.balance = 1000000.0
        st.session_state.portfolio = {}
        save_account_data() # 重置後也要存檔
        st.success("帳戶已重置！")
        time.sleep(1) # 暫停一下讓使用者看到訊息
        st.rerun()

# --- 4. 核心功能 ---
st.title("🏹 台股全自動飆股雷達 (模擬實戰版)")

if not is_authenticated:
    st.warning("⚠️ 請輸入授權碼解鎖專業功能。")
else:
    # --- 策略與掃描邏輯 ---
    @st.cache_data
    def get_extended_stock_list():
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

    @st.cache_data(ttl=3600) # 快取資料一小時
    def scan_breakout_pro():
        all_tickers = get_extended_stock_list()
        # 下載近期的數據以加快速度
        data = yf.download(all_tickers, period="60d", group_by='ticker', progress=False, threads=True)
        results = []

        for ticker in all_tickers:
            try:
                df = data[ticker].dropna()
                if len(df) < 20: continue
                close = df['Close']
                curr_price, curr_vol = close.iloc[-1], df['Volume'].iloc[-1]

                if curr_vol < 1000000: continue # 1000張門檻

                ma5 = close.rolling(5).mean().iloc[-1]
                ma10 = close.rolling(10).mean().iloc[-1]
                ma20 = close.rolling(20).mean().iloc[-1]
                ma_list = [ma5, ma10, ma20]
                squeeze_ratio = (max(ma_list) - min(ma_list)) / min(ma_list)
                vol_ratio = curr_vol / df['Volume'].rolling(5).mean().iloc[-1]
                bias_5ma = (curr_price - ma5) / ma5

                # 篩選邏輯
                if curr_price > max(ma_list) and squeeze_ratio < 0.03 and bias_5ma < 0.035:
                    if vol_ratio > 3.0:
                        strategy = "🔥 爆量大突破"
                    elif squeeze_ratio < 0.015:
                        strategy = "💎 極致糾結"
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
            except Exception as e:
                # st.write(f"處理 {ticker} 時發生錯誤: {e}") # Debug用
                continue
        return sorted(results, key=lambda x: x['成交量(張)'], reverse=True)[:5]

    @st.cache_data(ttl=60) # 每分鐘更新一次即時價格
    def get_current_prices(tickers):
        """獲取多支股票的即時價格"""
        prices = {}
        data = yf.download(tickers, period="1d", progress=False)
        if len(tickers) == 1:
             prices[tickers[0].replace(".TW", "")] = data['Close'].iloc[-1]
        else:
            for ticker in tickers:
                try:
                    prices[ticker.replace(".TW", "")] = data['Close'][ticker].iloc[-1]
                except:
                    prices[ticker.replace(".TW", "")] = None # 如果抓不到就設為 None
        return prices


    # --- UI 顯示 ---
    tab1, tab2 = st.tabs(["🚀 今日精選標的", "💼 我的模擬持倉"])

    with tab1:
        if st.button("🔍 開始全自動掃描 (每日限額 5 支)"):
            with st.spinner('雷達掃描中，請稍候...'):
                top_picks = scan_breakout_pro()
                st.session_state.last_picks = top_picks
        
        if 'last_picks' in st.session_state and st.session_state.last_picks:
            for stock in st.session_state.last_picks:
                with st.expander(f"📈 {stock['代碼']} {stock['產業']} ({stock['策略建議']})"):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("目前價格", f"{stock['價格']:.2f}")
                    col2.metric("建議停利", f"{stock['建議停利點']:.2f}", delta="約 15%")
                    col3.metric("建議停損", f"{stock['建議停損點']:.2f}", delta="約 -3%", delta_color="inverse")

                    # 下單 UI
                    shares_to_buy = st.number_input(
                        f"購買張數 ({stock['代碼']})",
                        min_value=1, max_value=100, step=1, key=f"buy_{stock['代碼']}"
                    )
                    total_cost = shares_to_buy * 1000 * stock['價格']
                    st.info(f"預估花費: ${total_cost:,.0f}")

                    if st.button(f"確認買入 {shares_to_buy} 張", key=f"btn_{stock['代碼']}"):
                        if st.session_state.balance >= total_cost:
                            st.session_state.balance -= total_cost
                            code = stock['代碼']
                            
                            # **優化：如果已持有，則計算平均成本**
                            if code in st.session_state.portfolio:
                                old_shares, old_cost = st.session_state.portfolio[code]
                                total_old_value = old_shares * 1000 * old_cost
                                
                                new_total_shares = old_shares + shares_to_buy
                                new_avg_cost = (total_old_value + total_cost) / (new_total_shares * 1000)
                                
                                st.session_state.portfolio[code] = [new_total_shares, new_avg_cost]
                            else:
                                st.session_state.portfolio[code] = [shares_to_buy, stock['價格']]
                            
                            save_account_data() # 儲存到資料庫
                            st.success(f"成功買入 {code}！花費 ${total_cost:,.0f}")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("現金餘額不足！")
        else:
            st.info("點擊按鈕開始掃描今日的潛力飆股！")


    with tab2:
        st.subheader("📊 目前持倉與即時損益")
        if not st.session_state.portfolio:
            st.info("目前尚無持倉，快去掃描標的並下單吧！")
        else:
            portfolio_items = st.session_state.portfolio.items()
            codes = [f"{code}.TW" for code in st.session_state.portfolio.keys()]
            
            with st.spinner("更新即時市價..."):
                current_prices = get_current_prices(codes)

            portfolio_data = []
            total_portfolio_value = 0.0

            for code, (shares, cost_price) in portfolio_items:
                current_price = current_prices.get(code)
                if current_price is None:
                    st.warning(f"無法獲取 {code} 的即時價格，暫以成本價計算。")
                    current_price = cost_price

                cost_total = shares * 1000 * cost_price
                current_total_value = shares * 1000 * current_price
                profit_loss = current_total_value - cost_total
                profit_loss_percent = (profit_loss / cost_total) * 100 if cost_total != 0 else 0
                total_portfolio_value += current_total_value

                portfolio_data.append({
                    "代碼": code,
                    "持有張數": shares,
                    "平均成本": f"{cost_price:.2f}",
                    "目前市價": f"{current_price:.2f}",
                    "持有總成本": f"${cost_total:,.0f}",
                    "目前總市值": f"${current_total_value:,.0f}",
                    "總損益": f"${profit_loss:,.0f}",
                    "報酬率(%)": f"{profit_loss_percent:.2f}%"
                })

            df = pd.DataFrame(portfolio_data)
            
            # 使用 Styler 為報酬率上色
            def color_profit(val):
                if isinstance(val, str) and '%' in val:
                    num_val = float(val.replace('%',''))
                    color = 'red' if num_val > 0 else 'green' if num_val < 0 else 'gray'
                    return f'color: {color}'
                return ''
            
            st.dataframe(df.style.applymap(color_profit, subset=['報酬率(%)']), use_container_width=True)
            
            st.metric("持倉總市值", f"${total_portfolio_value:,.0f}")
            
            st.divider()

            # --- 新增：賣出股票的 UI ---
            st.subheader("📉 個股賣出操作區")
            if len(codes) > 0:
                col1, col2, col3 = st.columns([1,1,1])
                with col1:
                    stock_to_sell = st.selectbox("選擇要賣出的股票", options=list(st.session_state.portfolio.keys()))
                
                if stock_to_sell:
                    max_shares = st.session_state.portfolio[stock_to_sell][0]
                    with col2:
                        shares_to_sell = st.number_input("賣出張數", min_value=1, max_value=max_shares, step=1)
                    
                    sell_price = current_prices.get(stock_to_sell, 0)
                    total_proceeds = shares_to_sell * 1000 * sell_price
                    
                    with col3:
                        st.text(f"預估可得: ${total_proceeds:,.0f}")
                        if st.button(f"確認賣出 {shares_to_sell} 張 {stock_to_sell}", type="primary"):
                            st.session_state.balance += total_proceeds
                            
                            # 更新持倉
                            st.session_state.portfolio[stock_to_sell][0] -= shares_to_sell
                            # 如果張數為 0，從持倉中移除
                            if st.session_state.portfolio[stock_to_sell][0] == 0:
                                del st.session_state.portfolio[stock_to_sell]
                            
                            save_account_data() # 儲存到資料庫
                            st.success(f"成功賣出 {stock_to_sell} {shares_to_sell} 張！")
                            time.sleep(1)
                            st.rerun()

# --- 5. 側邊欄腳註 ---
st.sidebar.info("💡 模擬下單僅供交易邏輯驗證，非真實投資建議。")
