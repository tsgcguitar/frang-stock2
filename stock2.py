import streamlit as st
import yfinance as yf
import pandas as pd
import sqlite3
import json
import time

# --- 1. 系統設定與資料庫 ---
st.set_page_config(page_title="台股飆股雷達-專業版", layout="wide")
DB_FILE = "trading_radar_v9.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                balance REAL,
                portfolio TEXT
            )
        """)

def load_user(username):
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute("SELECT balance, portfolio FROM users WHERE username = ?", (username,)).fetchone()
        if row: return row[0], json.loads(row[1])
        return 1000000.0, {}

def save_user(username, bal, port):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?)", (username, bal, json.dumps(port)))

# --- 2. 核心掃描引擎 (強化版邏輯) ---
def get_stock_strategy(df, close, vol, ma_list):
    ma5, ma10, ma20 = ma_list
    ma_max, ma_min = max(ma_list), min(ma_list)
    gap = (ma_max - ma_min) / ma_min
    vol_ma5 = df['Volume'].rolling(5).mean().iloc[-1]
    
    # 策略 1: 均線糾結突破 (最強推)
    if gap <= 0.03 and close > ma_max:
        return "均線糾結突破 (主力收籌結束)"
    # 策略 2: 價量齊揚
    if close > ma5 and vol > (vol_ma5 / 1000 * 1.5):
        return "價量齊揚 (動能噴發)"
    # 策略 3: 底部回升
    if close > ma20 and df['Close'].iloc[-5] < ma20:
        return "多頭回歸 (底部轉折)"
    return "趨勢觀察"

@st.cache_data(ttl=3600)
def get_all_tickers():
    # 模擬 1700 檔清單 (實際環境可導入 csv)
    return [f"{i}.TW" for i in range(1101, 2500)] + [f"{i}.TWO" for i in range(3000, 8000)]

def run_radar():
    results = []
    found = 0
    all_codes = get_all_tickers()
    
    status = st.empty()
    bar = st.progress(0)
    
    # 每次掃描分片處理，避免超時
    step = 50 
    for i in range(0, 1000, step): # 範例掃描前 1000 檔
        batch = all_codes[i:i+step]
        status.text(f"雷達搜尋中... 已掃描 {i} 檔")
        bar.progress(i/1000)
        
        try:
            data = yf.download(batch, period="40d", group_by='ticker', progress=False, threads=True)
            for t in batch:
                if found >= 5: break
                df = data[t].dropna()
                if len(df) < 22: continue # 排除新股
                
                close = float(df['Close'].iloc[-1])
                vol = float(df['Volume'].iloc[-1]) / 1000 # 張
                ma5 = df['Close'].rolling(5).mean().iloc[-1]
                ma10 = df['Close'].rolling(10).mean().iloc[-1]
                ma20 = df['Close'].rolling(20).mean().iloc[-1]
                ma_list = [ma5, ma10, ma20]
                
                # 嚴格篩選條件
                if vol < 1000: continue # 排除冷門
                if (close - ma5) / ma5 > 0.035: continue # 排除追高
                if close < max(ma_list): continue # 必須站上均線
                
                strategy = get_stock_strategy(df, close, vol, ma_list)
                if strategy == "趨勢觀察": continue

                results.append({
                    "代碼": t.split('.')[0],
                    "價格": round(close, 2),
                    "成交量": int(vol),
                    "策略": strategy,
                    "停損": round(min(ma_list) * 0.98, 2),
                    "停利": round(close * 1.15, 2),
                    "網址": f"https://www.wantgoo.com/stock/{t.split('.')[0]}"
                })
                found += 1
        except: continue
        if found >= 5: break
    bar.empty()
    status.empty()
    return results

# --- 3. UI 介面 ---
init_db()
if 'is_login' not in st.session_state: st.session_state.is_login = False

# 側邊欄
with st.sidebar:
    if st.session_state.is_login:
        st.success(f"👤 用戶: {st.session_state.user}")
        st.metric("💰 模擬倉餘額", f"${st.session_state.bal:,.0f}")
        if st.button("登出"): 
            st.session_state.clear()
            st.rerun()
    st.divider()
    st.info("訂閱問題 官方line: 811162")

# 主頁面
if not st.session_state.is_login:
    st.title("🏹 台股全自動飆股雷達")
    st.markdown("### 領先市場，買在起漲點")
    
    with st.expander("📢 工具使用說明與小提醒", expanded=True):
        st.write("這是一款專為不喜歡追高的投資者設計的雷達。")
        st.write("* **停損建議**：跌破均線群底端應執行紀律。")
        st.write("* **量能門檻**：已過濾成交量 < 1000 張的股票。")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🌙 月租專業版")
        st.markdown("## NT$ 199")
        if st.button("點我訂閱 (月)", use_container_width=True):
            st.warning("【匯款資訊】永豐(807) 帳號: 148-018-00054187\n請傳轉帳截圖與後5碼至 LINE: 811162")
    with col2:
        st.subheader("☀️ 年租尊榮版 (省2個月!)")
        st.markdown("## NT$ 1,990")
        if st.button("點我訂閱 (年)", use_container_width=True, type="primary"):
            st.error("【匯款資訊】永豐(807) 帳號: 148-018-00054187\n請傳轉帳截圖與後5碼至 LINE: 811162")

    st.divider()
    acc = st.text_input("輸入帳號")
    pwd = st.text_input("授權碼", type="password")
    if st.button("登入系統", use_container_width=True):
        if pwd in ["PREMIUM888", "STOCK2026"]:
            bal, port = load_user(acc)
            st.session_state.update({"is_login":True, "user":acc, "bal":bal, "port":port})
            st.rerun()

else:
    t1, t2 = st.tabs(["🚀 起漲點掃描", "💼 個人模擬倉"])
    
    with t1:
        if st.button("🔍 開始掃描全台股突破標的", type="primary"):
            st.session_state.scan = run_radar()
            
        if 'scan' in st.session_state:
            for s in st.session_state.scan:
                with st.expander(f"📈 {s['代碼']} | {s['策略']} | 現價: {s['價格']}"):
                    c1, c2 = st.columns(2)
                    c1.write(f"成交量: {s['成交量']} 張")
                    c1.write(f"停損: :red[{s['停損']}] | 停利: :green[{s['停利']}]")
                    c1.markdown(f"[🔗 查看即時線圖]({s['網址']})")
                    
                    buy_n = c2.number_input("張數", 1, 100, key=f"n_{s['代碼']}")
                    cost = buy_n * 1000 * s['價格']
                    c2.markdown(f"#### 金額: :blue[NT$ {cost:,.0f}]")
                    if c2.button(f"買入 {s['代碼']}", key=f"b_{s['代碼']}"):
                        if st.session_state.bal >= cost:
                            st.session_state.bal -= cost
                            code = s['代碼']
                            q, c = st.session_state.port.get(code, [0, 0])
                            new_q = q + buy_n
                            new_cost = ((q * c) + cost) / new_q
                            st.session_state.port[code] = [new_q, new_cost]
                            save_user(st.session_state.user, st.session_state.bal, st.session_state.port)
                            st.success("購入成功！")
                            st.rerun()

    with t2:
        st.subheader("📊 持股明細與獲利分析")
        if not st.session_state.port:
            st.info("目前無持股")
        else:
            for code, (q, avg_c) in list(st.session_state.port.items()):
                # 抓取最新價算損益
                try:
                    curr_p = yf.Ticker(f"{code}.TW").fast_info['last_price']
                except:
                    curr_p = avg_c
                
                profit = (curr_p - avg_c) * q * 1000
                p_ratio = (curr_p - avg_c) / avg_c * 100
                color = "red" if profit >= 0 else "green" # 台股習慣

                with st.container(border=True):
                    cols = st.columns([1, 1, 1, 1, 1])
                    cols[0].write(f"**{code}**")
                    cols[1].write(f"{q} 張")
                    cols[2].write(f"成本: {avg_c:.2f}")
                    cols[3].write(f"損益: :{color}[{profit:,.0f} ({p_ratio:.2f}%)]")
                    if cols[4].button("賣出", key=f"sell_{code}"):
                        st.session_state.bal += (curr_p * q * 1000)
                        del st.session_state.port[code]
                        save_user(st.session_state.user, st.session_state.bal, st.session_state.port)
                        st.toast(f"{code} 已全數賣出")
                        st.rerun()
            
            if st.button("⚠️ 重置帳戶"):
                save_user(st.session_state.user, 1000000.0, {})
                st.rerun()

