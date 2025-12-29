import streamlit as st
import yfinance as yf
import pandas as pd
import sqlite3
import json
import time
from datetime import datetime

# --- 1. 系統設定與資料庫初始化 ---
st.set_page_config(page_title="台股起漲點雷達-官方版", layout="wide")

# 初始化資料庫
def init_db():
    conn = sqlite3.connect("trading_radar_v8.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            balance REAL,
            portfolio TEXT
        )
    """)
    conn.commit()
    conn.close()

def load_user_data(username):
    conn = sqlite3.connect("trading_radar_v8.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance, portfolio FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0], json.loads(row[1])
    else:
        # 初始 100 萬起始金
        return 1000000.0, {}

def save_user_data(username, balance, portfolio):
    conn = sqlite3.connect("trading_radar_v8.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (username, balance, portfolio) VALUES (?, ?, ?)",
                   (username, balance, json.dumps(portfolio)))
    conn.commit()
    conn.close()

# --- 2. 核心掃描策略 (修正掃描沒反應的問題) ---
@st.cache_data(ttl=3600)
def get_all_taiwan_tickers():
    """產生台股清單: 上市(.TW)與上櫃(.TWO)常用區間"""
    # 這裡僅列出主要區間，實務上可導入更完整的 excel 清單
    list_tw = [f"{i}.TW" for i in range(1101, 9999)]
    list_two = [f"{i}.TWO" for i in range(1101, 9999)]
    return list_tw + list_two

def run_radar_scan(ticker_list):
    results = []
    found_count = 0
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 為了加速，我們採取分批抽樣掃描，或在實際環境中縮小範圍
    # yf.download 建議不要一次超過 100 檔，否則易被封 IP 或超時
    batch_size = 50
    total_to_check = 600 # 限制掃描前 600 檔以確保速度，可根據需求調整
    
    for i in range(0, total_to_check, batch_size):
        batch = ticker_list[i : i + batch_size]
        status_text.text(f"正在雷達掃描中... 已掃描 {i}/{total_to_check} 檔")
        progress_bar.progress(i / total_to_check)
        
        try:
            # 抓取最近 40 天資料
            data = yf.download(batch, period="40d", group_by='ticker', progress=False, threads=True)
            
            for ticker in batch:
                if found_count >= 5: break # 限制顯示 5 檔
                
                df = data[ticker] if len(batch) > 1 else data
                df = df.dropna()
                
                if len(df) < 25: continue # 排除新股 (至少要能算出20MA)
                
                # 計算數據
                close = float(df['Close'].iloc[-1])
                vol = float(df['Volume'].iloc[-1]) / 1000 # 換算張數
                ma5 = df['Close'].rolling(5).mean().iloc[-1]
                ma10 = df['Close'].rolling(10).mean().iloc[-1]
                ma20 = df['Close'].rolling(20).mean().iloc[-1]
                
                # 邏輯判斷
                ma_list = [ma5, ma10, ma20]
                ma_max, ma_min = max(ma_list), min(ma_list)
                gap = (ma_max - ma_min) / ma_min # 糾結度
                
                # 篩選條件
                cond_vol = vol >= 1000 # 成交量 > 1000張
                cond_knot = gap <= 0.03 # 均線糾結 3% 以內
                cond_break = close > ma_max # 站上所有均線
                cond_not_too_high = (close - ma5) / ma5 <= 0.035 # 離5MA不超過3.5%
                
                if cond_vol and cond_knot and cond_break and cond_not_too_high:
                    # 獲取產業資訊
                    try:
                        info = yf.Ticker(ticker).info
                        industry = info.get('industry', '其他')
                    except:
                        industry = "資訊傳輸中"
                        
                    results.append({
                        "代碼": ticker.split('.')[0],
                        "產業": industry,
                        "目前價格": round(close, 2),
                        "成交量": int(vol),
                        "策略建議": "均線糾結突破 (起漲點)",
                        "建議停損點": round(ma_min * 0.98, 2),
                        "建議停利點": round(close * 1.15, 2),
                        "連結": f"https://www.wantgoo.com/stock/{ticker.split('.')[0]}"
                    })
                    found_count += 1
        except Exception as e:
            continue
            
        if found_count >= 5: break

    progress_bar.empty()
    status_text.empty()
    return results

# --- 3. UI 介面實作 ---
init_db()

# Session State 初始化
if 'is_logged_in' not in st.session_state:
    st.session_state.is_logged_in = False

# 側邊欄：登入與基本資訊
with st.sidebar:
    st.header("🔐 雷達系統登入")
    if not st.session_state.is_logged_in:
        user_id = st.text_input("帳號 (ID)")
        user_pw = st.text_input("授權碼 / 密碼", type="password")
        if st.button("啟動雷達系統", use_container_width=True):
            if user_pw in ["PREMIUM888", "STOCK2026", "FRANKVVIP"] and user_id:
                bal, port = load_user_data(user_id)
                st.session_state.current_user = user_id
                st.session_state.balance = bal
                st.session_state.portfolio = port
                st.session_state.is_logged_in = True
                st.rerun()
            else:
                st.error("授權碼無效，請聯繫下方 LINE 客服")
    else:
        st.success(f"👤 用戶: {st.session_state.current_user}")
        st.metric("💰 模擬倉餘額", f"${st.session_state.balance:,.0f}")
        if st.button("登出帳號"):
            st.session_state.clear()
            st.rerun()
    
    st.divider()
    st.write("🆘 訂閱與技術支援")
    st.info("官方 LINE ID: **811162**")

# 主頁面邏輯
if not st.session_state.is_logged_in:
    # --- 登入前：顯示產品說明與訂閱計畫 ---
    st.title("🏹 台股全自動飆股雷達")
    st.markdown("### 領先市場，買在起漲點")
    
    col_info, col_img = st.columns([2, 1])
    with col_info:
        st.info("""
        **關於此工具** 這是一款專為不喜歡追高的投資者又想要買在起漲點設計的雷達。
        
        **📢 操作小提醒：**
        1. **停損建議**：若收盤價跌破『建議停損點』，應果斷執行紀律。
        2. **量能門檻**：已過濾成交量 < 1000 張的冷門股。
        3. **產業連動**：若同產業多檔上榜，則該族群為強勢主流。
        """)
    
    st.divider()
    st.subheader("💎 選擇您的訂閱計畫")
    plan1, plan2 = st.columns(2)
    
    with plan1:
        st.markdown("#### 🌙 月租專業版")
        st.code("NT$ 199 / 月")
        if st.button("查看付款資訊 (月租)", use_container_width=True):
            st.warning("【匯款資訊】\n銀行：永豐銀行 (807)\n帳號：148-018-00054187\n金額：199 元\n\n💡 匯款後請截圖發送至 811162 LINE ID，附上後五碼，將於30分鐘內幫您開通。")
            
    with plan2:
        st.markdown("#### ☀️ 年租尊榮版")
        st.code("NT$ 1,990 / 年")
        if st.button("查看付款資訊 (年租)", use_container_width=True, type="primary"):
            st.warning("【匯款資訊】\n銀行：永豐銀行 (807)\n帳號：148-018-00054187\n金額：1,990 元\n\n💡 匯款後請截圖發送至 811162 LINE ID，附上後五碼，將於30分鐘內幫您開通。")

else:
    # --- 登入後：功能分頁 ---
    tab1, tab2 = st.tabs(["🚀 起漲點掃描", "💼 個人模擬倉"])
    
    with tab1:
        if st.button("🔍 開始掃描全台股突破標的", type="primary", use_container_width=True):
            with st.spinner("雷達正在過濾全台股標的，請稍候..."):
                all_tickers = get_all_taiwan_tickers()
                st.session_state.scan_results = run_radar_scan(all_tickers)
        
        if 'scan_results' in st.session_state:
            if not st.session_state.scan_results:
                st.warning("目前市場尚未篩選到符合「糾結突破」條件的標的，請稍後再試。")
            else:
                for s in st.session_state.scan_results:
                    with st.expander(f"📈 {s['代碼']} - {s['產業']} | 現價: {s['目前價格']}", expanded=True):
                        c1, c2 = st.columns([1, 1])
                        with c1:
                            st.write(f"**成交量:** {s['成交量']} 張")
                            st.write(f"**策略建議:** :blue[{s['策略建議']}]")
                            st.write(f"**建議停損:** :red[{s['建議停損點']}] | **停利:** :green[{s['建議停利點']}]")
                            st.markdown(f"[🔗 點我查看即時線圖]({s['連結']})")
                        
                        with c2:
                            num = st.number_input("購買張數", 1, 100, key=f"n_{s['代碼']}")
                            total_cost = num * 1000 * s['目前價格']
                            st.markdown(f"#### 預估金額: :orange[NT$ {total_cost:,.0f}]")
                            if st.button(f"確認下單 {s['代碼']}", key=f"b_{s['代碼']}"):
                                if st.session_state.balance >= total_cost:
                                    st.session_state.balance -= total_cost
                                    # 更新庫存 (平均成本計算)
                                    code = s['代碼']
                                    old_q, old_c = st.session_state.portfolio.get(code, [0, 0])
                                    new_q = old_q + num
                                    new_c = ((old_q * old_c) + total_cost) / new_q
                                    st.session_state.portfolio[code] = [new_q, new_c]
                                    
                                    save_user_data(st.session_state.current_user, st.session_state.balance, st.session_state.portfolio)
                                    st.success(f"✅ 成功購入 {code} {num}張！")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("餘額不足，無法購買！")

    with tab2:
        st.subheader("📊 持股明細與資產")
        if not st.session_state.portfolio:
            st.info("目前模擬倉無持股。")
        else:
            p_data = []
            for code, (q, c) in st.session_state.portfolio.items():
                p_data.append({"股票代碼": code, "持股張數": q, "平均成本": round(c, 2), "總投入": round(q*c*1000, 0)})
            st.dataframe(pd.DataFrame(p_data), use_container_width=True)
            
            if st.button("⚠️ 重置帳戶資產 (回復至100萬)"):
                st.session_state.balance = 1000000.0
                st.session_state.portfolio = {}
                save_user_data(st.session_state.current_user, 1000000.0, {})
                st.rerun()
