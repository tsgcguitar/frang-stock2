import streamlit as st
import yfinance as yf
import pandas as pd
import sqlite3
import json
import time

# --- 1. 系統設定與資料庫初始化 ---
st.set_page_config(page_title="台股起漲點雷達-官方版", layout="wide")
DB_FILE = "trading_radar_v8.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                balance REAL,
                portfolio TEXT
            )
        """)
        conn.commit()

def load_user_data(username):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance, portfolio FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row:
            return row[0], json.loads(row[1])
        else:
            # 初始 100 萬起始金
            init_bal, init_port = 1000000.0, {}
            cursor.execute("INSERT INTO users (username, balance, portfolio) VALUES (?, ?, ?)",
                           (username, init_bal, json.dumps(init_port)))
            conn.commit()
            return init_bal, init_port

def save_user_data():
    if st.session_state.get('is_logged_in'):
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = ?, portfolio = ? WHERE username = ?",
                           (st.session_state.balance, 
                            json.dumps(st.session_state.portfolio), 
                            st.session_state.current_user))
            conn.commit()

# --- 2. 核心掃描策略 ---
@st.cache_data(ttl=3600)
def get_all_taiwan_tickers():
    """模擬全台股清單 (可擴充)"""
    tickers = [f"{i}.TW" for i in range(1101, 9999)] + [f"{i}.TWO" for i in range(1101, 9999)]
    # 這裡先過濾掉一些明顯無效的，實際執行時 yfinance 會處理
    return tickers[:500] # 範例取前500檔測試

def run_radar_scan(ticker_list):
    results = []
    found = 0
    # 批量抓取 K 線資料
    data = yf.download(ticker_list, period="40d", group_by='ticker', progress=False)
    
    for ticker in ticker_list:
        if found >= 5: break
        try:
            df = data[ticker].dropna()
            if len(df) < 20: continue # 需求 2: 排除資料不足 20 天的新股
            
            # 計算均線
            ma5 = df['Close'].rolling(5).mean().iloc[-1]
            ma10 = df['Close'].rolling(10).mean().iloc[-1]
            ma20 = df['Close'].rolling(20).mean().iloc[-1]
            close = float(df['Close'].iloc[-1])
            vol = float(df['Volume'].iloc[-1]) / 1000 # 成交張數
            
            ma_list = [ma5, ma10, ma20]
            ma_max, ma_min = max(ma_list), min(ma_list)
            gap = (ma_max - ma_min) / ma_min
            
            # --- 篩選條件邏輯 ---
            # 1. 成交量門檻 > 1000 張
            if vol < 1000: continue
            # 2. 均線糾結: 高低落差在 3% 以內
            if gap > 0.03: continue
            # 3. 股價站上所有均線 (突破)
            if close < ma_max: continue
            # 4. 確保買在起漲: 離 5MA 不超過 3.5% (不追高)
            if (close - ma5) / ma5 > 0.035: continue
            
            # 符合條件則抓取產業與產出結果
            info = yf.Ticker(ticker).info
            results.append({
                "代碼": ticker.split('.')[0],
                "產業": info.get('industry', '未知'),
                "目前價格": round(close, 2),
                "成交量": int(vol),
                "策略建議": "均線糾結突破 (剛起漲)",
                "建議停損點": round(ma_min * 0.98, 2), # 均線群底端再往下 2%
                "建議停利點": round(close * 1.15, 2), # 預設 15% 停利
                "連結": f"https://www.wantgoo.com/stock/{ticker.split('.')[0]}"
            })
            found += 1
        except:
            continue
    return results

# --- 3. UI 介面 ---
init_db()

with st.sidebar:
    st.header("🔐 會員登入")
    if not st.session_state.get('is_logged_in'):
        input_user = st.text_input("帳號 (ID)")
        user_key = st.text_input("授權碼 / 密碼", type="password")
        if st.button("登入雷達系統", use_container_width=True):
            if user_key in ["PREMIUM888", "STOCK2026", "FRANKVVIP"] and input_user:
                bal, port = load_user_data(input_user)
                st.session_state.current_user = input_user
                st.session_state.balance = bal
                st.session_state.portfolio = port
                st.session_state.is_logged_in = True
                st.rerun()
            else:
                st.error("授權碼錯誤，請聯繫客服")
    else:
        st.success(f"👤 當前用戶: {st.session_state.current_user}")
        st.metric("💰 模擬倉餘額", f"NT$ {st.session_state.balance:,.0f}")
        if st.button("登出帳號"):
            st.session_state.clear()
            st.rerun()
    st.divider()
    st.info("訂閱問題 官方line: 811162")

if not st.session_state.get('is_logged_in'):
    # --- 登入前的頁面 (訂閱與資訊) ---
    st.title("🏹 台股全自動飆股雷達")
    st.subheader("領先市場，買在起漲點。")
    
    st.markdown("""
    ### 關於此工具
    這是一款專為不喜歡追高的投資者又想要買在起漲點設計的雷達。
    
    📢 **操作小提醒：**
    * **停損建議**：若收盤價跌破『建議停損點』(通常為均線群底端)，應果斷執行紀律。
    * **量能門檻**：系統已過濾單日成交量小於 1000 張的冷門股，降低被操控風險。
    * **產業連動**：若發現同一產業有多檔同時上榜，該族群為當日強勢主流。
    """)
    
    st.divider()
    st.subheader("💎 選擇您的訂閱計畫")
    sub1, sub2 = st.columns(2)
    with sub1:
        st.info("### 🌙 月租專業版\n**NT$ 199 / 月**")
        if st.button("點我查看付款資訊 (月租)", use_container_width=True):
            st.warning("【匯款資訊】\n銀行：永豐銀行 (807)\n帳號：148-018-00054187\n金額：199 元")
            
    with sub2:
        st.success("### ☀️ 年租尊榮版\n**NT$ 1,990 / 年**")
        if st.button("點我查看付款資訊 (年租)", use_container_width=True):
            st.warning("【匯款資訊】\n銀行：永豐銀行 (807)\n帳號：148-018-00054187\n金額：1,990 元")
            
else:
    # --- 登入後的頁面 (掃描與交易) ---
    tab1, tab2 = st.tabs(["🚀 起漲點掃描", "💼 個人模擬倉"])
    
    with tab1:
        if st.button("🔍 開始掃描全台股突破標的", type="primary"):
            with st.spinner("雷達掃描中，僅顯示前 5 檔符合條件標的..."):
                all_codes = get_all_taiwan_tickers()
                st.session_state.scan_results = run_radar_scan(all_codes)
        
        if 'scan_results' in st.session_state:
            for s in st.session_state.scan_results:
                with st.expander(f"📈 代碼: {s['代碼']} | 產業: {s['產業']} | 現價: {s['目前價格']}"):
                    c1, c2 = st.columns(2)
                    c1.write(f"成交量: {s['成交量']} 張")
                    c1.write(f"建議停損: :red[{s['建議停損點']}] | 停利: :green[{s['建議停利點']}]")
                    c1.markdown(f"[🔗 查看即時線圖]({s['連結']})")
                    
                    # 下單區
                    st.divider()
                    num = c2.number_input("購買張數", 1, 100, key=f"buy_{s['代碼']}")
                    cost = num * 1000 * s['目前價格']
                    # 需求 4: 顯示金額
                    c2.markdown(f"### 💵 預估總金額: :blue[NT$ {cost:,.0f}]")
                    
                    if c2.button(f"確認買入 {s['代碼']}", key=f"btn_{s['代碼']}", use_container_width=True):
                        if st.session_state.balance >= cost:
                            st.session_state.balance -= cost
                            # 持久化庫存
                            code = s['代碼']
                            old_q, old_c = st.session_state.portfolio.get(code, [0, 0])
                            new_q = old_q + num
                            new_c = ((old_q * old_c) + cost) / new_q
                            st.session_state.portfolio[code] = [new_q, new_c]
                            save_user_data()
                            st.success(f"✅ {code} 已購入，資料已儲存！")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("餘額不足！")

    with tab2:
        st.subheader("📊 我的個人帳戶資產")
        if not st.session_state.portfolio:
            st.info("目前無持股，趕快去執行掃描吧！")
        else:
            p_list = []
            for code, (q, c) in st.session_state.portfolio.items():
                p_list.append({"代碼": code, "持股張數": q, "平均成本": round(c, 2)})
            st.table(p_list)
            
            if st.button("⚠️ 重置帳戶資產 (100萬)"):
                st.session_state.balance = 1000000.0
                st.session_state.portfolio = {}
                save_user_data()
                st.rerun()
