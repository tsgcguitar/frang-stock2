import streamlit as st
import yfinance as yf
import pandas as pd
import sqlite3
import json
import time

# --- 1. 網頁基礎設定 ---
st.set_page_config(page_title="台股飆股雷達-官方實戰版", layout="wide")

# --- 2. 資料庫與基礎功能 ---
DB_FILE = "stock_radar_v5.db"

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

@st.cache_data(ttl=86400)
def get_stock_name(ticker_code):
    """取得股票正確名稱"""
    try:
        t = yf.Ticker(ticker_code)
        # yfinance 抓取台灣股票名稱有時會是英文，這裏做簡單處理
        name = t.info.get('shortName', ticker_code.split('.')[0])
        return name
    except:
        return ticker_code.split('.')[0]

init_db()

# --- 3. 側邊欄登入邏輯 ---
VALID_KEYS = ["PREMIUM888", "STOCK2026", "FRANKVVIP"]

with st.sidebar:
    st.header("🔐 會員登入")
    if not st.session_state.get('is_logged_in'):
        input_user = st.text_input("帳號 (ID)", placeholder="請輸入您的 ID")
        user_key = st.text_input("授權碼 / 密碼", type="password")
        if st.button("登入系統", use_container_width=True):
            if user_key in VALID_KEYS and input_user:
                st.session_state.current_user = input_user
                st.session_state.is_logged_in = True
                bal, port, premium = get_user_data(input_user)
                st.session_state.balance = bal
                st.session_state.portfolio = port
                st.session_state.is_premium = premium
                st.success("登入成功！")
                st.rerun()
            else:
                st.error("帳號或授權碼錯誤")
    else:
        st.success(f"👤 {st.session_state.current_user} " + ("(VIP)" if st.session_state.is_premium else ""))
        st.metric("💰 模擬倉餘額", f"${st.session_state.balance:,.0f}")
        if st.button("安全登出", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    
    st.divider()
    st.info("💡 忘記授權碼或匯款開通請聯繫客服")

# --- 4. 主畫面邏輯 ---

# 情況 A: 使用者尚未登入 (顯示介紹與訂閱方案)
if not st.session_state.get('is_logged_in'):
    st.title("🏹 台股全自動飆股雷達")
    st.subheader("領先市場，買在起漲點。專為紀律投資者設計的掃描工具。")
    
    # 產品特色介紹
    c1, c2, c3 = st.columns(3)
    c1.markdown("### 🔍 全自動掃描\n每日自動分析全台股上市櫃公司，篩選均線糾結與爆量突破標的。")
    c2.markdown("### 📊 模擬實戰\n內建模擬倉位管理，免下載 App 即可測試您的交易策略與損益。")
    c3.markdown("### ⚠️ 紀律停損點\n系統自動計算支撐位，給予最精準的建議停損與停利區間。")
    
    st.divider()
    
    # 訂閱方案區
    st.markdown("<h2 style='text-align: center;'>💎 選擇您的專業計畫</h2>", unsafe_allow_html=True)
    sub1, sub2 = st.columns(2)
    
    with sub1:
        st.info("### 🌙 月租專業版")
        st.title("NT$ 199 / 月")
        st.write("● 無限制標的掃描\n● 每日強勢產業分析\n● 模擬倉完整功能\n● 官方 LINE 訊號提醒")
        if st.button("立即申請月租 (查看匯款資訊)", key="sub_m", use_container_width=True):
            st.session_state.pay_info = True
            
    with sub2:
        st.success("### ☀️ 年租尊榮版 (現省 $398)")
        st.title("NT$ 1,990 / 年")
        st.write("● 包含所有月租功能\n● **優先** 獲取新策略開發\n● 一對一策略診斷\n● 終身會員專屬群組")
        if st.button("立即申請年租 (查看匯款資訊)", key="sub_y", use_container_width=True):
            st.session_state.pay_info = True

    if st.session_state.get('pay_info'):
        st.warning("### 💳 訂閱匯款帳戶資訊")
        col_pay1, col_pay2 = st.columns([1, 1])
        with col_pay1:
            st.markdown("""
            **請匯款至以下帳號：**
            - **銀行代碼**：807 (永豐銀行)
            - **帳號**：148-018-0005418-7
            - **匯款金額**：199 或 1,990 元
            """)
        with col_pay2:
            st.markdown(f"""
            **開通流程：**
            1. 匯款後請截圖或告知末五碼。
            2. 傳送至 **官方 Line: 811162**。
            3. 提供您的 **ID (帳號)**。
            4. 客服將在 30 分鐘內為您開通權限。
            """)
        if st.button("我已了解，關閉視窗"):
            st.session_state.pay_info = False
            st.rerun()

# 情況 B: 使用者已登入 (顯示操作介面)
else:
    # 這裡放原本的核心功能 (scan_strategy, tab1, tab2 等)
    # 為了節省空間，這裡展示優化過的下單金額與名稱顯示部分
    
    @st.cache_data(ttl=1800)
    def scan_strategy():
        # (這裡維持您原本的邏輯，但增加取得名稱)
        # 範例結構：
        results = []
        # ... 掃描邏輯 ...
        # results.append({"代碼": code, "名稱": get_stock_name(ticker), ...})
        return results

    tab1, tab2 = st.tabs(["🚀 飆股掃描", "💼 我的庫存"])

    with tab1:
        st.subheader("📊 今日潛力標的")
        if st.button("🔍 執行全台股策略掃描"):
            # 呼叫掃描函數 (此處省略部分重複代碼)
            pass 

        # 假設已經有 picks 資料
        if 'last_picks' in st.session_state:
            for row in st.session_state.last_picks:
                with st.expander(f"📈 {row['代碼']} {row['名稱']} - {row['策略建議']}"):
                    # 顯示資訊...
                    # 下單區優化
                    st.divider()
                    b1, b2 = st.columns([2, 1])
                    num_shares = b1.number_input("購買張數", 1, 100, key=f"buy_{row['代碼']}")
                    total_amt = num_shares * 1000 * row['目前價格']
                    b1.info(f"💰 預估下單金額：**NT$ {total_amt:,.0f}**")
                    
                    if b2.button(f"確認買進 {row['名稱']}", key=f"btn_{row['代碼']}", use_container_width=True):
                        # ... 買入邏輯 ...
                        st.success(f"已買入 {row['名稱']} {num_shares} 張")

    with tab2:
        st.subheader("💎 我的模擬倉位")
        if not st.session_state.portfolio:
            st.info("目前庫存空空如也，快去掃描標的吧！")
        else:
            # 損益表邏輯，增加名稱顯示
            port_list = []
            for code, (shares, cost) in st.session_state.portfolio.items():
                name = get_stock_name(f"{code}.TW")
                # ... 計算損益 ...
                port_list.append({"股票": f"{code} {name}", "張數": shares, "成本": cost})
            st.table(port_list)
