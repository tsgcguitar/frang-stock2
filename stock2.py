import streamlit as st
import yfinance as yf
import pandas as pd
import sqlite3
import json
import time

# --- 1. 網頁基礎設定 ---
st.set_page_config(page_title="台股飆股雷達-付費實戰版", layout="wide")

# --- 2. 資料庫設定 (多用戶支援) ---
DB_FILE = "stock_radar_v3.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                balance REAL NOT NULL,
                portfolio TEXT NOT NULL
            )
        """)
        conn.commit()

def get_user_data(username):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance, portfolio FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row:
            return row[0], json.loads(row[1])
        else:
            init_bal, init_port = 1000000.0, {}
            cursor.execute("INSERT INTO users (username, balance, portfolio) VALUES (?, ?, ?)",
                           (username, init_bal, json.dumps(init_port)))
            conn.commit()
            return init_bal, init_port

def save_user_data(username):
    if not username: return
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        port_json = json.dumps(st.session_state.portfolio)
        cursor.execute("UPDATE users SET balance = ?, portfolio = ? WHERE username = ?",
                       (st.session_state.balance, port_json, username))
        conn.commit()

init_db()

# --- 3. 側邊欄：登入與說明 ---
VALID_KEYS = ["PREMIUM888", "STOCK2026", "FRANKVVIP"]

with st.sidebar:
    st.header("🔐 用戶登入")
    if not st.session_state.get('is_logged_in'):
        input_user = st.text_input("帳號 (ID)", placeholder="例如: Kevin888")
        user_key = st.text_input("授權碼", type="password")
        if st.button("登入 / 註冊"):
            if user_key in VALID_KEYS and input_user:
                st.session_state.current_user = input_user
                st.session_state.is_logged_in = True
                bal, port = get_user_data(input_user)
                st.session_state.balance = bal
                st.session_state.portfolio = port
                st.success("登入成功")
                st.rerun()
            else:
                st.error("帳號或授權碼錯誤")
    else:
        st.info(f"👤 {st.session_state.current_user}")
        st.metric("💰 可用現金", f"${st.session_state.balance:,.0f}")
        if st.button("重置帳戶"):
            st.session_state.balance = 1000000.0
            st.session_state.portfolio = {}
            save_user_data(st.session_state.current_user)
            st.rerun()
        if st.button("登出"):
            st.session_state.clear()
            st.rerun()

    st.divider()
    st.markdown("""
    ### 關於此工具
    這是一款專為不喜歡追高的投資者又想要買在起漲點設計的雷達。
    
    **📢 操作小提醒：**
    1. **停損建議**：若收盤價跌破『建議停損點』(通常為均線群底端)，應果斷執行紀律。
    2. **量能門檻**：系統已過濾單日成交量小於 1000 張的冷門股。
    3. **產業連動**：若發現同一產業有多檔同時上榜，該族群為當日強勢主流。
    
    **訂閱問題 官方line: 811162**
    """)

# --- 4. 核心邏輯 ---
st.title("🏹 台股全自動飆股雷達 (模擬實戰版)")

if not st.session_state.get('is_logged_in'):
    st.warning("👈 請先從左側登入以使用完整功能。")
else:
    current_user = st.session_state.current_user

    @st.cache_data
    def get_all_tw_stock_list():
        # 擴大掃描範圍：包含主要類股代號 (11xx - 99xx)
        # 注意：為了效能，這裡列出常見範圍，全掃描需要較長時間
        stock_list = []
        # 水泥/食品/塑膠/紡織/機電/電纜/玻璃/造紙/鋼鐵/橡膠/汽車/營建/航運/觀光/金融/百貨/其他
        ranges = [
            range(1101, 1110), range(1201, 1236), range(1301, 1342), range(1402, 1477),
            range(1503, 1605), range(1701, 1795), range(2002, 2069), range(2101, 2115),
            range(2201, 2250), range(2301, 2499), range(2501, 2548), range(2601, 2646),
            range(2701, 2756), range(2801, 2892), range(2903, 2915), range(3002, 3715),
            range(4102, 4999), range(5201, 5907), range(6101, 6799), range(8001, 8499),
            range(9902, 9962)
        ]
        for r in ranges:
            stock_list.extend([f"{i}.TW" for i in r])
        return stock_list

    def get_industry_guess(ticker):
        try:
            code = int(ticker.split(".")[0])
            if 2300 <= code < 2500: return "電子/半導體"
            if 2600 <= code < 2700: return "航運/運輸"
            if 1500 <= code < 1600: return "電機/機電"
            if 1700 <= code < 1800: return "化工/生技"
            if 2800 <= code < 2900: return "金融"
            return "其他/傳產"
        except: return "一般"

    @st.cache_data(ttl=1800) # 30分鐘更新一次快取
    def scan_strategy():
        tickers = get_all_tw_stock_list()
        # 下載數據，忽略錯誤
        data = yf.download(tickers, period="60d", group_by='ticker', progress=False, threads=True)
        results = []

        for ticker in tickers:
            try:
                # 處理單一股票數據
                if ticker in data.columns.levels[0]: # 確保有抓到資料
                    df = data[ticker].dropna()
                else:
                    continue
                
                # 1. 排除資料不足 20 天的新股
                if len(df) < 20: continue
                
                close = df['Close']
                if len(close) == 0: continue
                
                curr_price = float(close.iloc[-1])
                curr_vol = float(df['Volume'].iloc[-1])

                # 2. 篩選成交量 > 1000 張
                if curr_vol < 1000000: continue

                # 計算均線
                ma5 = close.rolling(5).mean().iloc[-1]
                ma10 = close.rolling(10).mean().iloc[-1]
                ma20 = close.rolling(20).mean().iloc[-1]
                ma_list = [ma5, ma10, ma20]
                
                # 3. 均線糾結邏輯 (高低落差 < 3%)
                max_ma = max(ma_list)
                min_ma = min(ma_list)
                squeeze_ratio = (max_ma - min_ma) / min_ma
                
                # 4. 突破邏輯 (收盤價 > 所有均線)
                breakout = curr_price > max_ma
                
                # 5. 乖離率控制 (距離5日線 < 3.5%)
                bias_5ma = abs(curr_price - ma5) / ma5

                if breakout and squeeze_ratio < 0.03 and bias_5ma < 0.035:
                    strategy_name = "💎 極致糾結噴發"
                    # 可以根據其他條件微調名稱
                    if curr_vol > df['Volume'].rolling(5).mean().iloc[-1] * 2:
                        strategy_name = "🔥 爆量起漲"

                    stock_code = ticker.replace(".TW", "")
                    link = f"https://tw.stock.yahoo.com/quote/{stock_code}.TW"
                    
                    results.append({
                        "代碼": stock_code,
                        "產業": get_industry_guess(ticker),
                        "目前價格": round(curr_price, 2),
                        "成交量": int(curr_vol / 1000),
                        "策略建議": strategy_name,
                        "建議停損點": round(min_ma * 0.97, 2), # 均線底端再往下抓一點緩衝
                        "建議停利點": round(curr_price * 1.15, 2),
                        "連結": link
                    })
            except Exception as e:
                continue
                
        # 6. 只吐前 5 檔 (按成交量排序)
        return sorted(results, key=lambda x: x['成交量'], reverse=True)[:5]

    @st.cache_data(ttl=30)
    def get_live_prices(code_list):
        prices = {}
        if not code_list: return prices
        try:
            # 加上 .TW 後綴
            yf_codes = [f"{c}.TW" for c in code_list]
            data = yf.download(yf_codes, period="1d", progress=False)
            
            # 處理只有一支股票的情況
            if len(code_list) == 1:
                # 確保回傳 float
                val = data['Close'].iloc[-1]
                prices[code_list[0]] = float(val) if not pd.isna(val) else None
            else:
                for c in code_list:
                    try:
                        val = data['Close'][f"{c}.TW"].iloc[-1]
                        prices[c] = float(val) if not pd.isna(val) else None
                    except:
                        prices[c] = None
        except:
            pass # 發生錯誤回傳空字典
        return prices

    # --- UI 頁面 ---
    tab1, tab2 = st.tabs(["🚀 飆股掃描", "💼 我的庫存"])

    with tab1:
        st.subheader("📊 今日潛力飆股 (Top 5)")
        if st.button("🔍 啟動全台股掃描"):
            with st.spinner('掃描全台股上市櫃資料中 (需時約 10-20 秒)...'):
                picks = scan_strategy()
                st.session_state.last_picks = picks
        
        if 'last_picks' in st.session_state and st.session_state.last_picks:
            # 轉換成 DataFrame 顯示更漂亮
            df_show = pd.DataFrame(st.session_state.last_picks)
            
            # 使用 expander 顯示詳細下單介面
            for index, row in df_show.iterrows():
                with st.expander(f"📈 {row['代碼']} {row['產業']} - {row['策略建議']}"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("價格", row['目前價格'])
                    c2.metric("成交量", f"{row['成交量']} 張")
                    c3.metric("停損", row['建議停損點'], delta_color="inverse")
                    c4.markdown(f"[查看線圖]({row['連結']})")
                    
                    # 買入區
                    b1, b2 = st.columns([1, 1])
                    shares = b1.number_input(f"張數", 1, 100, key=f"n_{row['代碼']}")
                    cost = shares * 1000 * row['目前價格']
                    
                    if b2.button(f"買進 {row['代碼']}", key=f"b_{row['代碼']}"):
                        if st.session_state.balance >= cost:
                            st.session_state.balance -= cost
                            code = row['代碼']
                            if code in st.session_state.portfolio:
                                old_s, old_c = st.session_state.portfolio[code]
                                new_s = old_s + shares
                                new_c = ((old_s * old_c) + (shares * row['目前價格'])) / new_s
                                st.session_state.portfolio[code] = [new_s, new_c]
                            else:
                                st.session_state.portfolio[code] = [shares, row['目前價格']]
                            save_user_data(current_user)
                            st.success(f"已買入 {code}！")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("餘額不足")

        else:
            st.info("點擊按鈕開始掃描。")

    with tab2:
        st.subheader("💎 庫存損益表")
        if not st.session_state.portfolio:
            st.info("暫無持倉")
        else:
            codes = list(st.session_state.portfolio.keys())
            current_price_map = get_live_prices(codes)
            
            table_data = []
            
            for code, (shares, avg_cost) in st.session_state.portfolio.items():
                # 這裡就是修正 TypeError 的關鍵：檢查是否為 None
                curr_p = current_price_map.get(code)
                if curr_p is None:
                    curr_p = avg_cost # 如果抓不到，暫時用成本價代替
                
                mkt_val = shares * 1000 * curr_p
                cost_val = shares * 1000 * avg_cost
                profit = mkt_val - cost_val
                roi = (profit / cost_val) * 100
                
                link = f"https://tw.stock.yahoo.com/quote/{code}.TW"

                table_data.append({
                    "代碼": code,
                    "持倉": shares,
                    "成本": f"{avg_cost:.2f}",
                    "現價": f"{curr_p:.2f}", # 這裡安全了
                    "市值": f"{int(mkt_val):,}",
                    "損益": f"{int(profit):,}",
                    "報酬率": f"{roi:.2f}%",
                    "線圖": link
                })

            df_port = pd.DataFrame(table_data)
            
            # 使用 column_config 讓連結變成可點擊的按鈕或連結
            st.dataframe(
                df_port,
                column_config={
                    "線圖": st.column_config.LinkColumn("技術分析", display_text="前往看圖")
                },
                use_container_width=True
            )
            
            st.divider()
            
            # 賣出區
            sc1, sc2, sc3 = st.columns(3)
            sell_target = sc1.selectbox("賣出標的", codes)
            if sell_target:
                max_s = st.session_state.portfolio[sell_target][0]
                sell_num = sc2.number_input("賣出張數", 1, max_s)
                
                # 取得該股現價計算預估獲利
                s_price = current_price_map.get(sell_target, st.session_state.portfolio[sell_target][1])
                est_return = sell_num * 1000 * s_price
                
                sc3.write(f"預估回流資金: ${int(est_return):,}")
                if sc3.button("確認賣出"):
                    st.session_state.balance += est_return
                    st.session_state.portfolio[sell_target][0] -= sell_num
                    if st.session_state.portfolio[sell_target][0] == 0:
                        del st.session_state.portfolio[sell_target]
                    save_user_data(current_user)
                    st.success("賣出成功！")
                    time.sleep(0.5)
                    st.rerun()
