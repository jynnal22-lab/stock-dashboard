import streamlit as st
import yfinance as yf
import random
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import timedelta, datetime, timezone
from email.utils import parsedate_to_datetime
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

st.set_page_config(page_title="실시간 주식 차트 대시보드 Ver 4.2 (예측 강화)", layout="wide")

st.markdown("""
    <style>
        .block-container {
            padding-top: 3rem !important; 
            padding-bottom: 0rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
        
        #MainMenu { visibility: hidden; }
        .stDeployButton { display: none; }
        [data-testid="stAppDeployButton"] { display: none !important; }
        
        [data-testid="stSidebarUserContent"] {
            padding-top: 1rem !important;
        }
        
        div.row-widget.stRadio > div {
            margin-top: -10px;
            margin-bottom: -20px;
        }
        
        .stTabs {
            margin-top: -15px;
        }
        .stTabs [data-baseweb="tab-list"] {
            margin-bottom: -10px;
        }
        [data-baseweb="tab-panel"] {
            padding-top: 0rem !important;
        }
        
        .stAlert {
            padding-top: 0.2rem !important;
            padding-bottom: 0.2rem !important;
            margin-top: 5px !important;
            margin-bottom: 0px !important;
        }
        
        h4 {
            padding-bottom: 0px !important;
            margin-bottom: 0px !important;
        }
        
        [data-testid="stMetricValue"] {
            font-size: 1.5rem;
        }
    </style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def get_usd_krw_info():
    try:
        ex_rate_info = yf.Ticker("USDKRW=X").history(period="1d")
        rate = ex_rate_info['Close'].iloc[-1]
        dt = ex_rate_info.index[-1]
        return rate, dt.strftime("%Y-%m-%d %H:%M 기준")
    except:
        return 1350.0, "환율 로딩 오류"

usd_to_krw, usd_to_krw_time = get_usd_krw_info()

@st.cache_data(ttl=10)
def get_history_data(ticker, period, interval, prepost=False):
    try:
        return yf.Ticker(ticker).history(period=period, interval=interval, prepost=prepost)
    except:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def get_daily_data(ticker):
    try:
        return yf.Ticker(ticker).history(period="5d", interval="1d")
    except:
        return pd.DataFrame()

TICKER_NAMES = {
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스",
    "TSLA": "테슬라",
    "INTC": "인텔",
    "NVDA": "엔비디아",
    "AAPL": "애플",
    "GOOGL": "구글(알파벳 A)"
}

@st.cache_data(ttl=86400)
def get_kor_name(ticker):
    if ticker in TICKER_NAMES:
        return TICKER_NAMES[ticker]
    try:
        t_info = yf.Ticker(ticker).info
        return t_info.get('shortName') or t_info.get('longName', "")
    except:
        return ""


with st.sidebar:
    st.markdown("### 📈 주식 차트 대시보드 V4.2 (예측 강화)")
    
    with st.expander("✨ V4.2 패치 내용 보기"):
        st.markdown(
            """
            - **복합 모멘텀 예측 알고리즘 탑재:** RSI, 볼린저 밴드, 스토캐스틱, OBV 4가지 지표를 종합 분석하여 예측선 도출
            - **예측 신뢰 구간 시각화:** 변동성을 반영한 예상 가격 범위(상하단 밴드) 제공
            - 차트 상하 중앙 정렬 최적화
            """
        )

    clock_html = """
    <style>
        .clock-container {
            color: #E0E0E0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            font-size: 16px; 
            font-weight: bold; 
            text-align: center; 
            padding: 3px 0;
        }
        .refresh-container {
            text-align: center; 
            color: gray; 
            font-size: 14px; 
            margin-top: -2px;
        }
        @media (prefers-color-scheme: light) {
            .clock-container { color: #31333F; }
        }
    </style>
    <div class="clock-container" id="live-clock">⏰ 현재 시간: 로딩중...</div>
    <div class="refresh-container" id="last-refresh">🔄 마지막 갱신: 로딩중...</div>
    <script>
        var initTime = new Date().toLocaleTimeString('ko-KR', { hour12: false });
        document.getElementById('last-refresh').innerHTML = '🔄 마지막 갱신: ' + initTime;
        try { window.parent._lastRefreshTime = initTime; } catch(e) {}

        function updateClock() {
            var now = new Date();
            var timeStr = now.toLocaleTimeString('ko-KR', { hour12: false });
            document.getElementById('live-clock').innerHTML = '⏰ 현재 시간: ' + timeStr;
            try {
                var refreshTime = window.parent._lastRefreshTime;
                if (refreshTime) {
                    document.getElementById('last-refresh').innerHTML = '🔄 마지막 갱신: ' + refreshTime;
                }
            } catch(e) {}
        }
        setInterval(updateClock, 1000);
        updateClock();
    </script>
    """
    st.components.v1.html(clock_html, height=55)
    st.markdown("---")

st.sidebar.header("⚙️ 차트 설정")

default_kr_tickers = st.query_params.get("kr_tickers", "005930.KS, 000660.KS")
default_us_tickers = st.query_params.get("us_tickers", "TSLA, INTC, NVDA, AAPL, GOOGL")

kr_tickers_input = st.sidebar.text_input("🇰🇷 한국 주식 심볼 (쉼표 구분)", value=default_kr_tickers)
st.query_params["kr_tickers"] = kr_tickers_input

us_tickers_input = st.sidebar.text_input("🇺🇸 미국 주식 심볼 (쉼표 구분)", value=default_us_tickers)
st.query_params["us_tickers"] = us_tickers_input

kr_tickers = [t.strip().upper() for t in kr_tickers_input.split(",") if t.strip()]
us_tickers = [t.strip().upper() for t in us_tickers_input.split(",") if t.strip()]
all_tickers = kr_tickers + us_tickers

period_options = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "max"]
saved_period = st.query_params.get("period", "1d")
period_idx = period_options.index(saved_period) if saved_period in period_options else 0
period_help_text = """
**💡 투자 성향별 추천 기간**
- **단기/단타:** `1d` 또는 `5d`
- **스윙 (며칠~몇주):** `1mo`
- **중장기 추세 확인:** `6mo` 또는 `1y`
"""
period = st.sidebar.selectbox("조회 기간", period_options, index=period_idx, help=period_help_text)
st.query_params["period"] = period

interval_options = ["1m", "5m", "15m", "30m", "60m", "1d"]
saved_interval = st.query_params.get("interval", "5m")
interval_idx = interval_options.index(saved_interval) if saved_interval in interval_options else 1
interval_help_text = """
**💡 투자 성향별 추천 캔들**
- **단기/단타:** `5m` (가장 민감하고 정확도 높음)
- **스윙 (며칠~몇주):** `30m` 또는 `60m` (잔파도를 걸러줌)
- **중장기 추세 확인:** `1d`
"""
interval = st.sidebar.selectbox("차트 캔들 간격", interval_options, index=interval_idx, help=interval_help_text)
st.query_params["interval"] = interval

def get_bool_param(key, default_val):
    val = st.query_params.get(key, str(default_val))
    return val == "True"

show_prediction = st.sidebar.checkbox("🔮 복합 모멘텀 AI 예측선 (신뢰구간)", value=get_bool_param("show_pred", True))
st.query_params["show_pred"] = str(show_prediction)

show_ma = st.sidebar.checkbox("📊 이동평균선(5,20,60) 표시", value=get_bool_param("show_ma", True))
st.query_params["show_ma"] = str(show_ma)

show_macd = st.sidebar.checkbox("📉 MACD 지표 표시", value=get_bool_param("show_macd", True))
st.query_params["show_macd"] = str(show_macd)

show_news = st.sidebar.checkbox("📰 실시간 종목 뉴스 표시", value=get_bool_param("show_news", True))
st.query_params["show_news"] = str(show_news)

show_prepost = st.sidebar.checkbox("🌙 미국 시간외 거래(프리/애프터) 표시", value=get_bool_param("show_prepost", False))
st.query_params["show_prepost"] = str(show_prepost)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 목표가 / 손절가 자동 계산기")
target_pct = st.sidebar.number_input("익절 목표 수익률 (%)", value=5.0, step=0.5)
stop_loss_pct = st.sidebar.number_input("손절 라인 (%)", value=3.0, step=0.5)

st.sidebar.markdown("---")
st.sidebar.subheader("⏱️ 자동 새로고침 설정")
refresh_sec = st.sidebar.number_input("자동 새로고침 간격(초)", min_value=10, max_value=600, value=60, step=10)

if st.sidebar.button("🔄 즉시 전체 새로고침"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    **📌 한국 주식 심볼 입력 방법**
    - **코스피(KOSPI):** 종목코드 뒤에 `.KS`
    - **코스닥(KOSDAQ):** 종목코드 뒤에 `.KQ`
    """
)


def render_charts(ticker_list, title, is_us_market=False):
    if not ticker_list:
        st.info(f"{title}에 해당하는 종목이 없습니다.")
        return
        
    if len(ticker_list) > 1:
        tabs = st.tabs(ticker_list)
    else:
        tabs = [st.container()]
    
    for idx, ticker in enumerate(ticker_list):
        with tabs[idx]:
            try:
                use_prepost = is_us_market and show_prepost
                df = get_history_data(ticker, period, interval, prepost=use_prepost).copy()
                if df.empty:
                    st.warning(f"[{ticker}] 데이터를 불러올 수 없습니다.")
                    continue
                    
                try:
                    if df.index.tz is None:
                        df.index = df.index.tz_localize('UTC').tz_convert('Asia/Seoul')
                    else:
                        df.index = df.index.tz_convert('Asia/Seoul')
                except:
                    pass

                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).fillna(0)
                loss = (-delta.where(delta < 0, 0)).fillna(0)
                avg_gain = gain.ewm(com=13, adjust=False).mean()
                avg_loss = loss.ewm(com=13, adjust=False).mean()
                rs = avg_gain / avg_loss
                df['RSI'] = 100 - (100 / (1 + rs))
                
                # --- 기술적 지표 4종 추가 (RSI, BB, Stoch, OBV) ---
                # 1. Bollinger Bands (20일 이동평균, 2배수 표준편차)
                df['MA20'] = df['Close'].rolling(window=20).mean()
                df['BB_std'] = df['Close'].rolling(window=20).std()
                df['BB_upper'] = df['MA20'] + (df['BB_std'] * 2)
                df['BB_lower'] = df['MA20'] - (df['BB_std'] * 2)
                
                # 2. Stochastic Oscillator (Fast %K, Slow %D)
                low_min = df['Low'].rolling(window=14).min()
                high_max = df['High'].rolling(window=14).max()
                df['Stoch_K'] = 100 * ((df['Close'] - low_min) / (high_max - low_min))
                df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()
                
                # 3. OBV (On Balance Volume)
                df['OBV'] = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()
                
                current_rsi = df['RSI'].iloc[-1]
                lookback = min(len(df), 20)
                pct_slope = 0.0
                prediction_comment = ""
                miss_warning = ""
                future_times = []
                future_y = []
                future_y_upper = []
                future_y_lower = []
                t_label = ""
                
                if lookback >= 5:
                    y_vals = df['Close'].iloc[-lookback:].values
                    x_vals = np.arange(len(y_vals))
                    raw_slope, _ = np.polyfit(x_vals, y_vals, 1)
                    
                    # --- 4개 지표 종합 예측 스코어 산출 ---
                    score = 0.0
                    
                    # 1. RSI Score
                    if not pd.isna(current_rsi):
                        if current_rsi < 30: score += 1.0
                        elif current_rsi > 70: score -= 1.0
                        else: score += (50 - current_rsi) / 50.0

                    # 2. BB Score
                    curr_close = df['Close'].iloc[-1]
                    upper_bb = df['BB_upper'].iloc[-1] if not pd.isna(df['BB_upper'].iloc[-1]) else curr_close * 1.05
                    lower_bb = df['BB_lower'].iloc[-1] if not pd.isna(df['BB_lower'].iloc[-1]) else curr_close * 0.95
                    if curr_close < lower_bb: score += 1.5
                    elif curr_close > upper_bb: score -= 1.5
                    elif upper_bb != lower_bb:
                        pos = (curr_close - lower_bb) / (upper_bb - lower_bb)
                        score += (0.5 - pos) * 2.0

                    # 3. Stoch Score
                    k = df['Stoch_K'].iloc[-1]
                    d = df['Stoch_D'].iloc[-1]
                    if not pd.isna(k) and not pd.isna(d):
                        if k < 20 and k > d: score += 1.0
                        elif k > 80 and k < d: score -= 1.0
                        else: score += (50 - k) / 50.0

                    # 4. OBV Score
                    if len(df) >= 5:
                        obv_slope, _ = np.polyfit(np.arange(5), df['OBV'].iloc[-5:].values, 1)
                        if obv_slope > 0: score += 0.5
                        else: score -= 0.5

                    normalized_score = max(-1.0, min(1.0, score / 4.0))
                    
                    # 최종 기울기 도출: 과거 추세(raw_slope)에 현재 모멘텀(normalized_score) 반영
                    adjusted_slope = raw_slope * 0.2 + (y_vals[-1] * 0.0005 * normalized_score)
                    pct_slope = (adjusted_slope / y_vals[-1]) * 100
                    
                    if show_prediction:
                        last_time = df.index[-1]
                        time_diff = df.index[-1] - df.index[-2] if len(df) >= 2 else timedelta(minutes=5)
                        if time_diff.total_seconds() <= 0: time_diff = timedelta(minutes=5)
                        
                        t_hour = 17 if is_us_market else 15
                        t_minute = 0 if is_us_market else 30
                        t_label = "종합 지표 예측"
                            
                        target_time = last_time.replace(hour=t_hour, minute=t_minute, second=0, microsecond=0)
                        if target_time <= last_time: target_time += timedelta(days=1)
                            
                        steps = int((target_time - last_time) / time_diff)
                        steps = max(5, min(steps, 200)) 
                        
                        future_times = [last_time] + [last_time + time_diff * i for i in range(1, steps + 1)]
                        future_y = [y_vals[-1]] + [adjusted_slope * i + y_vals[-1] for i in range(1, steps + 1)]
                        
                        # 신뢰구간 (상/하단 밴드) 계산
                        bb_std_last = df['BB_std'].iloc[-1] if not pd.isna(df['BB_std'].iloc[-1]) else (y_vals[-1] * 0.01)
                        std_dev_growth = np.linspace(bb_std_last * 0.5, bb_std_last * 1.5, len(future_y))
                        future_y_upper = [y + std for y, std in zip(future_y, std_dev_growth)]
                        future_y_lower = [y - std for y, std in zip(future_y, std_dev_growth)]
                        
                        trend_dir = "횡보"
                        if pct_slope > 0.01:
                            trend_dir = "상승"
                            prediction_comment = f"📈 **종합 추세:** 모멘텀 기반 상승 예측 (점수: {normalized_score:+.2f})"
                        elif pct_slope < -0.01:
                            trend_dir = "하락"
                            prediction_comment = f"📉 **종합 추세:** 모멘텀 기반 하락 예측 (점수: {normalized_score:+.2f})"
                        else:
                            prediction_comment = f"➖ **종합 추세:** 박스권 횡보 예측 (점수: {normalized_score:+.2f})"
                        
                        if len(df) >= 3:
                            recent_change = (df['Close'].iloc[-1] - df['Close'].iloc[-3]) / df['Close'].iloc[-3] * 100
                            if trend_dir == "상승" and recent_change < -0.3:
                                miss_warning = f"🚨 **단기 급락 감지!** 호가창 확인 요망"
                                prediction_comment = "" 
                            elif trend_dir == "하락" and recent_change > 0.3:
                                miss_warning = f"🚨 **단기 급등 감지!** 호가창 확인 요망"
                                prediction_comment = "" 

                rec_badge = "⚪ 분석 대기중"
                rsi_comment = ""
                
                if not pd.isna(current_rsi):
                    rsi_score = 100 - current_rsi
                    trend_bonus = pct_slope * 500
                    buy_score = max(0, min(100, rsi_score + trend_bonus))
                    
                    if buy_score >= 70:
                        rec_badge = f"🟢 강력 매수 ({buy_score:.1f}%)"
                        rsi_comment = "과매도 구간 / 상승 모멘텀 강함."
                    elif buy_score <= 30:
                        rec_badge = f"🔴 매도 주의 ({buy_score:.1f}%)"
                        rsi_comment = "단기 과매수 / 하락 압력 강함."
                    elif buy_score >= 55:
                        rec_badge = f"↗️ 매수 / 보유 ({buy_score:.1f}%)"
                        rsi_comment = "안정적인 상승세입니다."
                    elif buy_score <= 45:
                        rec_badge = f"↘️ 관망 / 축소 ({buy_score:.1f}%)"
                        rsi_comment = "매도세가 다소 우세합니다."
                    else:
                        rec_badge = f"⚪ 중립 ({buy_score:.1f}%)"
                        rsi_comment = "수급이 팽팽한 횡보 구간."

                kor_name = get_kor_name(ticker)
                display_title = f"📊 {ticker} ({kor_name}) | {rec_badge}" if kor_name else f"📊 {ticker} | {rec_badge}"

                daily_df = get_daily_data(ticker)
                prev_close_usd_or_krw = None
                if not daily_df.empty and len(daily_df) >= 2:
                    prev_close_usd_or_krw = daily_df['Close'].iloc[-2]
                else:
                    try:
                        prev_close_usd_or_krw = yf.Ticker(ticker).fast_info.get('previousClose', None)
                    except:
                        pass
                
                if is_us_market:
                    df['Open'] = df['Open'] * usd_to_krw
                    df['High'] = df['High'] * usd_to_krw
                    df['Low'] = df['Low'] * usd_to_krw
                    df['Close'] = df['Close'] * usd_to_krw
                    prev_krw = prev_close_usd_or_krw * usd_to_krw if prev_close_usd_or_krw else None
                    if future_y:
                        future_y = [y * usd_to_krw for y in future_y]
                        future_y_upper = [y * usd_to_krw for y in future_y_upper]
                        future_y_lower = [y * usd_to_krw for y in future_y_lower]
                else:
                    prev_krw = prev_close_usd_or_krw

                curr_krw = df['Close'].iloc[-1]

                # --- 지표별 대시보드 상태 패널 ---
                bb_status = "중립"
                if curr_close < lower_bb: bb_status = "매수"
                elif curr_close > upper_bb: bb_status = "매도"

                stoch_status = "중립"
                if not pd.isna(k) and not pd.isna(d):
                    if k < 20 and k > d: stoch_status = "매수"
                    elif k > 80 and k < d: stoch_status = "매도"

                obv_status = "중립"
                if len(df) >= 5:
                    if obv_slope > 0: obv_status = "매수 우위"
                    else: obv_status = "매도 우위"
                
                gauge_fig = go.Figure(go.Indicator(
                    mode="gauge",
                    value=normalized_score,
                    title={'text': "AI 모멘텀 스코어", 'font': {'size': 14}},
                    gauge={
                        'axis': {'range': [-1, 1], 'tickwidth': 1},
                        'bar': {'color': "purple"},
                        'steps': [
                            {'range': [-1, -0.3], 'color': "rgba(255,0,0,0.2)"},
                            {'range': [-0.3, 0.3], 'color': "rgba(200,200,200,0.2)"},
                            {'range': [0.3, 1], 'color': "rgba(0,255,0,0.2)"}],
                    }
                ))
                gauge_fig.add_annotation(
                    x=0.5, y=0.15,
                    text=f"{normalized_score:+.2f}",
                    font=dict(size=26),
                    showarrow=False
                )
                gauge_fig.update_layout(height=200, margin=dict(l=15, r=15, t=50, b=10))

                st.markdown("---")
                dash_cols = st.columns([1.5, 1, 1, 1, 1])
                import random
                with dash_cols[0]:
                    st.plotly_chart(gauge_fig, use_container_width=True, key=f"gauge_{ticker}_{idx}_{random.random()}")
                with dash_cols[1]:
                    rsi_help = "RSI(상대강도지수)는 현재 주가의 과열/침체 상태를 나타냅니다.\n- 30 미만 (매수): 과매도 상태로 반등 가능성이 높습니다.\n- 70 초과 (매도): 과매수 상태로 하락 가능성이 높습니다."
                    st.metric("RSI 상태", f"{current_rsi:.1f}", "매수" if current_rsi < 30 else "매도" if current_rsi > 70 else "중립", help=rsi_help)
                with dash_cols[2]:
                    bb_help = "볼린저 밴드는 주가의 변동성 범위를 나타냅니다.\n- 하단 이탈 (매수): 주가가 밴드 하단선보다 낮아져 반등 가능성이 있습니다.\n- 상단 이탈 (매도): 주가가 밴드 상단선보다 높아져 하락 가능성이 있습니다."
                    st.metric("볼린저 밴드", bb_status, "이탈" if bb_status != "중립" else "안정", help=bb_help)
                with dash_cols[3]:
                    stoch_help = "스토캐스틱은 최근 가격 변동폭 내에서 현재 주가의 위치를 나타냅니다.\n- 20 이하 크로스 (매수): 침체 구간에서 상승 전환 신호입니다.\n- 80 이상 크로스 (매도): 과열 구간에서 하락 전환 신호입니다."
                    st.metric("스토캐스틱", stoch_status, "크로스" if stoch_status != "중립" else "", help=stoch_help)
                with dash_cols[4]:
                    obv_help = "OBV는 거래량을 누적하여 세력의 매집/분산을 예측하는 지표입니다.\n- 매수 우위: 매수 거래량이 매도 거래량보다 많은 상승 추세입니다.\n- 매도 우위: 매도 거래량이 매수 거래량보다 많은 하락 추세입니다."
                    st.metric("OBV 추세", obv_status, "상승" if obv_status == "매수 우위" else "하락" if obv_status == "매도 우위" else "", help=obv_help)
                st.markdown("---")

                col_title, col_price, col_input = st.columns([2.5, 1, 1])
                
                with col_title:
                    st.markdown(f"#### {display_title}")
                    if miss_warning:
                        st.warning(miss_warning + " | " + rsi_comment if rsi_comment else miss_warning)
                    
                    if normalized_score >= 0.5:
                        comments = [
                            "🚀 가즈아아아!! 영끌해서 사세요!!",
                            "🔥 상승 에너지 폭발! 지금 안 사면 벼락거지 됩니다!",
                            "💸 돈 복사가 시작됩니다. 풀매수 타이밍!",
                            "🏎️ 페라리 매장 구경가셔도 좋습니다. 강력 매수!"
                        ]
                        action_comment = random.choice(comments)
                        status_icon = "🟢"
                    elif normalized_score >= 0.1:
                        comments = [
                            "👍 따뜻한 훈풍이 붑니다. 분할 매수로 탑승하세요.",
                            "🛒 장바구니에 살포시 담아볼 만한 자리입니다.",
                            "📈 차트가 예뻐지고 있네요. 조금씩 사 모으세요!",
                            "🌱 싹이 트고 있습니다. 긍정적으로 매수 접근!"
                        ]
                        action_comment = random.choice(comments)
                        status_icon = "🟢"
                    elif normalized_score > -0.1:
                        comments = [
                            "👀 치열한 눈치싸움 중... 팝콘이나 챙기세요.",
                            "⚖️ 수급이 팽팽합니다. 일단 커피 한잔하며 관망!",
                            "🧘 마음의 평화를 유지하며 천천히 지켜보세요.",
                            "🐢 횡보의 늪입니다. 섣부른 진입은 자제하세요."
                        ]
                        action_comment = random.choice(comments)
                        status_icon = "⚪"
                    elif normalized_score > -0.5:
                        comments = [
                            "🌧️ 하늘에 먹구름이 낍니다. 비중을 살짝 줄이세요.",
                            "📉 소나기는 피하는 게 상책! 부분 매도로 현금 확보!",
                            "⚠️ 분위기가 쎄합니다. 방어적으로 대응하세요.",
                            "🥶 찬바람이 붑니다. 조금 팔아두는 것도 좋겠네요."
                        ]
                        action_comment = random.choice(comments)
                        status_icon = "🔴"
                    else:
                        comments = [
                            "🚨 한강물 온도가 차갑습니다. 껴입으시고 당장 파세요!!",
                            "📉 지하실 밑에 멘틀이 있습니다. 즉시 대피하세요!!",
                            "🧨 폭탄 돌리기가 터졌습니다!! 뒤도 돌아보지 말고 매도!!",
                            "☠️ 생명연장의 꿈을 위해 빤스런 하세요! 강력 매도!"
                        ]
                        action_comment = random.choice(comments)
                        status_icon = "🔴"

                    param_key = f"avg_{ticker}"
                    default_avg_price = float(st.query_params.get(param_key, 0.0))
                    
                    if default_avg_price > 0:
                        target_price = default_avg_price * (1 + target_pct / 100)
                        stop_price = default_avg_price * (1 - stop_loss_pct / 100)
                        unit_str = "$" if is_us_market else "원"
                        fmt = "{:,.2f}" if is_us_market else "{:,.0f}"
                        
                        target_msg = f"**{fmt.format(target_price)}{unit_str}** 도달 시 파세요!"
                        stop_msg = f"**{fmt.format(stop_price)}{unit_str}** 밑으로 떨어지면 손절!"
                        
                        st.info(f"{status_icon} **AI 매매 조언:** {action_comment}\n\n🎯 익절 목표 ({target_pct}%): {target_msg} | 🛡️ 손절 라인 ({stop_loss_pct}%): {stop_msg}")
                    else:
                        st.info(f"{status_icon} **AI 매매 조언:** {action_comment} \n\n(👉 우측 평단가를 입력하시면 정확한 익절/손절가를 알려드립니다!)")
                
                with col_price:
                    if prev_krw:
                        change_krw = curr_krw - prev_krw
                        change_pct = (change_krw / prev_krw) * 100
                        st.metric(
                            label="현재 주가 (원화 기준)", 
                            value=f"₩{curr_krw:,.0f}", 
                            delta=f"{change_krw:+,.0f}원 ({change_pct:+.2f}%)"
                        )
                    else:
                        st.metric(label="현재 주가 (원화 기준)", value=f"₩{curr_krw:,.0f}")
                
                with col_input:
                    step_val = 1.0 if is_us_market else 100.0
                    unit_str = "$" if is_us_market else "원"
                    param_key = f"avg_{ticker}"
                    default_avg_price = float(st.query_params.get(param_key, 0.0))
                    
                    input_price = st.number_input(
                        f"💰 평단가 ({unit_str})", 
                        value=default_avg_price, 
                        step=step_val, 
                        key=f"input_{ticker}"
                    )
                    if input_price > 0:
                        st.query_params[param_key] = input_price
                    elif param_key in st.query_params:
                        del st.query_params[param_key]

                rows_count = 4 if show_macd else 3
                row_heights = [0.45, 0.15, 0.15, 0.25] if show_macd else [0.6, 0.2, 0.2]
                chart_height = 580 if show_macd else 480 

                vol_colors = ['red' if close >= open_price else 'blue' for close, open_price in zip(df['Close'], df['Open'])]
                fig = make_subplots(
                    rows=rows_count, cols=1, 
                    shared_xaxes=True, 
                    vertical_spacing=0.04,
                    row_heights=row_heights
                )

                fig.add_trace(go.Candlestick(
                    x=df.index,
                    open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                    name=ticker, increasing_line_color='red', decreasing_line_color='blue'
                ), row=1, col=1)

                if show_prediction and lookback >= 5 and future_times:
                    # 1. Base (평균) 시나리오
                    fig.add_trace(go.Scatter(
                        x=future_times, y=future_y, mode='lines', name="기본 (Base)",
                        line=dict(color='purple', width=3, dash='dash')
                    ), row=1, col=1)
                    
                    # 2. Bull (낙관) 시나리오
                    fig.add_trace(go.Scatter(
                        x=future_times, y=future_y_upper, mode='lines', name='강세 (Bull)',
                        line=dict(color='green', width=2, dash='dot')
                    ), row=1, col=1)
                    
                    # 3. Bear (비관) 시나리오
                    fig.add_trace(go.Scatter(
                        x=future_times, y=future_y_lower, mode='lines', name='약세 (Bear)',
                        line=dict(color='red', width=2, dash='dot')
                    ), row=1, col=1)
                    
                    # 목표가 Annotation
                    last_f_time = future_times[-1]
                    fig.add_annotation(x=last_f_time, y=future_y[-1], text=f"Base: {future_y[-1]:,.0f}", showarrow=True, arrowhead=1, ax=40, ay=0, row=1, col=1, font=dict(color="purple"))
                    fig.add_annotation(x=last_f_time, y=future_y_upper[-1], text=f"Bull: {future_y_upper[-1]:,.0f}", showarrow=True, arrowhead=1, ax=40, ay=-15, row=1, col=1, font=dict(color="green"))
                    fig.add_annotation(x=last_f_time, y=future_y_lower[-1], text=f"Bear: {future_y_lower[-1]:,.0f}", showarrow=True, arrowhead=1, ax=40, ay=15, row=1, col=1, font=dict(color="red"))

                fig.add_trace(go.Bar(
                    x=df.index, y=df['Volume'], 
                    marker_color=vol_colors, name='거래량'
                ), row=2, col=1)

                fig.add_trace(go.Scatter(
                    x=df.index, y=df['RSI'], 
                    mode='lines', name='RSI', line=dict(color='purple', width=1.5)
                ), row=3, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="blue", row=3, col=1)

                if show_macd:
                    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
                    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
                    df['MACD'] = exp1 - exp2
                    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
                    df['MACD_Hist'] = df['MACD'] - df['Signal']
                    
                    macd_colors = ['red' if val >= 0 else 'blue' for val in df['MACD_Hist']]
                    
                    fig.add_trace(go.Bar(
                        x=df.index, y=df['MACD_Hist'], 
                        marker_color=macd_colors, name='MACD 히스토그램'
                    ), row=4, col=1)
                    
                    fig.add_trace(go.Scatter(
                        x=df.index, y=df['MACD'], 
                        mode='lines', name='MACD(12,26)', line=dict(color='orange', width=1.5)
                    ), row=4, col=1)
                    
                    fig.add_trace(go.Scatter(
                        x=df.index, y=df['Signal'], 
                        mode='lines', name='시그널(9)', line=dict(color='royalblue', width=1.5)
                    ), row=4, col=1)

                if prev_krw:
                    fig.add_hline(y=prev_krw, line_dash="dot", line_color="gray", row=1, col=1)
                    
                if len(df) > 0:
                    today_open_krw = df['Open'].iloc[0]
                    fig.add_hline(y=today_open_krw, line_dash="dashdot", line_color="orange", row=1, col=1)

                if input_price > 0:
                    display_avg_price = input_price * usd_to_krw if is_us_market else input_price
                    label_text = f"내 평단가: {input_price:,.2f}$" if is_us_market else f"내 평단가: {input_price:,.0f}원"
                    fig.add_hline(
                        y=display_avg_price, line_dash="solid", line_color="magenta", 
                        row=1, col=1, annotation_text=label_text, annotation_position="top left"
                    )

                if show_ma:
                    if len(df) >= 5:
                        df['MA5'] = df['Close'].rolling(window=5).mean()
                        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], mode='lines', name='5MA', line=dict(color='orange', width=1.5)), row=1, col=1)
                    if len(df) >= 20:
                        df['MA20'] = df['Close'].rolling(window=20).mean()
                        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], mode='lines', name='20MA', line=dict(color='green', width=1.5)), row=1, col=1)
                    if len(df) >= 60:
                        df['MA60'] = df['Close'].rolling(window=60).mean()
                        fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], mode='lines', name='60MA', line=dict(color='royalblue', width=1.5)), row=1, col=1)

                if not is_us_market and interval != "1d":
                    try:
                        target_close = df.index[-1].replace(hour=17, minute=0, second=0)
                        fig.add_trace(go.Scatter(x=[target_close], y=[df['Close'].iloc[-1]], mode='markers', marker=dict(color='rgba(0,0,0,0)'), showlegend=False, hoverinfo='none'), row=1, col=1)
                    except:
                        pass

                fig.update_layout(
                    template="plotly_white", xaxis_rangeslider_visible=False,
                    margin=dict(l=0, r=0, t=5, b=0), height=chart_height,
                    legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1)
                )
                
                # 🔥 캔들 데이터 기준으로 Y축 범위를 잡아서 상하 중앙 정렬
                if use_prepost:
                    # 시간외 거래 ON → 튀는 데이터 제거
                    y_min = df['Low'].quantile(0.02)
                    y_max = df['High'].quantile(0.98)
                else:
                    # 정규장만 → 그대로
                    y_min = df['Low'].min()
                    y_max = df['High'].max()   
                
                # NaN 및 분산 0 예외 처리 (프론트엔드 크래시 방지)
                if pd.isna(y_min) or pd.isna(y_max):
                    y_min = df['Close'].min()
                    y_max = df['Close'].max()
                if pd.isna(y_min) or pd.isna(y_max):
                    y_min, y_max = 0, 1
                    
                y_padding = (y_max - y_min) * 0.5
                if y_padding == 0:
                    y_padding = y_min * 0.01 if y_min > 0 else 1.0
                    
                fig.update_yaxes(
                    title_text="가격", tickformat="₩,",
                    range=[y_min - y_padding, y_max + y_padding],
                    row=1, col=1
                )
                fig.update_yaxes(title_text="거래량", row=2, col=1)
                fig.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1)
                
                if show_macd:
                    fig.update_yaxes(title_text="MACD", row=4, col=1)
                    fig.update_xaxes(rangeslider=dict(visible=False), row=4, col=1)
                    
                fig.update_xaxes(rangeslider=dict(visible=False), row=1, col=1)
                fig.update_xaxes(rangeslider=dict(visible=False), row=2, col=1)
                fig.update_xaxes(rangeslider=dict(visible=False), row=3, col=1)
                
                import random
                st.plotly_chart(fig, use_container_width=True, key=f"main_{ticker}_{idx}_{random.random()}")

                if show_news:
                    with st.expander(f"📰 [{ticker}] 실시간 핵심 뉴스"):
                        try:
                            query = kor_name if kor_name else ticker
                            encoded_query = urllib.parse.quote(query)
                            rss_url = f"https://news.google.com/rss/search?q={encoded_query}+when:1d&hl=ko&gl=KR&ceid=KR:ko"
                            req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
                            
                            with urllib.request.urlopen(req) as response:
                                xml_data = response.read()
                                
                            root = ET.fromstring(xml_data)
                            items = root.findall('.//item')
                            
                            if items:
                                seen_titles = set()
                                display_count = 0
                                for item in items:
                                    title_elem = item.find('title')
                                    link_elem = item.find('link')
                                    pub_date_elem = item.find('pubDate')
                                    
                                    if title_elem is not None and link_elem is not None:
                                        title = title_elem.text
                                        if title not in seen_titles:
                                            seen_titles.add(title)
                                            link = link_elem.text
                                            pub_date = pub_date_elem.text if pub_date_elem is not None else ""
                                            
                                            if pub_date:
                                                try:
                                                    dt = parsedate_to_datetime(pub_date)
                                                    kst_timezone = timezone(timedelta(hours=9))
                                                    dt_kst = dt.astimezone(kst_timezone)
                                                    pub_date = dt_kst.strftime('%m-%d %H:%M')
                                                except:
                                                    pass

                                            date_str = f" ({pub_date})" if pub_date else ""
                                            st.markdown(f"- [{title}]({link}){date_str}")
                                            display_count += 1
                                            
                                    if display_count >= 3: 
                                        break
                                        
                                if display_count == 0: 
                                    st.write("최근 뉴스가 없습니다.")
                            else:
                                st.write("최근 뉴스가 없습니다.")
                        except:
                            st.write("뉴스 로딩 오류")

            except Exception as e:
                st.error(f"[{ticker}] 차트 오류: {e}")


@st.fragment(run_every=int(refresh_sec))
def render_dynamic_dashboard():

    force_run_key = datetime.now().timestamp()
    updater_html = f"""
    <script>
        /* {force_run_key} */
        try {{
            window.parent._lastRefreshTime = new Date().toLocaleTimeString('ko-KR', {{hour12: false}});
        }} catch(e) {{}}
    </script>
    """
    st.components.v1.html(updater_html, height=0)

    js_code = """
    <script>
    setTimeout(function() {
        var expanders = window.parent.document.querySelectorAll('[data-testid="stExpander"]');
        for (var i = 0; i < expanders.length; i++) {
            if (expanders[i].innerText.includes("주요 시장 지수")) {
                expanders[i].style.position = 'absolute';
                expanders[i].style.top = '0.3rem';
                expanders[i].style.left = '3.5rem';
                expanders[i].style.width = 'calc(100% - 4.5rem)';
                expanders[i].style.zIndex = '999999';
                
                var details = expanders[i].querySelector('details');
                if (details) {
                    details.style.backgroundColor = '#1E1E1E';
                    details.style.border = '1px solid #444';
                    details.style.borderRadius = '8px';
                    details.style.boxShadow = '0 4px 12px rgba(0,0,0,0.4)';
                    details.style.margin = '0';
                }
            }
        }
    }, 100);
    </script>
    """
    st.components.v1.html(js_code, height=0)

    with st.expander("🌐 주요 시장 지수 및 환율 열어보기"):
        index_symbols = {"코스피": "^KS11", "코스닥": "^KQ11", "S&P 500": "^GSPC", "나스닥": "^IXIC"}
        
        idx_cols = st.columns(5)
        for i, (name, symbol) in enumerate(index_symbols.items()):
            try:
                idx_df = get_daily_data(symbol) 
                idx_df = idx_df.dropna(subset=['Close'])
                if len(idx_df) >= 2:
                    curr_idx = idx_df['Close'].iloc[-1]
                    prev_idx = idx_df['Close'].iloc[-2]
                    idx_change = curr_idx - prev_idx
                    idx_pct = (idx_change / prev_idx) * 100
                    idx_cols[i].metric(label=name, value=f"{curr_idx:,.2f}", delta=f"{idx_change:+.2f} ({idx_pct:+.2f}%)")
                else:
                    idx_cols[i].metric(label=name, value="데이터 없음")
            except:
                idx_cols[i].metric(label=name, value="오류")
                
        idx_cols[4].metric(label="원/달러 환율", value=f"₩{usd_to_krw:,.2f}", help=f"환율 업데이트 기준: {usd_to_krw_time}")
    
    if not all_tickers:
        st.info("사이드바에서 조회할 종목 심볼을 최소 1개 이상 입력해 주세요.")
    else:
        market_choice = st.radio(
            "🌍 시장을 선택하세요", 
            ["🇰🇷 한국 주식", "🇺🇸 미국 주식"], 
            horizontal=True,
            label_visibility="collapsed"
        )
        
        if market_choice == "🇰🇷 한국 주식":
            render_charts(kr_tickers, "🇰🇷 한국 주식", is_us_market=False)
        else:
            render_charts(us_tickers, "🇺🇸 미국 주식", is_us_market=True)

render_dynamic_dashboard()