import streamlit as st
import yfinance as yf
import pandas as pd

# 1. 網頁基礎設定
st.set_page_config(page_title="台股飆股雷達-付費專業版", layout="wide")

# --- 🔑 付費驗證系統 ---
# 你可以在這裡設定多組授權碼，或是未來對接資料庫
VALID_KEYS = ["PREMIUM888", "STOCK2024", "FRANKVIP"] 

with st.sidebar:
    st.header("🔐 會員登入")
    user_key = st.text_input("請輸入授權碼以解鎖功能", type="password")
    
    if user_key in VALID_KEYS:
        st.success("驗證成功：專業版已解鎖")
        is_authenticated = True
    elif user_key == "":
        st.info("請輸入授權碼。欲購買授權請聯絡管理員。")
        is_authenticated = False
    else:
        st.error("授權碼錯誤，請重新輸入。")
        is_authenticated = False

    st.divider()
    st.write("📩 **購買授權或回報問題**")
    st.write("官方 LINE: @your_id")
    st.write("版本：v2.1 (付費專用版)")

# 2. 核心功能 (只有驗證通過才會執行)
st.title("🏹 台股全自動飆股雷達 (專業版)")

if not is_authenticated:
    st.warning("⚠️ 此為付費專業工具，請於左側選單輸入授權碼解鎖。")
    st.image("https://images.unsplash.com/photo-1611974717482-98252430424b?auto=format&fit=crop&w=800&q=80") # 放一張美觀的示意圖
else:
    st.markdown("當前邏輯：**均線極度糾結 + 單日量能 > 1000張 + 剛帶量突破 + 低乖離防追高**")

    # --- 以下為你原本的強大程式碼 ---
    @st.cache_data
    def get_extended_stock_list():
        ranges = [
            range(1101, 1110), range(1501, 1600), range(2301, 2499),
            range(2601, 2640), range(2801, 2900), range(3001, 3100),
            range(3201, 3700), range(4901, 5000), range(6101, 6299),
            range(8001, 8299)
        ]
        return [f"{i}.TW" for r in ranges for i in r]

    def get_industry_v2(ticker):
        try:
            code = int(ticker.split(".")[0])
            if code == 2330: return "半導體-晶圓代工"
            if code == 2317: return "電子代工-鴻海"
            if code in [1513, 1514, 1519, 6806]: return "綠能/重電/儲能"
            if 2301 <= code <= 2499: return "電子/半導體"
            if 2601 <= code <= 2699: return "航運/航空"
            if 2801 <= code <= 2899: return "金融金控"
            return "其他/傳產"
        except: return "未知"

    def scan_breakout_pro():
        all_tickers = get_extended_stock_list()
        data = yf.download(all_tickers, period="60d", group_by='ticker', progress=False)
        results = []
        progress_bar = st.progress(0)
        
        for i, ticker in enumerate(all_tickers):
            try:
                df = data[ticker].dropna()
                if len(df) < 20: continue
                close = df['Close']
                curr_price, curr_vol = close.iloc[-1], df['Volume'].iloc[-1]
                
                if curr_vol < 1000000: continue # 1000張門檻
                
                ma5, ma10, ma20 = close.rolling(5).mean().iloc[-1], close.rolling(10).mean().iloc[-1], close.rolling(20).mean().iloc[-1]
                ma_list = [ma5, ma10, ma20]
                squeeze_ratio = (max(ma_list) - min(ma_list)) / min(ma_list)
                vol_ratio = curr_vol / df['Volume'].rolling(5).mean().iloc[-1]
                bias_5ma = (curr_price - ma5) / ma5

                if curr_price > max(ma_list) and squeeze_ratio < 0.03 and bias_5ma < 0.035 and vol_ratio > 1.2:
                    strategy = "🔥 爆量大突破" if vol_ratio > 3.0 else "✅ 安全起漲"
                    results.append({
                        "代碼": ticker.replace(".TW", ""),
                        "產業": get_industry_v2(ticker),
                        "價格": round(curr_price, 2),
                        "成交量(張)": int(curr_vol / 1000),
                        "策略建議": strategy,
                        "建議停損點": round(min(ma_list), 2),
                        "連結": f"https://tw.stock.yahoo.com/quote/{ticker}"
                    })
            except: continue
            progress_bar.progress((i + 1) / len(all_tickers))
        return sorted(results, key=lambda x: x['成交量(張)'], reverse=True)[:20]

    if st.button("🚀 執行全台股專業掃描"):
        with st.spinner('大數據分析中...'):
            top_picks = scan_breakout_pro()
            if top_picks:
                st.dataframe(pd.DataFrame(top_picks), use_container_width=True, hide_index=True,
                             column_config={"連結": st.column_config.LinkColumn("查看線圖")})
            else:
                st.warning("目前無符合標的。")