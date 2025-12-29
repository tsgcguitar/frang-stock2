import streamlit as st
import yfinance as yf
import pandas as pd
import sqlite3
import json
import random
import time

# --- 1. 系統設定與資料庫 ---
st.set_page_config(page_title="台股全量飆股雷達", layout="wide")
DB_FILE = "trading_radar_v10.db"

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

# --- 2. 核心全量掃描引擎 ---
@st.cache_data(ttl=3600)
def get_all_tickers():
    """模擬全台股 1700 檔清單"""
    tw = [f"{i}.TW" for i in range(1101, 9999)]
    two = [f"{i}.TWO" for i in range(1101, 9999)]
    return tw + two

def run_full_scan():
    all_codes = get_all_tickers()
    qualified_list = []
    
    status = st.empty()
    bar = st.progress(0)
    
    # 實際運作時，為了 API 穩定性，我們分批抓取
    batch_size = 100
    for i in range(0, len(all_codes), batch_size):
        batch = all_codes[i : i + batch_size]
        status.text(f"正在掃描全台股標的... 已掃描 {i}/{len(all_codes)} 檔")
        bar.progress(i / len(all_codes))
        
        try:
            # 抓取最近 40 天 K 線
            data = yf.download(batch, period="40d", group_by='ticker', progress=False, threads=True)
            
            for t in batch:
                df = data[t].dropna()
                if len(df) < 20: continue # 排除新股
                
                # 計算均線
                ma5 = df['Close'].rolling(5).mean().iloc[-1]
                ma10 = df['Close'].rolling(10).mean().iloc[-1]
                ma20 = df['Close'].rolling(20).mean().iloc[-1]
                close = float(df['Close'].iloc[-1])
                vol = float(df['Volume'].iloc[-1]) / 1000 # 成交張數
                
                # 均線糾結判斷 (3%以內)
                ma_list = [ma5, ma10, ma20]
                gap = (max(ma_list) - min(ma_list)) / min(ma_list)
                
                # --- 嚴格篩選邏輯 ---
                # 1. 成交量 > 1000張
                # 2. 均線落差 < 3%
                # 3. 股價突破所有均線
                # 4. 離 5MA 不超過 3.5% (起漲點)
                if vol >= 1000 and gap <= 0.03 and close >= max(ma_list):
                    if (close - ma5) / ma5 <= 0.035:
                        qualified_list.append({
                            "代碼": t.split('.')[0],
                            "現價": round(close, 2),
                            "成交量": int(vol),
                            "建議停損": round(min(ma_list) * 0.98, 2),
                            "建議停利": round(close * 1.15, 2),
                            "策略建議": "均線糾結突破 (噴發前兆)",
                            "連結": f"https://www.wantgoo.com/stock/{t.split('.')[0]}"
                        })
        except: continue
        
        # 如果已經掃到足夠樣本，可適時停止或繼續。為了「全量」我們會跑完，但若使用者急迫可調整。
    
    status.empty()
    bar.empty()
    
    # 隨機輸出 5 個會漲的標的
    if len(qualified_list) > 5:
        return random.sample(qualified_list, 5)
    return qualified_list

# --- 3. UI 介面 ---
init_db()
if 'login' not in st.session_state: st.session_state.login = False

# 側邊欄：登入與說明
with st.sidebar:
    if st.session_state.login:
        st.success(f"👤 當前用戶: {st.session_state.user}")
        st.metric("💰 餘額", f"NT$ {st.session_state.bal:,.0f}")
        if st.button("登出"): st.session_state.clear(); st.rerun()
    st.divider()
    st.info("訂閱問題 官方LINE: 811162")

# 主頁
if not st.session_state.login:
    st.title("🏹 台股全自動飆股雷達")
    
    # 訂閱計畫
    c1, c2 = st.columns(2)
    with c1:
        st.info("### 🌙 月租專業版\n**NT$ 199**")
        if st.button("查看付款資訊 (月租)", use_container_width=True):
            st.warning("銀行：永豐銀行 (807)\n帳號：148-018-00054187\n請截圖轉帳畫面以及後5碼傳至 LINE: 811162")
    with c2:
        st.success("### ☀️ 年租尊榮版\n**NT$ 1,990**")
        if st.button("查看付款資訊 (年租)", use_container_width=True):
            st.warning("銀行：永豐銀行 (807)\n帳號：148-018-00054187\n請截圖轉帳畫面以及後5碼傳至 LINE: 811162")
            
    st.divider()
    user_id = st.text_input("輸入帳號")
    user_pw = st.text_input("輸入授權碼", type="password")
    if st.button("登入雷達", use_container_width=True):
        if user_pw in ["STOCK2026"]:
            bal, port = load_user(user_id)
            st.session_state.update({"login":True, "user":user_id, "bal":bal, "port":port})
            st.rerun()
else:
    tab1, tab2 = st.tabs(["🚀 起漲點掃描", "💼 個人模擬倉"])
    
    with tab1:
        if st.button("🔍 全量掃描全台股突破標的", type="primary"):
            with st.spinner("雷達正在過濾 1700+ 檔標的，大約需要 30-60 秒..."):
                st.session_state.scan_res = run_full_scan()
        
        if 'scan_res' in st.session_state:
            for s in st.session_state.scan_res:
                with st.expander(f"📈 {s['代碼']} | 現價: {s['現價']} | 條件: 符合均線糾結"):
                    col1, col2 = st.columns(2)
                    col1.write(f"成交量: {s['成交量']} 張")
                    col1.write(f"停損: :red[{s['建議停損']}] | 停利: :green[{s['建議停利']}]")
                    col1.markdown(f"[🔗 查看即時線圖]({s['連結']})")
                    
                    buy_num = col2.number_input("購買張數", 1, 100, key=f"buy_{s['代碼']}")
                    total_price = buy_num * 1000 * s['現價']
                    col2.markdown(f"#### 預估金額: :blue[NT$ {total_price:,.0f}]")
                    
                    if col2.button(f"確認買入 {s['代碼']}", key=f"btn_{s['代碼']}"):
                        if st.session_state.bal >= total_price:
                            st.session_state.bal -= total_price
                            # 更新庫存
                            old_q, old_c = st.session_state.port.get(s['代碼'], [0, 0])
                            new_q = old_q + buy_num
                            new_c = ((old_q * old_c) + total_price) / new_q
                            st.session_state.port[s['代碼']] = [new_q, new_c]
                            save_user(st.session_state.user, st.session_state.bal, st.session_state.port)
                            st.success(f"{s['代碼']} 已加入模擬倉！")
                            time.sleep(1); st.rerun()

    with tab2:
        st.subheader("📊 持股明細與獲利分析")
        if not st.session_state.port:
            st.info("目前無持股。")
        else:
            # 為了讓損益精準，顯示時會嘗試抓取最新價
            for code, (q, avg_cost) in list(st.session_state.port.items()):
                try:
                    # 快速抓取目前價格以計算真實損益
                    current_price = yf.Ticker(f"{code}.TW").fast_info['last_price']
                except:
                    current_price = avg_cost / 1000 # 避免出錯
                
                # 計算損益：(現價 - 成本/1000) * 張數 * 1000
                # 注意：儲存的 avg_cost 是總金額/張數，所以 avg_cost/1000 才是單股成本
                single_cost = avg_cost / 1000
                total_profit = (current_price - single_cost) * q * 1000
                profit_percent = (current_price - single_cost) / single_cost * 100
                
                color = "red" if total_profit >= 0 else "green"
                
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([1, 2, 2, 1])
                    c1.write(f"**{code}**")
                    c2.write(f"持股: {q} 張")
                    c3.write(f"損益: :{color}[{total_profit:,.0f} ({profit_percent:.2f}%)]")
                    if c4.button("賣出", key=f"sell_{code}"):
                        st.session_state.bal += (current_price * q * 1000)
                        del st.session_state.port[code]
                        save_user(st.session_state.user, st.session_state.bal, st.session_state.port)
                        st.toast(f"{code} 已按市價結算賣出")
                        time.sleep(1); st.rerun()
            
            if st.button("⚠️ 重置帳戶"):
                save_user(st.session_state.user, 1000000.0, {})
                st.rerun()
