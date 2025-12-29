import streamlit as st
import yfinance as yf
import pandas as pd

# 1. 網頁基礎設定
st.set_page_config(page_title="台股飆股雷達-付費實戰版", layout="wide")

# --- 模擬下單帳戶初始化 ---
if 'balance' not in st.session_state:
    st.session_state.balance = 1000000.0  # 起始資金 100 萬
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}  # 持倉格式: {代碼: [張數, 成本]}

# --- 🔑 付費驗證系統 ---
VALID_KEYS = ["PREMIUM888", "STOCK2026", "FRANKVVIP"] 

with st.sidebar:
    st.header("🔐 會員登入")
    user_key = st.text_input("請輸入授權碼", type="password")
    is_authenticated = user_key in VALID_KEYS
    
    if is_authenticated:
        st.success("專業實戰版已解鎖")
    elif user_key != "":
        st.error("授權碼錯誤")

    st.divider()
    st.header("💰 模擬帳戶餘額")
    st.metric("可用現金", f"${st.session_state.balance:,.0f}")
    
    if st.button("重置帳戶"):
        st.session_state.balance = 1000000.0
        st.session_state.portfolio = {}
        st.rerun()

# 2. 核心功能
st.title("🏹 台股全自動飆股雷達 (模擬實戰版)")

if not is_authenticated:
    st.warning("⚠️ 請輸入授權碼解鎖專業功能。")
else:
    # --- 策略與掃描邏輯 ---
    @st.cache_data
    def get_extended_stock_list():
        ranges = [range(1501, 1600), range(2301, 2499), range(2601, 2640), range(6101, 6299)]
        return [f"{i}.TW" for r in ranges for i in r]

    def get_industry_v2(ticker):
        try:
            code = int(ticker.split(".")[0])
            if code == 2330: return "半導體-晶圓代工"
            if 2301 <= code <= 2499: return "電子/半導體"
            if 1501 <= code <= 1599: return "電機/機電"
            return "其他/傳產"
        except: return "未知"

    def scan_breakout_pro():
        all_tickers = get_extended_stock_list()
        data = yf.download(all_tickers, period="60d", group_by='ticker', progress=False)
        results = []
        
        for ticker in all_tickers:
            try:
                df = data[ticker].dropna()
                if len(df) < 20: continue
                close = df['Close']
                curr_price, curr_vol = close.iloc[-1], df['Volume'].iloc[-1]
                
                if curr_vol < 1000000: continue # 1000張門檻
                
                ma5 = close.rolling(5).mean().iloc[-1]
                ma10 = close.rolling(10).mean().iloc[-1]
                ma20 = close.rolling(20).mean().iloc[-1]
                ma_list = [ma5, ma10, ma20]
                squeeze_ratio = (max(ma_list) - min(ma_list)) / min(ma_list)
                vol_ratio = curr_vol / df['Volume'].rolling(5).mean().iloc[-1]
                bias_5ma = (curr_price - ma5) / ma5

                # 篩選邏輯
                if curr_price > max(ma_list) and squeeze_ratio < 0.03 and bias_5ma < 0.035:
                    # --- 多樣化策略建議 ---
                    if vol_ratio > 3.0:
                        strategy = "🔥 爆量大突破：短期動能最強"
                    elif squeeze_ratio < 0.015:
                        strategy = "💎 極致糾結：盤整噴發，波段首選"
                    elif curr_price > ma20 and close.iloc[-2] <= ma20:
                        strategy = "🔄 轉強訊號：底部翻揚站上月線"
                    elif vol_ratio > 1.5 and bias_5ma < 0.01:
                        strategy = "🛡️ 潛伏起漲：帶量且風險極低"
                    else:
                        strategy = "✅ 穩定起漲：符合量價邏輯"

                    results.append({
                        "代碼": ticker.replace(".TW", ""),
                        "產業": get_industry_v2(ticker),
                        "價格": round(curr_price, 2),
                        "成交量(張)": int(curr_vol / 1000),
                        "策略建議": strategy,
                        "建議停損點": round(min(ma_list) * 0.97, 2),
                        "建議停利點": round(curr_price * 1.15, 2),
                    })
            except: continue
        return sorted(results, key=lambda x: x['成交量(張)'], reverse=True)[:5] # 只吐 5 支

    # --- UI 顯示 ---
    tab1, tab2 = st.tabs(["🚀 今日精選標的", "💼 我的模擬持倉"])

    with tab1:
        if st.button("🔍 開始全自動掃描 (限額 5 支)"):
            with st.spinner('分析中...'):
                top_picks = scan_breakout_pro()
                st.session_state.last_picks = top_picks
        
        if 'last_picks' in st.session_state:
            for stock in st.session_state.last_picks:
                with st.expander(f"📈 {stock['代碼']} - {stock['產業']} ({stock['策略建議']})"):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("目前價格", stock['價格'])
                    col2.metric("建議停利", stock['建議停利點'], delta="15%", delta_color="normal")
                    col3.metric("建議停損", stock['建議停損點'], delta="-3%", delta_color="inverse")
                    
                    # 下單 UI
                    shares = st.number_input(f"購買張數 ({stock['代碼']})", min_value=1, max_value=100, step=1, key=f"buy_{stock['代碼']}")
                    total_cost = shares * 1000 * stock['價格']
                    
                    if st.button(f"確認購買 {shares} 張", key=f"btn_{stock['代碼']}"):
                        if st.session_state.balance >= total_cost:
                            st.session_state.balance -= total_cost
                            code = stock['代碼']
                            if code in st.session_state.portfolio:
                                st.session_state.portfolio[code][0] += shares
                            else:
                                st.session_state.portfolio[code] = [shares, stock['價格']]
                            st.success(f"成功買入 {code}！花費 ${total_cost:,.0f}")
                            st.rerun()
                        else:
                            st.error("現金不足！")

    with tab2:
        if not st.session_state.portfolio:
            st.info("目前尚無持倉，快去掃描標的並下單吧！")
        else:
            portfolio_data = []
            for code, info in st.session_state.portfolio.items():
                portfolio_data.append({
                    "代碼": code,
                    "持張": info[0],
                    "成本價": info[1],
                    "目前總值": info[0] * 1000 * info[1] # 這裡可進一步串接即時價計算損益
                })
            st.table(pd.DataFrame(portfolio_data))
            if st.button("出清所有持倉 (結算)"):
                # 簡單結算邏輯
                total_value = sum(item[0] * 1000 * item[1] for item in st.session_state.portfolio.values())
                st.session_state.balance += total_value
                st.session_state.portfolio = {}
                st.success("已按成本價全數出清，回籠資金！")
                st.rerun()

# 側邊欄腳註
st.sidebar.info("💡 模擬下單僅供交易邏輯驗證，非真實投資建議。")
