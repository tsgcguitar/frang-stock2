import streamlit as st
import yfinance as yf
import pandas as pd
import random
import time
import twstock
from datetime import datetime
from supabase import create_client, Client

# --- 1. 初始化與 UI 樣式強化 ---
st.set_page_config(page_title="從從容容飆股王", layout="wide")

st.markdown("""
<style>
.stApp { background: linear-gradient(to bottom right, #001233, #000814); color: #E0F7FA; }
.stMarkdown, .stText, p, li, span, label, div { color: #FFFFFF !important; font-weight: 500; }
h1, h2, h3 { color: #00E5FF !important; text-shadow: 0 0 10px rgba(0, 229, 255, 0.6); }
h4 { color: #FFEA00 !important; }
.stock-card {
    background: rgba(0, 40, 80, 0.85);
    border: 2px solid #00B0FF;
    box-shadow: 0 0 20px rgba(0, 176, 255, 0.4);
    padding: 25px; border-radius: 15px; margin-bottom: 25px;
}
.reason-tag {
    background-color: rgba(255, 255, 255, 0.1);
    padding: 5px 10px; border-radius: 5px; font-size: 0.9em; color: #FF80AB !important;
    margin-right: 10px; border: 1px solid #FF80AB;
}
.stButton>button {
    background: linear-gradient(to bottom, #00E5FF, #00B0FF);
    color: #001233 !important;
    font-weight: 800 !important;
    border-radius: 8px; width: 100%; height: 50px;
}
.profit-up { color: #FF3D00 !important; font-size: 1.2em; font-weight: 900; }
.profit-down { color: #00E676 !important; font-size: 1.2em; font-weight: 900; }
.price-tag { color: #FFFF00 !important; font-size: 1.1em; }
.logout-btn>button {
    background: #FF5252 !important; color: white !important; height: 35px !important;
}
div[data-baseweb="select"] > div {
    background-color: #001233 !important; color: white !important; border: 1px solid #00B0FF !important;
}
div[role="listbox"] { background-color: #001233 !important; }
div[role="option"] { background-color: #001233 !important; color: white !important; }
div[role="option"]:hover { background-color: #00B0FF !important; }
</style>
""", unsafe_allow_html=True)

# Supabase 連線
SUPABASE_URL = "https://jhphmcbqtprfhvdkklps.supabase.co"
SUPABASE_KEY = "sb_publishable_qfe3kH2yYYXN_PI7KNCZMg_UJmcvJWE"
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("⚠️ 雲端資料庫連線中斷")

# --- 2. 核心功能函數 ---
@st.cache_data(ttl=86400)
def get_all_tickers():
    mapping = {}
    for code, info in twstock.twse.items():
        if len(code) == 4: mapping[f"{code}.TW"] = getattr(info, 'industry', '上市股')
    for code, info in twstock.tpex.items():
        if len(code) == 4: mapping[f"{code}.TWO"] = getattr(info, 'industry', '上櫃股')
    return mapping

# 檢查自選股是否存在並回傳正確後綴
def validate_ticker(code, mapping):
    code = code.strip()
    if f"{code}.TW" in mapping: return f"{code}.TW"
    if f"{code}.TWO" in mapping: return f"{code}.TWO"
    return None

def run_full_scan(tickers_map):
    qualified = []
    status = st.empty()
    progress = st.progress(0)
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
                    c = df['Close'].iloc[-1]
                    v = df['Volume'].iloc[-1]
                    ma5, ma10, ma20, ma60 = df['Close'].rolling(5).mean().iloc[-1], df['Close'].rolling(10).mean().iloc[-1], df['Close'].rolling(20).mean().iloc[-1], df['Close'].rolling(60).mean().iloc[-1]
                    ma60_p = df['Close'].rolling(60).mean().iloc[-2]
                    v20_a = df['Volume'].rolling(20).mean().iloc[-1]
                    
                    # 計算指標
                    ma_list = [ma5, ma10, ma20]
                    convergence_rate = (max(ma_list) - min(ma_list)) / min(ma_list) # 糾結度
                    vol_multiplier = v / v20_a if v20_a > 0 else 0 # 量增倍數
                    dist_ma5_rate = (c - ma5) / ma5 # 離MA5乖離率

                    if convergence_rate <= 0.03 and \
                       ma60 > ma60_p and c > max([ma5,ma10,ma20,ma60]) and \
                       dist_ma5_rate <= 0.05 and v > (v20_a * 1.5) and v >= 2000000:
                        
                        qualified.append({
                            "代碼": t.split('.')[0], 
                            "全代碼": t, 
                            "產業": tickers_map.get(t),
                            "現價": round(c, 2), 
                            "成交量": int(v // 2000), # 顯示為張數 (約略)
                            "停損": round(ma60, 2), 
                            "停利": round(c*1.2, 2),
                            # 新增數據欄位供顯示與排序
                            "糾結度": round(convergence_rate * 100, 2),
                            "量增倍數": round(vol_multiplier, 1),
                            "乖離率": round(dist_ma5_rate * 100, 2),
                            "raw_vol": v
                        })
                except: continue
        except: continue
    progress.empty(); status.empty()
    return qualified

# --- 3. 登入/註冊功能與介面 ---
if 'login' not in st.session_state: st.session_state.login = False

if not st.session_state.login:
    st.title("🏹 從從容容飆股王")
    st.markdown("### 🏆 買在起漲點，不追高雷達")
    col1, col2 = st.columns(2)
    # 更新價格：月費 399
    with col1: st.markdown("<div class='stock-card'><h3>🌙 月租版</h3><h1>$399</h1></div>", unsafe_allow_html=True)
    # 更新價格：年費 2990
    with col2: st.markdown("<div class='stock-card'><h3>☀️ 年費版</h3><h1>$2,990</h1></div>", unsafe_allow_html=True)
    with st.expander("💳 顯示付款資訊"):
        st.info("🏦 永豐銀行 (807) | 帳號：148-018-00054187\n\n轉帳後截圖聯繫 Line: 811162 將於30分鐘內開通。")
    
    user = st.text_input("👤 帳號 (英數共4碼以上)").strip().lower()
    pwd = st.text_input("🔑 授權碼", type="password")
    
    c_login, c_reg = st.columns(2)
    
    with c_login:
        if st.button("🚀 登入系統"):
            if pwd != "STOCK2026":
                st.error("授權碼 請聯繫Line: 811162開通")
            else:
                res = supabase.table("users").select("*").eq("username", user).execute()
                if res.data:
                    u = res.data[0]
                    st.session_state.update({
                        "login": True, "user": user, "bal": u['balance'], 
                        "port": u['portfolio'], "history": u.get('history', []),
                        "watchlist": u.get('watchlist', []) # 讀取自選清單
                    })
                    st.rerun()
                else:
                    st.error("此帳號尚未註冊，請先輸入帳號並點擊註冊")

    with c_reg:
        if st.button("📝 註冊帳號"):
            if len(user) < 4:
                st.warning("帳號長度需為 4 碼以上")
            elif pwd != "STOCK2026":
                st.error("授權碼 請聯繫Line: 811162開通")
            else:
                res = supabase.table("users").select("*").eq("username", user).execute()
                if res.data:
                    st.warning("已有此會員帳號")
                else:
                    # 初始化包含 watchlist
                    u = {"username": user, "balance": 1000000, "portfolio": {}, "history": [], "watchlist": []}
                    supabase.table("users").insert(u).execute()
                    st.success("註冊成功！請直接點擊登入")

# --- 4. 主程式分頁 ---
else:
    stat_col1, stat_col2 = st.columns([5, 1])
    stat_col1.markdown(f"👤 您好, **{st.session_state.user}** | 💰 餘額: `${st.session_state.bal:,.0f}`")
    with stat_col2:
        if st.button("🚪 登出", key="logout"):
            st.session_state.clear()
            st.rerun()

    # 新增 "❤️ 自選觀察" 分頁
    tab1, tab2, tab4, tab3 = st.tabs(["🚀 飆股雷達", "💼 雲端模擬倉", "❤️ 自選觀察", "📜 歷史損益"])
    
    mapping = get_all_tickers() # 獲取全台股列表

    # --- Tab 1: 飆股雷達 (含排序與細節) ---
    with tab1:
        if st.button("🔍 開始 1800 檔全量掃描"):
            res = run_full_scan(mapping)
            st.session_state.total_found = len(res)
            st.session_state.scan_res = res 
        
        if 'scan_res' in st.session_state:
            st.success(f"🎯 掃描完成！共找到 {st.session_state.total_found} 檔符合條件標的")
            
            # --- 新增排序選單 ---
            sort_opt = st.selectbox("🔃 排序方式", 
                ["默認", "現價 (高→低)", "成交量 (高→低)", "產業分類", "量增倍數 (高→低)"])
            
            display_data = st.session_state.scan_res
            if sort_opt == "現價 (高→低)":
                display_data = sorted(display_data, key=lambda x: x['現價'], reverse=True)
            elif sort_opt == "成交量 (高→低)":
                display_data = sorted(display_data, key=lambda x: x['raw_vol'], reverse=True)
            elif sort_opt == "產業分類":
                display_data = sorted(display_data, key=lambda x: str(x['產業']))
            elif sort_opt == "量增倍數 (高→低)":
                display_data = sorted(display_data, key=lambda x: x['量增倍數'], reverse=True)

            for s in display_data:
                with st.container():
                    # --- 更新卡片顯示：加入詳細數據 ---
                    st.markdown(f"""
                    <div class='stock-card'>
                        <div style="display:flex; justify-content:space-between;">
                            <h3>{s['代碼']} - {s['產業']}</h3>
                            <h2 style="color:#FFFF00;">${s['現價']}</h2>
                        </div>
                        <p>📊 成交量: {s['成交量']} 張 | 🛑 停損: {s['停損']} | 🎯 停利: {s['停利']}</p>
                        <hr style="border-color: #00B0FF; opacity: 0.3;">
                        <p>
                            <span class='reason-tag'>📈 量增: {s['量增倍數']}倍</span>
                            <span class='reason-tag'>🕸️ 均線糾結: {s['糾結度']}%</span>
                            <span class='reason-tag'>📏 離MA5: {s['乖離率']}%</span>
                        </p>
                        <a href='https://www.wantgoo.com/stock/{s['代碼']}' target='_blank' style="color:#00E5FF;">📈 查看線圖</a>
                    </div>""", unsafe_allow_html=True)
                    
                    with st.expander(f"🛒 買進 {s['代碼']}"):
                        qty = st.number_input("購買張數", min_value=1, value=1, key=f"q_{s['代碼']}")
                        total_cost = qty * 1000 * s['現價']
                        st.markdown(f"**預計買入總金額： `${total_cost:,.0f}`**")
                        if st.button(f"確認買進 {qty} 張", key=f"btn_{s['代碼']}"):
                            if st.session_state.bal >= total_cost:
                                st.session_state.bal -= total_cost
                                tk = s['全代碼']
                                st.session_state.port[tk] = st.session_state.port.get(tk, {'q':0, 'c':0, 'stop_loss': s['停損']})
                                st.session_state.port[tk]['q'] += qty
                                st.session_state.port[tk]['c'] += total_cost
                                supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                                st.success("交易成功！"); st.rerun()
                            else: st.error("餘額不足")

    # --- Tab 2: 雲端模擬倉 (保持不變) ---
    with tab2:
        total_unrealized_profit = 0
        col_bal, col_reset = st.columns([3, 1])
        col_bal.markdown(f"### 💰 帳戶餘額: `${st.session_state.bal:,.0f}`")
        if col_reset.button("⚠️ 重置 100 萬"):
            st.session_state.bal = 1000000
            st.session_state.port = {}
            st.session_state.history = []
            st.session_state.watchlist = []
            supabase.table("users").update({"balance": 1000000, "portfolio": {}, "history": [], "watchlist": []}).eq("username", st.session_state.user).execute()
            st.rerun()

        if st.button("🔄 刷新即時損益金額"): st.rerun()

        if st.session_state.port:
            for tk, d in list(st.session_state.port.items()):
                try:
                    ticker_obj = yf.Ticker(tk)
                    try: now_p = ticker_obj.fast_info['last_price']
                    except: now_p = ticker_obj.history(period="1d")['Close'].iloc[-1]
                    
                    cost_per_share = d['c'] / (d['q'] * 1000)
                    profit = (now_p * d['q'] * 1000) - d['c']
                    profit_rate = (profit / d['c']) * 100
                    total_unrealized_profit += profit
                    
                    stock_id = tk.split('.')[0]
                    if 'stop_loss' in d and now_p <= d['stop_loss']:
                        st.error(f"⚠️ {stock_id} 已達系統停損點，建議停損")
                    if profit_rate >= 15:
                        st.warning(f"🎊 {stock_id} 已賺超過 15% 建議觀察並停利")

                    color = "profit-up" if profit >= 0 else "profit-down"
                    st.markdown(f"""
                    <div class='stock-card'>
                        <h4>{stock_id} ({d['q']} 張)</h4>
                        <p>損益: <span class='{color}'>${profit:,.0f}</span> ({profit_rate:.2f}%)</p>
                        <p>均價: {cost_per_share:.2f} | 現價: {now_p:.2f}</p>
                    </div>""", unsafe_allow_html=True)
                    
                    with st.expander(f"💸 賣出 {stock_id}"):
                        s_qty = st.number_input("賣出張數", min_value=1, max_value=d['q'], value=d['q'], key=f"sq_{tk}")
                        est_back = s_qty * 1000 * now_p
                        st.markdown(f"**預計入帳： `${est_back:,.0f}`**")
                        if st.button(f"執行賣出 {s_qty} 張", key=f"sbtn_{tk}"):
                            cost_of_sold = (s_qty / d['q']) * d['c']
                            realized_p = est_back - cost_of_sold
                            
                            history_entry = {
                                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "month": datetime.now().strftime("%Y-%m"),
                                "stock": stock_id, "qty": s_qty, "profit": realized_p
                            }
                            st.session_state.history.append(history_entry)
                            st.session_state.bal += est_back
                            st.session_state.port[tk]['q'] -= s_qty
                            st.session_state.port[tk]['c'] -= cost_of_sold
                            if st.session_state.port[tk]['q'] <= 0: del st.session_state.port[tk]
                            
                            supabase.table("users").update({
                                "balance": st.session_state.bal, "portfolio": st.session_state.port,
                                "history": st.session_state.history
                            }).eq("username", st.session_state.user).execute()
                            st.success("賣出成功！"); st.rerun()
                except: st.warning(f"{tk} 數據更新中...")

            st.divider()
            sum_color = "profit-up" if total_unrealized_profit >= 0 else "profit-down"
            st.markdown(f"### 📈 總未實現損益: <span class='{sum_color}'>${total_unrealized_profit:,.0f}</span>", unsafe_allow_html=True)
        else: st.info("目前庫存空空如也")

    # --- Tab 4: 自選觀察清單 (新增功能) ---
    with tab4:
        st.markdown("### ❤️ 自選觀察清單")
        
        # 新增自選股輸入框
        c_add1, c_add2 = st.columns([3, 1])
        new_ticker = c_add1.text_input("輸入股票代號 (例如 2330)", placeholder="2330")
        if c_add2.button("➕ 加入清單"):
            if new_ticker:
                full_ticker = validate_ticker(new_ticker, mapping)
                if full_ticker:
                    if full_ticker not in st.session_state.watchlist:
                        st.session_state.watchlist.append(full_ticker)
                        # 更新資料庫
                        supabase.table("users").update({"watchlist": st.session_state.watchlist}).eq("username", st.session_state.user).execute()
                        st.success(f"已加入 {full_ticker}")
                        st.rerun()
                    else:
                        st.warning("已在清單中")
                else:
                    st.error("查無此代號，請確認是否為上市櫃股票")

        st.divider()

        # 顯示自選股
        if 'watchlist' in st.session_state and st.session_state.watchlist:
            # 建立移除清單的候選
            to_remove = []
            
            for tk in st.session_state.watchlist:
                try:
                    # 抓取即時資料
                    stock_id = tk.split('.')[0]
                    industry = mapping.get(tk, "未知")
                    ticker_obj = yf.Ticker(tk)
                    try:
                        now_p = ticker_obj.fast_info['last_price']
                        prev_close = ticker_obj.fast_info['previous_close']
                    except:
                        hist = ticker_obj.history(period="2d")
                        now_p = hist['Close'].iloc[-1]
                        prev_close = hist['Close'].iloc[0]
                    
                    change = (now_p - prev_close) / prev_close * 100
                    color = "profit-up" if change >= 0 else "profit-down"
                    arrow = "▲" if change >= 0 else "▼"

                    col_card, col_act = st.columns([5, 1])
                    with col_card:
                        st.markdown(f"""
                        <div class='stock-card' style='padding: 15px; margin-bottom: 10px;'>
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <div>
                                    <h3 style="margin:0;">{stock_id} <span style="font-size:0.6em; color:#ddd;">{industry}</span></h3>
                                    <a href='https://www.wantgoo.com/stock/{stock_id}' target='_blank' style="font-size:0.9em; color:#00E5FF;">📈 技術線圖</a>
                                </div>
                                <div style="text-align:right;">
                                    <h2 style="margin:0; color:#FFFF00;">${now_p:.2f}</h2>
                                    <span class='{color}'>{arrow} {change:.2f}%</span>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col_act:
                        st.write("") # Spacer
                        st.write("") 
                        if st.button("🗑️", key=f"del_{tk}"):
                            to_remove.append(tk)

                except:
                    st.warning(f"{tk} 暫時無法獲取數據")
            
            # 處理刪除
            if to_remove:
                for tr in to_remove:
                    st.session_state.watchlist.remove(tr)
                supabase.table("users").update({"watchlist": st.session_state.watchlist}).eq("username", st.session_state.user).execute()
                st.rerun()
        else:
            st.info("您的自選清單目前是空的")

    # --- Tab 3: 歷史損益 (保持不變) ---
    with tab3:
        st.markdown("### 📊 已實現損益歷史")
        if st.session_state.history:
            df_hist = pd.DataFrame(st.session_state.history)
            month_list = ["全部"] + sorted(list(df_hist['month'].unique()), reverse=True)
            sel_month = st.selectbox("📅 篩選月份", month_list)
            
            view_df = df_hist if sel_month == "全部" else df_hist[df_hist['month'] == sel_month]
            total_realized = view_df['profit'].sum()
            summary_color = "#FF3D00" if total_realized >= 0 else "#00E676"
            st.markdown(f"#### 💰 該期間總已實現損益: <span style='color:{summary_color}'>${total_realized:,.0f}</span>", unsafe_allow_html=True)
            st.dataframe(view_df[['date', 'stock', 'qty', 'profit']].sort_values('date', ascending=False), use_container_width=True)
        else:
            st.info("尚無歷史成交紀錄")
