import streamlit as st
import yfinance as yf
import pandas as pd
import random
import time
import twstock
from supabase import create_client, Client

# --- 1. 初始化與 UI 樣式 ---
st.set_page_config(page_title="從從容容飆股王", layout="wide")

st.markdown("""
<style>
.stApp { background: linear-gradient(to bottom right, #001233, #000814); color: #E0F7FA; }
.stMarkdown, .stText, p, li, span, label, div { color: #E6F7FF !important; }
h1, h2, h3 { color: #00E5FF !important; text-shadow: 0 0 8px rgba(0, 229, 255, 0.5); }
.stock-card {
    background: rgba(0, 30, 60, 0.75);
    border: 1px solid #00B0FF;
    box-shadow: 0 0 15px rgba(0, 176, 255, 0.3) inset;
    padding: 20px; border-radius: 12px; margin-bottom: 20px;
}
.profit-up { color: #FF5252 !important; font-weight: bold; }
.profit-down { color: #00E676 !important; font-weight: bold; }
.metric-box { background: rgba(0, 229, 255, 0.1); padding: 15px; border-radius: 8px; border: 1px dashed #00E5FF; text-align: center; margin-bottom: 20px;}
</style>
""", unsafe_allow_html=True)

# Supabase 設定
SUPABASE_URL = "https://jhphmcbqtprfhvdkklps.supabase.co"
SUPABASE_KEY = "sb_publishable_qfe3kH2yYYXN_PI7KNCZMg_UJmcvJWE"
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("⚠️ 雲端資料庫連線中斷")

# --- 2. 核心邏輯：批量掃描與策略 ---

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
    status = st.empty()
    progress = st.progress(0)
    ticker_list = list(tickers_map.keys())
    total = len(ticker_list)
    chunk_size = 50 
    
    for i in range(0, total, chunk_size):
        chunk = ticker_list[i : i + chunk_size]
        status.markdown(f"📡 正在掃描全台股: **第 {i} - {min(i+chunk_size, total)} 檔** (總計 {total})")
        progress.progress(min(i / total, 1.0))
        
        try:
            # 批量下載數據
            data = yf.download(chunk, period="160d", group_by='ticker', progress=False, threads=True)
            for t in chunk:
                try:
                    df = data[t].dropna() if len(chunk) > 1 else data.dropna()
                    if len(df) < 65: continue # 排除資料不足新股
                    
                    c = df['Close'].iloc[-1]
                    v = df['Volume'].iloc[-1]
                    ma5 = df['Close'].rolling(5).mean().iloc[-1]
                    ma10 = df['Close'].rolling(10).mean().iloc[-1]
                    ma20 = df['Close'].rolling(20).mean().iloc[-1]
                    ma60 = df['Close'].rolling(60).mean().iloc[-1]
                    ma60_prev = df['Close'].rolling(60).mean().iloc[-2]
                    v20_avg = df['Volume'].rolling(20).mean().iloc[-1]
                    
                    # 12/30 調整策略：5,10,20MA糾結，60MA向上
                    short_mas = [ma5, ma10, ma20]
                    is_tangled = (max(short_mas) - min(short_mas)) / min(short_mas) <= 0.03
                    is_ma60_up = ma60 > ma60_prev
                    is_above = c > max(ma5, ma10, ma20, ma60)
                    is_near_5ma = (c - ma5) / ma5 <= 0.05
                    is_vol_up = v > (v20_avg * 1.5)
                    is_not_cold = v >= 1000000 # 成交量需大於 1000 張

                    if is_tangled and is_ma60_up and is_above and is_near_5ma and is_vol_up and is_not_cold:
                        qualified.append({
                            "代碼": t.split('.')[0], 
                            "全代碼": t,
                            "產業": tickers_map.get(t), 
                            "現價": round(c, 2),
                            "成交量": int(v // 1000), 
                            "建議停損": round(ma60, 2), 
                            "建議停利": round(c * 1.15, 2),
                            "策略建議": "短中糾結噴發 + 季線向上支撐", 
                            "連結": f"https://www.wantgoo.com/stock/{t.split('.')[0]}"
                        })
                except: continue
            time.sleep(0.3) # 緩衝延遲
        except: continue
            
    progress.empty()
    status.empty()
    return qualified

# --- 3. 登入與訂閱頁面 ---
if 'login' not in st.session_state:
    st.session_state.login = False

if not st.session_state.login:
    st.title("🏹 從從容容飆股王")
    st.subheader("🏆 專為買在起漲點設計的投資雷達")
    
    col_a, col_b = st.columns(2)
    with col_a: st.markdown("<div class='stock-card'><h3>🌙 月租版</h3><h1>$299 /月</h1></div>", unsafe_allow_html=True)
    with col_b: st.markdown("<div class='stock-card'><h3>☀️ 年費版</h3><h1>$2,990 /年</h1><p>🎁 省下 2 個月月費</p></div>", unsafe_allow_html=True)
    
    with st.expander("💳 點擊展開付款資訊"):
        st.write("🏦 **永豐銀行 (807)** | 帳號：**148-018-00054187**")
        st.info("📢 轉帳後請截圖聯繫 官方Line: 811162，將於 30 分鐘內開通帳號。")

    user = st.text_input("👤 使用者帳號")
    pwd = st.text_input("🔑 授權碼", type="password")
    if st.button("🚀 登入系統"):
        if pwd == "STOCK2026": 
            res = supabase.table("users").select("*").eq("username", user).execute()
            if res.data:
                u_data = res.data[0]
            else:
                u_data = {"username": user, "balance": 1000000, "portfolio": {}}
                supabase.table("users").insert(u_data).execute()
            st.session_state.update({"login":True, "user":user, "bal":u_data['balance'], "port":u_data['portfolio']})
            st.rerun()
        else: st.error("授權碼錯誤")

# --- 4. 主程式介面 ---
else:
    tab1, tab2 = st.tabs(["🚀 飆股雷達", "💼 雲端模擬倉"])
    
    with tab1:
        st.info("💡 操作提醒：已過濾成交量 < 1000 張標的。若收盤價跌破『建議停損點』請果斷離場。")
        if st.button("🔍 開始 1700 檔全量掃描 (需時約 1-2 分鐘)"):
            all_m = get_all_tickers()
            res = run_full_scan(all_m)
            st.session_state.total_found = len(res)
            st.session_state.scan_res = random.sample(res, min(5, len(res)))
        
        if 'scan_res' in st.session_state:
            st.markdown(f"<div class='metric-box'>🎯 掃描完成！全市場共有 <b>{st.session_state.total_found}</b> 檔符合條件，隨機推薦 5 檔：</div>", unsafe_allow_html=True)
            for s in st.session_state.scan_res:
                with st.container():
                    st.markdown(f"""
                    <div class='stock-card'>
                        <h4>{s['代碼']} - {s['產業']} | <span style='color:#00E5FF'>現價: ${s['現價']}</span></h4>
                        <p>📊 成交量: {s['成交量']} 張 | 💡 {s['策略建議']}</p>
                        <p>🛑 建議停損: {s['建議停損']} | 🎯 建議停利: {s['建議停利']}</p>
                        <a href='{s['連結']}' target='_blank' style='color:#00E5FF'>📈 查看詳細線圖</a>
                    </div>""", unsafe_allow_html=True)
                    
                    # 買入功能 (增加張數選擇)
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        qty = st.number_input("購買張數", min_value=1, max_value=100, value=1, key=f"qty_{s['代碼']}")
                    with col2:
                        if st.button(f"買進 {qty} 張 {s['代碼']}", key=f"buy_{s['代碼']}"):
                            cost = qty * 1000 * s['現價']
                            if st.session_state.bal >= cost:
                                st.session_state.bal -= cost
                                # 以全代碼 (含後綴) 為索引
                                ticker_key = s['全代碼']
                                st.session_state.port[ticker_key] = st.session_state.port.get(ticker_key, {'q':0, 'c':0})
                                st.session_state.port[ticker_key]['q'] += qty
                                st.session_state.port[ticker_key]['c'] += cost
                                supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                                st.success(f"成功買進 {s['代碼']} {qty} 張")
                                st.rerun()
                            else: st.error("帳戶餘額不足")

    with tab2:
        st.subheader(f"💰 帳戶餘額: ${st.session_state.bal:,.0f}")
        if st.session_state.port:
            st.markdown("### 📊 庫存明細 (點擊刷新股價計算損益)")
            for full_ticker, d in list(st.session_state.port.items()):
                try:
                    # 使用全代碼下載，確保報價成功
                    now_data = yf.download(full_ticker, period="1d", progress=False)
                    now_p = float(now_data['Close'].iloc[-1])
                    current_value = now_p * d['q'] * 1000
                    profit = current_value - d['c']
                    profit_pct = (profit / d['c']) * 100 if d['c'] > 0 else 0
                    color = "profit-up" if profit >= 0 else "profit-down"
                    
                    st.markdown(f"""
                    <div class='stock-card'>
                        <b>{full_ticker.split('.')[0]}</b> ({d['q']} 張) | 損益: <span class='{color}'>${profit:,.0f} ({profit_pct:.2f}%)</span>
                        <p>成本: {d['c']/(d['q']*1000):.2f} | 現價: {now_p:.2f}</p>
                    </div>""", unsafe_allow_html=True)
                    
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        sell_qty = st.number_input("賣出張數", min_value=1, max_value=d['q'], value=d['q'], key=f"sell_qty_{full_ticker}")
                    with col2:
                        if st.button(f"執行賣出 {sell_qty} 張", key=f"sell_{full_ticker}"):
                            # 比例計算回收成本與金額
                            sell_value = sell_qty * 1000 * now_p
                            cost_of_sold = (sell_qty / d['q']) * d['c']
                            
                            st.session_state.bal += sell_value
                            st.session_state.port[full_ticker]['q'] -= sell_qty
                            st.session_state.port[full_ticker]['c'] -= cost_of_sold
                            
                            if st.session_state.port[full_ticker]['q'] <= 0:
                                del st.session_state.port[full_ticker]
                                
                            supabase.table("users").update({"balance": st.session_state.bal, "portfolio": st.session_state.port}).eq("username", st.session_state.user).execute()
                            st.rerun()
                except:
                    st.warning(f"⚠️ 無法取得 {full_ticker} 即時報價，請稍後再試。")
        else:
            st.info("目前庫存空空如也，快去雷達尋找飆股吧！")
