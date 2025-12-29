import streamlit as st
import yfinance as yf
import pandas as pd
import sqlite3
import json
import time

# --- 1. 網頁基礎設定 ---
st.set_page_config(page_title="台股飆股雷達-官方商業版", layout="wide")

# --- 2. 資料庫設定 (新增訂閱狀態欄位) ---
DB_FILE = "stock_radar_v4.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                balance REAL NOT NULL,
                portfolio TEXT NOT NULL,
                is_premium INTEGER DEFAULT 0
            )
        """)
        conn.commit()

def get_user_data(username):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance, portfolio, is_premium FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row:
            return row[0], json.loads(row[1]), row[2]
        else:
            init_bal, init_port, premium = 1000000.0, {}, 0
            cursor.execute("INSERT INTO users (username, balance, portfolio, is_premium) VALUES (?, ?, ?, ?)",
                           (username, init_bal, json.dumps(init_port), premium))
            conn.commit()
            return init_bal, init_port, premium

def save_user_data(username):
    if not username: return
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        port_json = json.dumps(st.session_state.portfolio)
        cursor.execute("UPDATE users SET balance = ?, portfolio = ? WHERE username = ?",
                       (st.session_state.balance, port_json, username))
        conn.commit()

init_db()

# --- 3. 核心功能函數 ---

@st.cache_data(ttl=86400)
def get_stock_name(ticker_code):
    """取得股票名稱 (快取 24 小時以維持效能)"""
    try:
        t = yf.Ticker(ticker_code)
        # 優先取 shortName，若無則回傳代碼本身
        return t.info.get('shortName', ticker_code.split('.')[0])
    except:
        return ticker_code.split('.')[0]

# --- 4. 側邊欄 ---
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
                bal, port, premium = get_user_data(input_user)
                st.session_state.balance = bal
                st.session_state.portfolio = port
                st.session_state.is_premium = premium
                st.success("登入成功")
                st.rerun()
            else:
                st.error("帳號或授權碼錯誤")
    else:
        st.success(f"👤 {st.session_state.current_user} " + ("(VIP)" if st.session_state.get('is_premium') else "(免費版)"))
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
    st.markdown("### 📞 客服中心\n**官方 LINE: 811162**")

# --- 5. 主程式頁面 ---
st.title("🏹 台股全自動飆股雷達 (模擬實戰版)")

if not st.session_state.get('is_logged_in'):
    st.warning("👈 請先從左側登入以使用完整功能。")
else:
    current_user = st.session_state.current_user

    @st.cache_data
    def get_all_tw_stock_list():
        ranges = [range(1101, 1110), range(2301, 2499), range(2601, 2646), range(2801, 2892), range(3002, 3715), range(6101, 6799)]
        stock_list = []
        for r in ranges:
            stock_list.extend([f"{i}.TW" for i in r])
        return stock_list

    @st.cache_data(ttl=1800)
    def scan_strategy():
        tickers = get_all_tw_stock_list()
        data = yf.download(tickers, period="60d", group_by='ticker', progress=False, threads=True)
        results = []

        for ticker in tickers:
            try:
                if ticker in data.columns.levels[0]:
                    df = data[ticker].dropna()
                else: continue
                
                if len(df) < 20: continue
                close = df['Close']
                curr_price = float(close.iloc[-1])
                curr_vol = float(df['Volume'].iloc[-1])

                if curr_vol < 1000000: continue

                ma5 = close.rolling(5).mean().iloc[-1]
                ma10 = close.rolling(10).mean().iloc[-1]
                ma20 = close.rolling(20).mean().iloc[-1]
                ma_list = [ma5, ma10, ma20]
                max_ma, min_ma = max(ma_list), min(ma_list)
                
                if curr_price > max_ma and (max_ma - min_ma) / min_ma < 0.03:
                    name = get_stock_name(ticker) # 這裡取得名稱
                    results.append({
                        "代碼": ticker.replace(".TW", ""),
                        "名稱": name,
                        "目前價格": round(curr_price, 2),
                        "成交量": int(curr_vol / 1000),
                        "策略建議": "🔥 爆量起漲" if curr_vol > df['Volume'].rolling(5).mean().iloc[-1] * 2 else "💎 極致糾結",
                        "建議停損點": round(min_ma * 0.97, 2),
                        "連結": f"https://tw.stock.yahoo.com/quote/{ticker}"
                    })
            except: continue
        return sorted(results, key=lambda x: x['成交量'], reverse=True)[:5]

    # --- UI Tabs ---
    tab1, tab2, tab3 = st.tabs(["🚀 飆股掃描", "💼 我的庫存", "💎 訂閱服務"])

    with tab1:
        st.subheader("📊 今日潛力飆股")
        if st.button("🔍 啟動全台股掃描"):
            with st.spinner('正在分析市場數據...'):
                st.session_state.last_picks = scan_strategy()
        
        if 'last_picks' in st.session_state:
            for row in st.session_state.last_picks:
                with st.expander(f"📈 {row['代碼']} {row['名稱']} - {row['策略建議']}"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("價格", row['目前價格'])
                    c2.metric("成交量", f"{row['成交量']} 張")
                    c3.metric("停損", row['建議停損點'])
                    c4.markdown(f"[查看線圖]({row['連結']})")
                    
                    # 買入區優化
                    st.divider()
                    b1, b2 = st.columns([2, 1])
                    shares = b1.number_input(f"購買張數", 1, 100, key=f"n_{row['代碼']}")
                    total_cost = shares * 1000 * row['目前價格']
                    
                    # 強調顯示下單金額
                    b1.info(f"💰 預估下單金額：**${total_cost:,.0f}** 元")
                    
                    if b2.button(f"確認買進 {row['名稱']}", key=f"b_{row['代碼']}", use_container_width=True):
                        if st.session_state.balance >= total_cost:
                            st.session_state.balance -= total_cost
                            code = row['代碼']
                            if code in st.session_state.portfolio:
                                old_s, old_c = st.session_state.portfolio[code]
                                new_s = old_s + shares
                                new_c = ((old_s * old_c) + (shares * row['目前價格'])) / new_s
                                st.session_state.portfolio[code] = [new_s, new_c]
                            else:
                                st.session_state.portfolio[code] = [shares, row['目前價格']]
                            save_user_data(current_user)
                            st.success(f"成功買入 {row['名稱']} {shares} 張！")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("您的現金餘額不足！")

    with tab2:
        st.subheader("💎 庫存損益表")
        if not st.session_state.portfolio:
            st.info("目前尚無持倉數據。")
        else:
            # 這裡簡單列出持倉
            st.write(st.session_state.portfolio)
            # ... (此處可保留您原本的損益表格計算代碼)

    with tab3:
        st.subheader("💎 訂閱 Premium 專業版")
        col_m, col_y = st.columns(2)
        
        with col_m:
            st.info("### 月租計畫")
            st.title("NT$ 199 /月")
            st.write("✓ 每日不限次數掃描\n✓ 存取所有策略清單\n✓ VIP 專屬 Line 群組")
            if st.button("點我訂閱月計畫"):
                st.session_state.show_payment = True
        
        with col_y:
            st.success("### 年租優惠 (省 2 個月!)")
            st.title("NT$ 1,990 /年")
            st.write("✓ 包含所有月租功能\n✓ 優先獲取新策略開發\n✓ 一對一操作諮詢")
            if st.button("點我訂閱年計畫"):
                st.session_state.show_payment = True

        if st.session_state.get('show_payment'):
            st.warning("#### 💳 匯款資訊 (手動審核)")
            st.markdown("""
            請匯款至以下帳號，匯款後請截圖傳至 **官方 Line (811162)**，我們將於 10 分鐘內為您開通權限。
            
            - **銀行代碼**：807 (永豐銀行)
            - **帳號**：148-018-0005418-7
            - **戶名**：(請確認您的開戶名稱)
            
            *提醒：匯款請註明您的帳號 ID，以利快速比對。*
            """)
            if st.button("關閉匯款資訊"):
                st.session_state.show_payment = False
                st.rerun()
