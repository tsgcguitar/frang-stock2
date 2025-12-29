import streamlit as st
import yfinance as yf
import pandas as pd
import sqlite3
import json
import random
import time
import twstock  # 需安裝 pip install twstock

# --- 1. 系統設定與資料庫 ---
st.set_page_config(page_title="台股全量飆股雷達 (極速版)", layout="wide", page_icon="⚡")
DB_FILE = "trading_radar_opt.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT,
                balance REAL,
                portfolio TEXT
            )
        """)

def get_user(username, password):
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute("SELECT balance, portfolio FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
        if row:
            try: port = json.loads(row[1])
            except: port = {}
            return row[0], port
        return None, None

def create_user(username, password):
    with sqlite3.connect(DB_FILE) as conn:
        try:
            conn.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (username, password, 1000000.0, "{}"))
            return True
        except: return False

def save_user_state(username, bal, port):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("UPDATE users SET balance = ?, portfolio = ? WHERE username = ?", (bal, json.dumps(port), username))

# --- 2. 極速核心引擎 ---

@st.cache_data(ttl=86400)  # 每天只抓一次清單
def get_valid_tw_tickers():
    """
    使用 twstock 取得真實有效的上市上櫃股票代碼。
    過濾掉權證、ETF等，只留普通股以加快速度。
    """
    # 上市
    twse = twstock.twse
    # 上櫃
    tpex = twstock.tpex
    
    codes = []
    
    # 篩選條件：只要股票 (代碼長度為4)
    for code, info in twse.items():
        if info['type'] == '股票' and len(code) == 4:
            codes.append(f"{code}.TW")
            
    for code, info in tpex.items():
        if info['type'] == '股票' and len(code) == 4:
            codes.append(f"{code}.TWO")
            
    return codes

@st.cache_data(ttl=1800) # 資料快取 30 分鐘，避免多人同時使用時重複下載
def fetch_and_scan_stocks(tickers):
    """
    大批量下載與運算
    """
    qualified_list = []
    
    # 分批下載，每批 300 檔 (yfinance 在 300-500 檔效率較佳)
    chunk_size = 300
    chunks = [tickers[i:i + chunk_size] for i in range(0, len(tickers), chunk_size)]
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_chunks = len(chunks)
    
    for i, batch in enumerate(chunks):
        status_text.text(f"🚀 正在光速掃描第 {i+1}/{total_chunks} 批股票... ({len(batch)} 檔)")
        progress_bar.progress((i) / total_chunks)
        
        try:
            # 下載 40 天資料 (計算 20MA 需要)
            # threads=True 開啟多執行緒下載
            data = yf.download(batch, period="40d", group_by='ticker', threads=True, progress=False)
            
            # 處理這批資料
            # 取得所有 columns 的第一層 (Ticker)
            # yfinance 如果只下載一檔，結構會不同，這裡做個防護
            if len(batch) == 1:
                # 這裡略過單檔處理的複雜度，全量掃描通常不會只有一檔
                pass 
            
            # 遍歷這批次裡面的每一檔
            # 利用 data.columns.levels[0] 確保只跑有下載到的資料
            downloaded_tickers = data.columns.levels[0] if isinstance(data.columns, pd.MultiIndex) else []
            
            for t in downloaded_tickers:
                try:
                    df = data[t].dropna()
                    if df.empty or len(df) < 20: continue

                    # --- 極速策略邏輯 ---
                    close = float(df['Close'].iloc[-1])
                    vol = float(df['Volume'].iloc[-1]) # yfinance volume 是股數
                    
                    # 1. 快速過濾：成交量 < 1000 張 (1,000,000 股) 直接跳過
                    if vol < 1000000: continue
                    
                    # 計算均線 (只取最後的值，不存整個 Series 以省記憶體)
                    ma5 = df['Close'].rolling(5).mean().iloc[-1]
                    ma10 = df['Close'].rolling(10).mean().iloc[-1]
                    ma20 = df['Close'].rolling(20).mean().iloc[-1]
                    
                    ma_list = [ma5, ma10, ma20]
                    max_ma = max(ma_list)
                    min_ma = min(ma_list)
                    
                    # 2. 均線糾結判定 (3%)
                    if (max_ma - min_ma) / min_ma > 0.03: continue
                    
                    # 3. 突破判定 (收盤價 > 所有均線)
                    if close <= max_ma: continue
                    
                    # 4. 起漲點判定 (離 5MA 不超過 3.5%)
                    if (close - ma5) / ma5 > 0.035: continue
                    
                    # 符合條件
                    stock_id = t.split('.')[0]
                    qualified_list.append({
                        "代碼": stock_id,
                        "現價": round(close, 2),
                        "成交量": int(vol // 1000),
                        "建議停損": round(min_ma * 0.98, 2),
                        "建議停利": round(close * 1.15, 2),
                        "策略建議": "均線糾結突破 (噴發前兆)",
                        "連結": f"https://www.wantgoo.com/stock/{stock_id}"
                    })
                except:
                    continue
                    
        except Exception as e:
            # 某一批次失敗不影響整體
            continue
            
    progress_bar.progress(1.0)
    status_text.empty()
    return qualified_list

# --- 3. UI 介面 ---
init_db()

if 'login' not in st.session_state: st.session_state.login = False
if 'bal' not in st.session_state: st.session_state.bal = 1000000.0
if 'port' not in st.session_state: st.session_state.port = {}

# 側邊欄
with st.sidebar:
    st.title("⚡ 極速飆股雷達")
    if st.session_state.login:
        st.success(f"👤 {st.session_state.user}")
        st.metric("💰 餘額", f"${st.session_state.bal:,.0f}")
        if st.button("登出"):
            st.session_state.clear()
            st.rerun()
    st.divider()
    st.info("訂閱官方LINE: 811162")

# 主流程
if not st.session_state.login:
    st.title("🏹 台股全自動飆股雷達 (加速版)")
    col1, col2 = st.columns(2)
    with col1:
        st.info("### 🌙 月租 NT$ 199")
    with col2:
        st.error("### ☀️ 年租 NT$ 1,990")
        
    if st.button("查看付款資訊", use_container_width=True):
        st.warning("銀行：永豐銀行 (807) | 帳號：148-018-00054187")

    st.divider()
    t1, t2 = st.tabs(["登入", "註冊"])
    with t1:
        u = st.text_input("帳號")
        p = st.text_input("密碼", type="password")
        if st.button("登入"):
            bal, port = get_user(u, p)
            if bal is not None:
                st.session_state.login = True
                st.session_state.user = u
                st.session_state.bal = bal
                st.session_state.port = port
                st.rerun()
            else: st.error("錯誤")
    with t2:
        nu = st.text_input("新帳號")
        np = st.text_input("新密碼", type="password")
        if st.button("註冊"):
            if create_user(nu, np): st.success("成功！請登入")
            else: st.error("帳號已存在")

else:
    t1, t2 = st.tabs(["🚀 極速掃描", "💼 模擬倉"])
    
    with t1:
        st.write("### ⚡ 全台股即時掃描")
        st.caption("優化核心：已啟用多執行緒下載與無效代碼過濾。")
        
        if st.button("開始全量掃描", type="primary"):
            # 1. 獲取真實清單 (極快)
            with st.spinner("正在讀取證交所最新清單..."):
                all_tickers = get_valid_tw_tickers()
                st.toast(f"已載入 {len(all_tickers)} 檔有效股票", icon="✅")
            
            # 2. 執行掃描
            results = fetch_and_scan_stocks(all_tickers)
            
            # 3. 隨機選出 5 檔
            if len(results) > 5:
                st.session_state.scan_res = random.sample(results, 5)
                st.success(f"掃描完畢！共發現 {len(results)} 檔，隨機顯示 5 檔。")
            else:
                st.session_state.scan_res = results
                if not results: st.warning("今日無符合條件標的")
                else: st.success("掃描完畢！")

        if 'scan_res' in st.session_state:
            for s in st.session_state.scan_res:
                with st.expander(f"🔥 {s['代碼']} | ${s['現價']} | 糾結突破"):
                    c1, c2 = st.columns(2)
                    c1.write(f"量: {s['成交量']}張")
                    c1.write(f"停損: {s['建議停損']} | 停利: {s['建議停利']}")
                    c1.markdown(f"[線圖連結]({s['連結']})")
                    
                    buy_n = c2.number_input("張數", 1, 10, key=f"b_{s['代碼']}")
                    cost = buy_n * 1000 * s['現價']
                    c2.write(f"總價: ${cost:,.0f}")
                    if c2.button(f"買進 {s['代碼']}", key=f"btn_{s['代碼']}"):
                        if st.session_state.bal >= cost:
                            st.session_state.bal -= cost
                            old = st.session_state.port.get(s['代碼'], {'q':0, 'c':0})
                            st.session_state.port[s['代碼']] = {
                                'q': old['q'] + buy_n,
                                'c': old['c'] + cost
                            }
                            save_user_state(st.session_state.user, st.session_state.bal, st.session_state.port)
                            st.toast("買入成功！")
                            time.sleep(1); st.rerun()
                        else: st.error("餘額不足")

    with t2:
        st.subheader("持股明細")
        if not st.session_state.port: st.info("空倉")
        else:
            total_profit = 0
            for c, v in list(st.session_state.port.items()):
                # 簡單抓現價
                try: 
                    # 嘗試快速抓價，若失敗用成本價代替以防卡住
                    curr = yf.Ticker(f"{c}.TW").fast_info.last_price
                    if not curr: curr = yf.Ticker(f"{c}.TWO").fast_info.last_price
                except: curr = v['c'] / (v['q']*1000)
                
                if not curr: curr = v['c'] / (v['q']*1000)
                
                mkt_val = curr * v['q'] * 1000
                profit = mkt_val - v['c']
                pct = (profit / v['c']) * 100
                total_profit += profit
                
                color = "red" if profit >= 0 else "green"
                
                with st.container(border=True):
                    col1, col2, col3 = st.columns([2,2,1])
                    col1.write(f"**{c}** {v['q']}張")
                    col1.write(f"均價: {v['c']/(v['q']*1000):.1f}")
                    col2.markdown(f"損益: :{color}[${profit:,.0f} ({pct:.1f}%)]")
                    if col3.button("賣", key=f"s_{c}"):
                        st.session_state.bal += mkt_val
                        del st.session_state.port[c]
                        save_user_state(st.session_state.user, st.session_state.bal, st.session_state.port)
                        st.rerun()
            
            st.divider()
            st.markdown(f"### 總損益: :{'red' if total_profit>0 else 'green'}[${total_profit:,.0f}]")
            if st.button("重置帳戶"):
                 save_user_state(st.session_state.user, 1000000.0, {})
                 st.session_state.bal = 1000000.0
                 st.session_state.port = {}
                 st.rerun()
