import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import timedelta, datetime, timezone
from email.utils import parsedate_to_datetime
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

# 1. 페이지 기본 설정 및 여백 최소화
st.set_page_config(page_title="실시간 주식 차트 대시보드 Ver 3.6", layout="wide")

st.markdown("""
    <style>
        /* 메인 화면 상하단 여백 최소화 */
        .block-container {
            padding-top: 3rem !important; 
            padding-bottom: 0rem !important;
        }
        
        /* 🔥 첫 번째 Expander(시장 지수)를 뜯어내서 사이드바 버튼(>) 옆으로 강제 이동 */
        [data-testid="stMain"] div[data-testid="stExpander"]:first-of-type {
            position: absolute !important;
            top: 0.3rem !important;      
            left: 3.5rem !important;     
            width: calc(100% - 4.5rem) !important; 
            z-index: 999999 !important;  
        }
        
        /* 띄워진 지수 박스가 열렸을 때 배경색 불투명 처리 */
        [data-testid="stMain"] div[data-testid="stExpander"]:first-of-type details {
            background-color: var(--background-color, #1E1E1E) !important;
            border: 1px solid var(--secondary-background-color, #444) !important;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
            margin: 0 !important;
        }
        
        /* 메뉴 및 Deploy 버튼 숨김 */
        #MainMenu { visibility: hidden; }
        .stDeployButton { display: none; }
        [data-testid="stAppDeployButton"] { display: none !important; }
        
        /* 사이드바 내부 상단 여백 축소 */
        [data-testid="stSidebarUserContent"] {
            padding-top: 1rem !important;
        }
        
        /* 라디오 버튼(시장 선택) 상하 여백 완벽 밀착 */
        div.row-widget.stRadio > div {
            margin-top: -10px;
            margin-bottom: -20px;
        }
        
        /* 탭 상단/하단 여백 밀착 및 내부 숨은 여백 날리기 */
        .stTabs {
            margin-top: -15px;
        }
        .stTabs [data-baseweb="tab-list"] {
            margin-bottom: -10px;
        }
        [data-baseweb="tab-panel"] {
            padding-top: 0rem !important;
        }
        
        /* AI 코멘트 박스(info, warning) 압축 */
        .stAlert {
            padding-top: 0.2rem !important;
            padding-bottom: 0.2rem !important;
            margin-top: 5px !important;
            margin-bottom: 0px !important;
        }
        
        /* 종목명 (####) 하단 여백 축소 */
        h4 {
            padding-bottom: 0px !important;
            margin-bottom: 0px !important;
        }
        
        /* 메트릭(현재가) 텍스트 크기 및 간격 조정 */
        [data-testid="stMetricValue"] {
            font-size: 1.5rem;
        }
    </style>
""", unsafe_allow_html=True)


# --- 데이터 스마트 캐싱 (버벅임 방지) ---

@st.cache_data(ttl=3600)
def get_usd_krw_rate():
    try:
        ex_rate_info = yf.Ticker("USDKRW=X").history(period="1d")
        return ex_rate_info['Close'].iloc[-1]
    except:
        return 1350.0 

usd_to_krw = get_usd_krw_rate()

@st.cache_data(ttl=10)
def get_history_data(ticker, period, interval):
    try:
        return yf.Ticker(ticker).history(period=period, interval=interval)
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


# 2. 사이드바 영역 구성
with st.sidebar:
    st.markdown("### 📈 주식 차트 대시보드 V3.6")
    
    with st.expander("✨ V3.6 패치 내용 보기"):
        st.markdown(
            """
            - **레이아웃 혁신:** 제목/현재가/평단가를 1줄로 통합!
            - **상단바 편입:** 시장 지수 패널을 상단 헤더로 이동시켜 스크롤 박멸
            - **시간 완벽 동기화:** 갱신 시간을 서버가 아닌 사용자 접속 기기(스마트폰/PC) 시간과 100% 일치
            """
        )

    # 🔥 서버 시계 오차를 무시하고 무조건 '접속한 사람 기기' 시간으로 강제 동기화하기 위한 난수키
    force_remount_key = datetime.now().timestamp()
    
    clock_html = """
    <style>
        @media (prefers-color-scheme: dark) {
            .clock-container { color: #E0E0E0; }
        }
        @media (prefers-color-scheme: light) {
            .clock-container { color: #31333F; }
        }
        .clock-container {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            font-size: 16px; 
            font-weight: bold; 
            text-align: center; 
            padding: 5px;
            margin-top: 5px;
        }
        .refresh-container {
            text-align: center; 
            color: gray; 
            font-size: 14px; 
            margin-top: -5px;
        }
    </style>
    <div class="clock-container" id="live-clock">⏰ 현재 시간: 로딩중...</div>
    <div class="refresh-container" id="last-refresh">🔄 마지막 갱신: 로딩중...</div>
    <script>
        /* 파이썬이 새로고침될 때마다 HTML 영역을 강제로 다시 그리게 만드는 난수: """ + str(force_remount_key) + """ */
        
        // 1. 화면이 갱신되는 바로 그 순간의 '접속자 기기(PC/폰) 시계'를 읽어와서 고정
        const loadTime = new Date();
        const refreshStr = loadTime.toLocaleTimeString('ko-KR', { hour12: false });
        document.getElementById('last-refresh').innerHTML = '🔄 마지막 갱신: ' + refreshStr;

        // 2. 1초마다 째깍거리는 현재 시간 시계
        function updateClock() {
            const now = new Date();
            const timeStr = now.toLocaleTimeString('ko-KR', { hour12: false });
            document.getElementById('live-clock').innerHTML = '⏰ 현재 시간: ' + timeStr;
        }
        setInterval(updateClock, 1000);
        updateClock();
    </script>
    """
    st.components.v1.html(clock_html, height=60)
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
period = st.sidebar.selectbox("조회 기간", period_options, index=period_idx)
st.query_params["period"] = period

interval_options = ["1m", "5m", "15m", "30m", "60m", "1d"]
saved_interval = st.query_params.get("interval", "5m")
interval_idx = interval_options.index(saved_interval) if saved_interval in interval_options else 1
interval = st.sidebar.selectbox("차트 캔들 간격", interval_options, index=interval_idx)
st.query_params["interval"] = interval

def get_bool_param(key, default_val):
    val = st.query_params.get(key, str(default_val))
    return val == "True"

show_prediction = st.sidebar.checkbox("🔮 AI 추세 예측선 표시", value=get_bool_param("show_pred", True))
st.query_params["show_pred"] = str(show_prediction)

show_ma = st.sidebar.checkbox("📊 이동평균선(5,20,60) 표시", value=get_bool_param("show_ma", True))
st.query_params["show_ma"] = str(show_ma)

show_macd = st.sidebar.checkbox("📉 MACD 지표 표시", value=get_bool_param("show_macd", True))
st.query_params["show_macd"] = str(show_macd)

show_news = st.sidebar.checkbox("📰 실시간 종목 뉴스 표시", value=get_bool_param("show_news", True))
st.query_params["show_news"] = str(show_news)

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


# --- 차트 렌더링 함수 ---
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
                df = get_history_data(ticker, period, interval).copy()
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
                
                # --- AI 추세선 및 코멘트 사전 계산 ---
                current_rsi = df['RSI'].iloc[-1]
                lookback = min(len(df), 20)
                pct_slope = 0.0
                prediction_comment = ""
                miss_warning = ""
                future_times = []
                future_y = []
                t_label = ""
                
                if lookback >= 5:
                    y_vals = df['Close'].iloc[-lookback:].values
                    x_vals = np.arange(len(y_vals))
                    raw_slope, _ = np.polyfit(x_vals, y_vals, 1)
                    damped_slope = raw_slope * 0.25 
                    pct_slope = (damped_slope / y_vals[-1]) * 100
                    
                    if show_prediction:
                        last_time = df.index[-1]
                        time_diff = df.index[-1] - df.index[-2] if len(df) >= 2 else timedelta(minutes=5)
                        if time_diff.total_seconds() <= 0: time_diff = timedelta(minutes=5)
                        
                        t_hour = 17 if is_us_market else 15
                        t_minute = 0 if is_us_market else 30
                        t_label = "17시 예측" if is_us_market else "15:30 예측"
                            
                        target_time = last_time.replace(hour=t_hour, minute=t_minute, second=0, microsecond=0)
                        if target_time <= last_time: target_time += timedelta(days=1)
                            
                        steps = int((target_time - last_time) / time_diff)
                        steps = max(5, min(steps, 200)) 
                        
                        future_times = [last_time] + [last_time + time_diff * i for i in range(1, steps + 1)]
                        future_y = [y_vals[-1]] + [damped_slope * i + y_vals[-1] for i in range(1, steps + 1)]
                        
                        trend_dir = "횡보"
                        if pct_slope > 0.02:
                            trend_dir = "상승"
                            prediction_comment = f"📈 **단기 추세:** 우상향 예측"
                        elif pct_slope < -0.02:
                            trend_dir = "하락"
                            prediction_comment = f"📉 **단기 추세:** 하락세 예측"
                        else:
                            prediction_comment = f"➖ **단기 추세:** 박스권 횡보 예측"
                        
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
                else:
                    prev_krw = prev_close_usd_or_krw

                curr_krw = df['Close'].iloc[-1]

                # 🌟 상단 1줄 가로 배치
                col_title, col_price, col_input = st.columns([2.5, 1, 1])
                
                with col_title:
                    st.markdown(f"#### {display_title}")
                    final_comment = ""
                    if miss_warning:
                        final_comment = miss_warning + " | " + rsi_comment if rsi_comment else miss_warning
                        st.warning(final_comment)
                    elif prediction_comment:
                        final_comment = prediction_comment + " | " + rsi_comment if rsi_comment else prediction_comment
                        st.info(final_comment)
                
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

                # 🔥 차트 높이 미세 조정 (스크롤 방지용 580px 유지)
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
                    fig.add_trace(go.Scatter(
                        x=future_times, y=future_y, mode='lines', name=t_label,
                        line=dict(color='purple', width=2, dash='dash')
                    ), row=1, col=1)

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

                fig.update_layout(
                    template="plotly_white", xaxis_rangeslider_visible=False,
                    margin=dict(l=0, r=0, t=5, b=0), height=chart_height,
                    legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1)
                )
                
                fig.update_yaxes(title_text="가격", tickformat="₩,", row=1, col=1)
                fig.update_yaxes(title_text="거래량", row=2, col=1)
                fig.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1)
                
                if show_macd:
                    fig.update_yaxes(title_text="MACD", row=4, col=1)
                    fig.update_xaxes(rangeslider=dict(visible=False), row=4, col=1)
                    
                fig.update_xaxes(rangeslider=dict(visible=False), row=1, col=1)
                fig.update_xaxes(rangeslider=dict(visible=False), row=2, col=1)
                fig.update_xaxes(rangeslider=dict(visible=False), row=3, col=1)
                
                st.plotly_chart(fig, use_container_width=True)

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

# --- 메인 화면 렌더링 ---
@st.fragment(run_every=int(refresh_sec))
def render_dynamic_dashboard():
    # 이 Expander는 CSS 마법을 통해 맨 위쪽 헤더(Nav-bar)로 공중부양 됩니다.
    with st.expander("🌐 주요 시장 지수 및 환율 열어보기"):
        index_symbols = {"코스피": "^KS11", "코스닥": "^KQ11", "S&P 500": "^GSPC", "나스닥": "^IXIC"}
        
        idx_cols = st.columns(5)
        for i, (name, symbol) in enumerate(index_symbols.items()):
            try:
                idx_df = get_daily_data(symbol) 
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
                
        idx_cols[4].metric(label="원/달러 환율", value=f"₩{usd_to_krw:,.2f}")
    
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