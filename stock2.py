import streamlit as st
import yfinance as yf
import pandas as pd
import twstock
from datetime import datetime
from supabase import create_client, Client

# --- 1. 初始化與 UI 樣式強化 (精準控制顏色) ---
st.set_page_config(page_title="從從容容飆股王", layout="wide")

st.markdown("""
<style>
/* 整體背景與主要文字 */
.stApp { background: linear-gradient(to bottom right, #001233, #000814); color: #FFFFFF; }

/* 標題與飆股卡片 */
h1, h2, h3 { color: #00E5FF !important; text-shadow: 0 0 10px rgba(0, 229, 255, 0.6); }
.stock-card {
    background: rgba(0, 40, 80, 0.85);
    border: 2px solid #00B0FF;
    box-shadow: 0 0 20px rgba(0, 176, 255, 0.4);
    padding: 25px; border-radius: 15px; margin-bottom: 25px;
}

/* 修正：不要強制所有 div 變白，避免影響下拉選單 */
.stMarkdown p, .stText, label { color: #FFFFFF !important; font-weight: 500; }

/* 針對下拉選單 (Selectbox) 與輸入框的文字顏色修正 */
div[data-baseweb="select"] > div { background-color: #001a35 !important; color: #FFFFFF !important; }
div[role="listbox"] { background-color: #001a35 !important; }
div[role="option"] { color: #FFFFFF !important; }

/* 表格顏色強化 */
.stTable { background-color: rgba(255,255,255,0.05); color: #FFFFFF !important; }
.stTable td, .stTable th { color: #FFFFFF !important; border-bottom: 1px solid #00B0FF !important; }

.profit-up { color: #FF3D00 !important; font-size: 1.2em; font-weight: 900; }
.profit-down { color: #00E676 !important; font-size: 1.2em; font-weight: 900; }
.price-tag { color: #FFFF00 !important; font-size: 1.1em; }
</style>
""", unsafe_allow_html=True)

# Supabase 連線
SUPABASE_URL = "https://jhphmcbqtprfhvdkklps.supabase.co"
SUPABASE_KEY = "sb_publishable_qfe3kH2yYYXN_PI7KNCZMg_UJmcvJWE"
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("⚠️ 雲端資料庫連線中斷")

# --- 2. 核心功能函數 (保持掃描邏輯) ---
@st.cache_data(ttl=86400)
def get_all_tickers():
    mapping = {}
    for code, info in twstock.twse.items():
        if len(code) == 4: mapping[f"{code}.TW"] = getattr(info, 'industry', '上市股')
    for code, info in twstock.tpex.items():
        if len(code) == 4: mapping[f"{code}.TWO"] = getattr(info, 'industry', '上櫃股')
    return mapping

def run_full_scan(tickers_map):
    qualified = []
    status = st.empty(); progress = st.progress(0)
    ticker_list = list(tickers_map.keys())
    chunk_size = 50 
    for i in range(0, len(ticker_list), chunk_size):
        chunk = ticker_list[i : i + chunk_size]
        status.markdown(f"📡 正在掃描: **{i}/{len(ticker_list)}** 檔")
        progress.progress(min(i / len(ticker_list), 1.0))
        try:
            data = yf.download(chunk, period="150d", group_by='ticker', progress=False, threads=True)
            for t in chunk:
                try:
                    df = data[t].dropna() if len(chunk) > 1 else data.dropna()
                    if len(df) < 65: continue
                    c = df['Close'].iloc[-1]; v = df['Volume'].iloc[-1]
                    ma5, ma10, ma20, ma60 = df['Close'].rolling(5).mean().iloc[-1], df['Close'].rolling(10).mean().iloc[-1], df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(60).mean().iloc[-1]
                    ma60_p = df['Close'].rolling(60).mean().iloc[-2]
                    v20_a = df['Volume'].rolling(20).mean().iloc[-1]
                    if (max([ma5,ma10,ma20])-min([ma5,ma10,ma20]))/min([ma5,ma10,ma20]) <= 0.03 and ma60 > ma60_p and c > max([ma5,ma10,ma20,ma60]) and (c - ma5)/ma5 <= 0.05 and v > (v20_a * 1.5) and v >= 1000000:
                        qualified.append({"代碼": t.split('.')[0], "全代碼": t, "產業": tickers_map.get(t), "現價": round(c, 2), "成交量": int(v // 1000), "停損": round(ma60, 2), "停利": round(c*1.15, 2)})
                except: continue
        except: continue
    progress.empty(); status.empty()
    return qualified

# --- 3. 登入介面 (修正歷史紀錄抓取邏輯) ---
if 'login' not in st.session_state: st.session_state.login = False

if not st.session_state.login:
    st.title("🏹 從從容容飆股王")
    user = st.text_input("👤 帳號 (請輸入小寫避免同步錯誤)").lower()
    pwd = st.text_input("🔑 授權碼", type="password")
    if st.button("🚀 登入"):
        if pwd == "STOCK2026":
            res = supabase.table("users").select("*").eq("username", user).execute()
            if res.data:
                u = res.data[0]
                # 重要：明確檢查 history 欄位，若沒有則設為空清單
                st.session_state.update({
                    "login": True, "user": user, 
                    "bal": u.get('balance', 1000000), 
                    "port": u.get('portfolio', {}), 
                    "history": u.get('history') if u.get('history') else []
                })
            else:
                u = {"username": user, "balance": 1000000, "portfolio": {}, "history": []}
                supabase.table("users").insert(u).execute()
                st.session_state.update({"login": True, "user": user, "bal": 1000000, "port": {}, "history": []})
            st.rerun()
        else:
            st.error("授權碼 請聯繫Line: 811162開通")

# --- 4. 主分頁內容 ---
else:
    tab1, tab2, tab3 = st.tabs(["🚀 飆股雷達", "💼 雲端模擬倉", "📊 歷史損益"])
    
    with tab1:
        if st.button("🔍 開始 1700 檔全量掃描"):
            res = run_full_scan(get_all_tickers())
            st.session_state.total_found = len(res); st.session_state.scan_res = res
        if 'scan_res' in st.session_state:
            st.success(f"🎯 掃描完成！共找到 {st.session_state.total_found} 檔標的")
            for s in st.session_state.scan_res:
                with st.container():
                    st.markdown(f"<div class='stock-card'><h3>{s['代碼']} - {s['產業']}</h3><p>💰 現價: <span class='price-tag'>${s['現價']}</span> | 🛑 停損: {s['停損']} | 🎯 停利: {s['停利']}</p><a href='https://www.wantgoo.com/stock/{s['代碼']}' target='_blank'>📈 查看線圖</a></div>", unsafe_allow_html=True)
                    with st.expander(f"🛒 買進 {s['代碼']}"):
                        qty = st.number_input("張數", min_value=1, value=1, key=f"q_{s['代碼']}")
                        total_cost = qty * 1000 * s['現價']
                        if st.button(f"確認買進", key=f"btn_{s['代碼']}"):
                            if st.session_state.bal >= total_cost:
                                st.session_state.bal -= total_cost
                                tk = s['全代碼']
                                st.session_state.port[tk] = st.session_state.port.get(tk, {'q':0, 'c':0})
                                st.session_state.port[tk]['q'] += qty; st.session_state.port[tk]['c'] += total_cost
                                supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                                st.success("交易成功！"); st.rerun()
                            else: st.error("餘額不足")

    with tab2:
        st.button("🔄 刷新即時報價")
        total_unrealized = 0
        st.markdown(f"### 💰 帳戶餘額: `${st.session_state.bal:,.0f}`")
        
        if st.session_state.port:
            for tk, d in list(st.session_state.port.items()):
                try:
                    ticker_obj = yf.Ticker(tk); hist = ticker_obj.history(period="65d")
                    now_p = hist['Close'].iloc[-1]; ma60_val = hist['Close'].rolling(60).mean().iloc[-1]
                    profit = (now_p * d['q'] * 1000) - d['c']; profit_pct = (profit / d['c']) * 100
                    total_unrealized += profit
                    
                    if now_p <= ma60_val: st.error(f"⚠️ {tk.split('.')[0]} 已達停損點位！")
                    if profit_pct >= 15: st.warning(f"🎊 {tk.split('.')[0]} 獲利超 15%！")

                    st.markdown(f"<div class='stock-card'><h4>{tk.split('.')[0]} ({d['q']} 張)</h4><p>損益: <span class='{'profit-up' if profit>=0 else 'profit-down'}'>${profit:,.0f}</span> ({profit_pct:.2f}%)</p><p>現價: {now_p:.2f} | 成本: {d['c']/(d['q']*1000):.2f}</p></div>", unsafe_allow_html=True)
                    
                    with st.expander(f"💸 賣出 {tk.split('.')[0]}"):
                        s_qty = st.number_input("賣出張數", min_value=1, max_value=d['q'], value=d['q'], key=f"sq_{tk}")
                        if st.button(f"執行賣出", key=f"sbtn_{tk}"):
                            realized_val = s_qty * 1000 * now_p
                            cost_share = (s_qty / d['q']) * d['c']
                            realized_profit = realized_val - cost_share
                            
                            # 儲存歷史紀錄
                            new_rec = {"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "tk": tk.split('.')[0], "profit": round(realized_profit, 0)}
                            st.session_state.history.append(new_rec)
                            
                            st.session_state.bal += realized_val
                            st.session_state.port[tk]['q'] -= s_qty; st.session_state.port[tk]['c'] -= cost_share
                            if st.session_state.port[tk]['q'] <= 0: del st.session_state.port[tk]
                            
                            # 同步到 Supabase
                            supabase.table("users").update({
                                "balance": st.session_state.bal, 
                                "portfolio": st.session_state.port, 
                                "history": st.session_state.history
                            }).eq("username", st.session_state.user).execute()
                            st.success("已賣出並紀錄損益"); st.rerun()
                except: st.warning(f"無法取得 {tk} 報價")
            st.markdown(f"### 📈 未實現總損益: <span class='{'profit-up' if total_unrealized>=0 else 'profit-down'}'>${total_unrealized:,.0f}</span>", unsafe_allow_html=True)
        else: st.info("目前無庫存")

    with tab3:
        st.markdown("### 📊 已實現損益查詢")
        if st.session_state.history:
            df_hist = pd.DataFrame(st.session_state.history)
            df_hist['date_dt'] = pd.to_datetime(df_hist['date'])
            
            # 月份篩選器 (顏色已修正)
            months = sorted(df_hist['date_dt'].dt.strftime('%Y-%m').unique().tolist(), reverse=True)
            selected_month = st.selectbox("📅 選擇查詢月份", ["全部顯示"] + months)
            
            if selected_month != "全部顯示":
                filtered_df = df_hist[df_hist['date_dt'].dt.strftime('%Y-%m') == selected_month]
            else:
                filtered_df = df_hist
            
            total_r = filtered_df['profit'].sum()
            st.markdown(f"#### 💰 {selected_month} 累計盈虧: `${total_r:,.0f}`")
            # 顯示表格 (排除隱藏的日期欄位)
            st.table(filtered_df[['date', 'tk', 'profit']].sort_values(by='date', ascending=False))
        else:
            st.info("尚無歷史紀錄")
