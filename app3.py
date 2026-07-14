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

# 1. 페이지 기본 설정
st.set_page_config(page_title="실시간 주식 차트 대시보드 Ver 3.1", layout="wide")

st.title("📈 실시간 주식 차트 대시보드 Ver 3.1")
st.markdown("RSI와 추세 기울기를 종합한 **AI 매수 적합도(%) 분석 시스템** 및 **MACD 지표 분석**이 도입되었습니다.")

# 실시간 원달러 환율 가져오기 (1시간 단위 캐싱)
@st.cache_data(ttl=3600)
def get_usd_krw_rate():
    try:
        ex_rate_info = yf.Ticker("USDKRW=X").history(period="1d")
        return ex_rate_info['Close'].iloc[-1]
    except:
        return 1350.0 

usd_to_krw = get_usd_krw_rate()

# 기본 한글 종목명 매핑 딕셔너리
TICKER_NAMES = {
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스",
    "TSLA": "테슬라",
    "INTC": "인텔",
    "NVDA": "엔비디아",
    "AAPL": "애플",
    "GOOGL": "구글(알파벳 A)"
}

# 2. 사이드바 설정 영역
st.sidebar.header("⚙️ 차트 설정")

# 테마(다크/라이트)에 맞춰 자연스럽게 변하는 투명 시계
current_refresh_time = datetime.now().strftime('%H:%M:%S')
with st.sidebar:
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
        }
    </style>
    <div class="clock-container" id="live-clock">
        ⏰ 현재 시간: 로딩중...
    </div>
    <script>
        function updateClock() {
            const now = new Date();
            const timeStr = now.toLocaleTimeString('ko-KR', { hour12: false });
            document.getElementById('live-clock').innerHTML = '⏰ 현재 시간: ' + timeStr;
        }
        setInterval(updateClock, 1000);
        updateClock();
    </script>
    """
    st.components.v1.html(clock_html, height=40)
    st.markdown(f"<div style='text-align: center; color: gray; font-size: 14px;'>🔄 마지막 갱신: {current_refresh_time}</div>", unsafe_allow_html=True)
    st.markdown("---")

# URL 쿼리 파라미터를 통한 사이드바 설정값 고정
if "tickers" in st.query_params:
    default_tickers = st.query_params["tickers"]
else:
    default_tickers = "005930.KS, 000660.KS, TSLA, INTC, NVDA, AAPL, GOOGL"

tickers_input = st.sidebar.text_input("종목 심볼 입력 (쉼표로 구분)", value=default_tickers)
st.query_params["tickers"] = tickers_input

tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
kr_tickers = [t for t in tickers if t.endswith('.KS') or t.endswith('.KQ')]
us_tickers = [t for t in tickers if not (t.endswith('.KS') or t.endswith('.KQ'))]

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

# MACD 토글 버튼 추가
show_macd = st.sidebar.checkbox("📉 MACD 지표 표시", value=get_bool_param("show_macd", True))
st.query_params["show_macd"] = str(show_macd)

show_news = st.sidebar.checkbox("📰 실시간 종목 뉴스 표시", value=get_bool_param("show_news", True))
st.query_params["show_news"] = str(show_news)

st.sidebar.markdown("---")
st.sidebar.subheader("⏱️ 자동 새로고침 설정")
refresh_sec = st.sidebar.number_input("자동 새로고침 간격(초)", min_value=10, max_value=600, value=60, step=10)

if st.sidebar.button("🔄 즉시 전체 새로고침"):
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    **📌 한국 주식 심볼 입력 방법**
    - **코스피(KOSPI):** 종목코드 뒤에 `.KS`
    - **코스닥(KOSDAQ):** 종목코드 뒤에 `.KQ`
    """
)

# --- 차트 렌더링 함수 (탭 기능 및 MACD 추가) ---
def render_charts(ticker_list, title):
    if not ticker_list:
        return
        
    st.header(title)
    
    # 종목이 2개 이상일 경우 탭(Tabs)을 생성하고, 1개일 경우 일반 컨테이너 사용
    if len(ticker_list) > 1:
        tabs = st.tabs(ticker_list)
    else:
        tabs = [st.container()]
    
    for idx, ticker in enumerate(ticker_list):
        # 각 종목을 해당하는 탭 안에 렌더링
        with tabs[idx]:
            try:
                ticker_obj = yf.Ticker(ticker)
                
                # 1. 데이터 먼저 불러오기
                df = ticker_obj.history(period=period, interval=interval)
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

                # 2. 보조지표(RSI) 계산
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).fillna(0)
                loss = (-delta.where(delta < 0, 0)).fillna(0)
                avg_gain = gain.ewm(com=13, adjust=False).mean()
                avg_loss = loss.ewm(com=13, adjust=False).mean()
                rs = avg_gain / avg_loss
                df['RSI'] = 100 - (100 / (1 + rs))
                
                current_rsi = df['RSI'].iloc[-1]
                pct_slope = 0.0
                
                # 3. 추세선(Slope) 계산 (데이터 5개 이상부터 분석)
                lookback = min(len(df), 20)
                if lookback >= 5:
                    y_vals = df['Close'].iloc[-lookback:].values
                    x_vals = np.arange(len(y_vals))
                    raw_slope, _ = np.polyfit(x_vals, y_vals, 1)
                    damped_slope = raw_slope * 0.25 
                    pct_slope = (damped_slope / y_vals[-1]) * 100

                # 4. 🔥 종합 매수 적합도(%) 계산 알고리즘
                rec_badge = "⚪ 분석 대기중"
                rsi_comment = ""
                
                if not pd.isna(current_rsi):
                    # 기본 점수: RSI 역산 (RSI가 낮을수록 점수 상승)
                    rsi_score = 100 - current_rsi
                    # 가중치: 기울기 백분율에 따른 보너스/페널티 점수
                    trend_bonus = pct_slope * 500
                    
                    # 최종 점수 산출 및 0~100 범위 제한
                    buy_score = rsi_score + trend_bonus
                    buy_score = max(0, min(100, buy_score))
                    
                    if buy_score >= 70:
                        rec_badge = f"🟢 강력 매수 구간 (추천도: {buy_score:.1f}%)"
                        rsi_comment = "🚨 **종합 분석:** 과매도 구간이거나 상승 모멘텀이 강합니다. 매수 매력도가 매우 높은 자리입니다."
                    elif buy_score <= 30:
                        rec_badge = f"🔴 강력 매도 주의 (추천도: {buy_score:.1f}%)"
                        rsi_comment = "🚨 **종합 분석:** 단기 과매수 상태이거나 하락 압력이 강합니다. 차익 실현 및 비중 축소가 권장됩니다."
                    elif buy_score >= 55:
                        rec_badge = f"↗️ 분할 매수 / 보유 (추천도: {buy_score:.1f}%)"
                        rsi_comment = "💡 **종합 분석:** 완만한 상승세 및 안정적인 매수세가 확인됩니다. 보유 또는 분할 매수가 유효합니다."
                    elif buy_score <= 45:
                        rec_badge = f"↘️ 비중 축소 / 관망 (추천도: {buy_score:.1f}%)"
                        rsi_comment = "💡 **종합 분석:** 매도세가 다소 우세합니다. 신규 진입을 자제하고 흐름을 지켜보는 것을 추천합니다."
                    else:
                        rec_badge = f"⚪ 중립 / 관망 (추천도: {buy_score:.1f}%)"
                        rsi_comment = "💡 **종합 분석:** 뚜렷한 방향성이 없는 횡보 구간이거나 수급이 팽팽합니다. 관망을 추천합니다."

                # 5. 종목명 및 추천 뱃지 출력
                kor_name = TICKER_NAMES.get(ticker, "")
                if not kor_name:
                    try:
                        fetched_name = ticker_obj.info.get('shortName') or ticker_obj.info.get('longName', "")
                        if fetched_name: kor_name = fetched_name
                    except:
                        pass
                
                display_title = f"📊 {ticker} ({kor_name}) &nbsp;|&nbsp; {rec_badge}" if kor_name else f"📊 {ticker} &nbsp;|&nbsp; {rec_badge}"
                st.subheader(display_title)

                # 환율 적용 및 전일 종가 계산
                try:
                    daily_df = ticker_obj.history(period="5d", interval="1d")
                    if len(daily_df) >= 2:
                        prev_close_usd_or_krw = daily_df['Close'].iloc[-2]
                    else:
                        prev_close_usd_or_krw = ticker_obj.fast_info.get('previousClose', None)
                except:
                    prev_close_usd_or_krw = ticker_obj.fast_info.get('previousClose', None)
                
                if ticker in us_tickers:
                    df['Open'] = df['Open'] * usd_to_krw
                    df['High'] = df['High'] * usd_to_krw
                    df['Low'] = df['Low'] * usd_to_krw
                    df['Close'] = df['Close'] * usd_to_krw
                    prev_krw = prev_close_usd_or_krw * usd_to_krw if prev_close_usd_or_krw else None
                else:
                    prev_krw = prev_close_usd_or_krw

                curr_krw = df['Close'].iloc[-1]

                col1, col2 = st.columns([1, 1])
                with col1:
                    if prev_krw:
                        change_krw = curr_krw - prev_krw
                        change_pct = (change_krw / prev_krw) * 100
                        st.metric(
                            label="현재 주가 (원화 차트 기준)", 
                            value=f"₩{curr_krw:,.0f}", 
                            delta=f"{change_krw:+,.0f}원 ({change_pct:+.2f}%)"
                        )
                        st.caption(f"**직전 장 마감 금액:** ₩{prev_krw:,.0f}")
                    else:
                        st.metric(label="현재 주가 (원화 차트 기준)", value=f"₩{curr_krw:,.0f}")
                        st.caption("직전 장 마감 데이터를 불러올 수 없습니다.")
                
                with col2:
                    step_val = 1.0 if ticker in us_tickers else 100.0
                    unit_str = "$" if ticker in us_tickers else "원"
                    param_key = f"avg_{ticker}"
                    default_avg_price = float(st.query_params.get(param_key, 0.0))
                    
                    input_price = st.number_input(
                        f"💰 [{ticker}] 내 평단가 입력 ({unit_str})", 
                        value=default_avg_price, 
                        step=step_val, 
                        key=f"input_{ticker}"
                    )
                    
                    if input_price > 0:
                        st.query_params[param_key] = input_price
                    elif param_key in st.query_params:
                        del st.query_params[param_key]

                # MACD를 켰을 때와 껐을 때 차트 단수(rows) 설정 변경
                rows_count = 4 if show_macd else 3
                row_heights = [0.5, 0.15, 0.15, 0.2] if show_macd else [0.6, 0.2, 0.2]
                chart_height = 900 if show_macd else 800

                # 다중 분할 차트 구성
                vol_colors = ['red' if close >= open_price else 'blue' for close, open_price in zip(df['Close'], df['Open'])]
                fig = make_subplots(
                    rows=rows_count, cols=1, 
                    shared_xaxes=True, 
                    vertical_spacing=0.05,
                    row_heights=row_heights
                )

                fig.add_trace(go.Candlestick(
                    x=df.index,
                    open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                    name=ticker, increasing_line_color='red', decreasing_line_color='blue'
                ), row=1, col=1)

                fig.add_trace(go.Bar(
                    x=df.index, y=df['Volume'], 
                    marker_color=vol_colors, name='거래량'
                ), row=2, col=1)

                fig.add_trace(go.Scatter(
                    x=df.index, y=df['RSI'], 
                    mode='lines', name='RSI', line=dict(color='purple', width=1.5)
                ), row=3, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1, annotation_text="과매수(70)")
                fig.add_hline(y=30, line_dash="dash", line_color="blue", row=3, col=1, annotation_text="과매도(30)")

                # MACD 계산 및 렌더링 (체크되었을 때만)
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
                        mode='lines', name='MACD 선(12,26)', line=dict(color='orange', width=1.5)
                    ), row=4, col=1)
                    
                    fig.add_trace(go.Scatter(
                        x=df.index, y=df['Signal'], 
                        mode='lines', name='시그널 선(9)', line=dict(color='royalblue', width=1.5)
                    ), row=4, col=1)

                if prev_krw:
                    fig.add_hline(
                        y=prev_krw, line_dash="dot", line_color="gray", 
                        row=1, col=1, annotation_text="직전 장 마감", annotation_position="bottom right"
                    )
                    
                if len(df) > 0:
                    today_open_krw = df['Open'].iloc[0]
                    fig.add_hline(
                        y=today_open_krw, line_dash="dashdot", line_color="orange", 
                        row=1, col=1, annotation_text="오늘 시가", annotation_position="bottom left"
                    )

                if input_price > 0:
                    display_avg_price = input_price * usd_to_krw if ticker in us_tickers else input_price
                    label_text = f"내 평단가: {input_price:,.2f}$" if ticker in us_tickers else f"내 평단가: {input_price:,.0f}원"
                    fig.add_hline(
                        y=display_avg_price, line_dash="solid", line_color="magenta", 
                        row=1, col=1, annotation_text=label_text, annotation_position="top left"
                    )

                if show_ma:
                    if len(df) >= 5:
                        df['MA5'] = df['Close'].rolling(window=5).mean()
                        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], mode='lines', name='5주기 MA', line=dict(color='orange', width=1.5)), row=1, col=1)
                    if len(df) >= 20:
                        df['MA20'] = df['Close'].rolling(window=20).mean()
                        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], mode='lines', name='20주기 MA', line=dict(color='green', width=1.5)), row=1, col=1)
                    if len(df) >= 60:
                        df['MA60'] = df['Close'].rolling(window=60).mean()
                        fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], mode='lines', name='60주기 MA', line=dict(color='royalblue', width=1.5)), row=1, col=1)

                # 15시 30분 / 17시 타겟 예측선
                prediction_comment = ""
                miss_warning = ""
                if show_prediction and lookback >= 5:
                    try:
                        y_pred = df['Close'].iloc[-lookback:].values
                        x_pred = np.arange(len(y_pred))
                        raw_slope, intercept = np.polyfit(x_pred, y_pred, 1)
                        damped_slope = raw_slope * 0.25 
                        
                        last_time = df.index[-1]
                        time_diff = df.index[-1] - df.index[-2] if len(df) >= 2 else timedelta(minutes=5)
                        if time_diff.total_seconds() <= 0: time_diff = timedelta(minutes=5)
                        
                        is_kr = ticker in kr_tickers
                        t_hour = 15 if is_kr else 17
                        t_minute = 30 if is_kr else 0
                        t_label = "15시 30분 예측선" if is_kr else "17시 예측선"
                            
                        target_time = last_time.replace(hour=t_hour, minute=t_minute, second=0, microsecond=0)
                        if target_time <= last_time: target_time += timedelta(days=1)
                            
                        steps = int((target_time - last_time) / time_diff)
                        steps = max(5, min(steps, 200)) 
                        
                        future_times = [last_time] + [last_time + time_diff * i for i in range(1, steps + 1)]
                        future_y = [y_pred[-1]] + [damped_slope * i + y_pred[-1] for i in range(1, steps + 1)]
                        
                        fig.add_trace(go.Scatter(
                            x=future_times, y=future_y, mode='lines', name=t_label,
                            line=dict(color='purple', width=4, dash='dash')
                        ), row=1, col=1)
                        
                        trend_dir = "횡보"
                        if pct_slope > 0.02:
                            trend_dir = "상승"
                            prediction_comment = f"📈 **단기 추세:** 최근 가격 흐름에서 매수세가 포착됩니다. {t_hour}시 {t_minute}분까지 우상향이 예측됩니다."
                        elif pct_slope < -0.02:
                            trend_dir = "하락"
                            prediction_comment = f"📉 **단기 추세:** 최근 가격 흐름에서 매도 압력이 우세합니다. {t_hour}시 {t_minute}분까지 하락세가 예측됩니다."
                        else:
                            prediction_comment = f"➖ **단기 추세:** 좁은 박스권에 머물고 있습니다. {t_hour}시 {t_minute}분까지 횡보할 것으로 예측됩니다."
                        
                        if len(df) >= 3:
                            recent_change = (df['Close'].iloc[-1] - df['Close'].iloc[-3]) / df['Close'].iloc[-3] * 100
                            if trend_dir == "상승" and recent_change < -0.3:
                                miss_warning = f"🚨 **추세 이탈 감지!** 단기 급락({recent_change:+.2f}%) 발생. 대량 매도세나 악재 뉴스를 확인하세요."
                                prediction_comment = "" 
                            elif trend_dir == "하락" and recent_change > 0.3:
                                miss_warning = f"🚨 **추세 이탈 감지!** 단기 급등({recent_change:+.2f}%) 발생. 대량 매수세나 호재 뉴스를 확인하세요."
                                prediction_comment = "" 
                    except:
                        pass 

                # 통합 AI 분석 코멘트 출력
                final_comment = ""
                if miss_warning:
                    final_comment = miss_warning + "\n\n" + rsi_comment if rsi_comment else miss_warning
                    st.warning(final_comment)
                elif prediction_comment:
                    final_comment = prediction_comment + "\n\n" + rsi_comment if rsi_comment else prediction_comment
                    st.info(final_comment)
                
                if final_comment:
                    st.caption(f"※ AI 분석 엔진: 최근 {lookback}주기 데이터 선형 회귀 분석 및 실시간 RSI 모멘텀 기반 종합 알고리즘")

                fig.update_layout(
                    template="plotly_white", xaxis_rangeslider_visible=False,
                    margin=dict(l=0, r=0, t=10, b=0), height=chart_height,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                fig.update_yaxes(title_text="가격 (원화)", tickformat="₩,", row=1, col=1)
                fig.update_yaxes(title_text="거래량", row=2, col=1)
                fig.update_yaxes(title_text="RSI (0~100)", range=[0, 100], row=3, col=1)
                
                if show_macd:
                    fig.update_yaxes(title_text="MACD", row=4, col=1)
                    fig.update_xaxes(rangeslider=dict(visible=False), row=4, col=1)
                    
                fig.update_xaxes(rangeslider=dict(visible=False), row=1, col=1)
                fig.update_xaxes(rangeslider=dict(visible=False), row=2, col=1)
                fig.update_xaxes(rangeslider=dict(visible=False), row=3, col=1)
                
                st.plotly_chart(fig, use_container_width=True)

                # 실시간 뉴스 렌더링 (Google RSS 파싱 방식 - KST 시간 적용 완료)
                if show_news:
                    with st.expander(f"📰 [{ticker}] 실시간 핵심 뉴스 보기"):
                        try:
                            query = kor_name if kor_name else ticker
                            encoded_query = urllib.parse.quote(query)
                            
                            # 구글 뉴스 한국어 RSS 피드 URL 생성 (최근 1일 데이터)
                            rss_url = f"https://news.google.com/rss/search?q={encoded_query}+when:1d&hl=ko&gl=KR&ceid=KR:ko"
                            
                            # 봇 차단을 방지하기 위해 User-Agent 추가
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
                                            
                                            # GMT 시간을 KST로 변환 적용
                                            if pub_date:
                                                try:
                                                    dt = parsedate_to_datetime(pub_date)
                                                    kst_timezone = timezone(timedelta(hours=9))
                                                    dt_kst = dt.astimezone(kst_timezone)
                                                    pub_date = dt_kst.strftime('%Y-%m-%d %H:%M:%S KST')
                                                except Exception:
                                                    pass

                                            date_str = f" ({pub_date})" if pub_date else ""
                                            st.markdown(f"- **[{title}]({link})**{date_str}")
                                            display_count += 1
                                            
                                    if display_count >= 3: 
                                        break
                                        
                                if display_count == 0: 
                                    st.write("최근 검색된 새로운 뉴스가 없습니다.")
                            else:
                                st.write("최근 검색된 뉴스가 없습니다.")
                        except Exception as e:
                            st.write(f"뉴스를 불러오는 중 오류가 발생했습니다: {e}")

            except Exception as e:
                st.error(f"[{ticker}] 차트 오류: {e}")

# --- 메인 화면 렌더링 (Fragment 적용) ---
st.markdown(f"**현재 적용된 원/달러 환율:** ₩{usd_to_krw:,.2f}")

@st.fragment(run_every=int(refresh_sec))
def render_dynamic_dashboard():
    st.markdown("### 🌐 주요 시장 지수")
    index_symbols = {"코스피": "^KS11", "코스닥": "^KQ11", "S&P 500": "^GSPC", "나스닥": "^IXIC"}
    idx_cols = st.columns(4)

    for i, (name, symbol) in enumerate(index_symbols.items()):
        try:
            idx_ticker = yf.Ticker(symbol)
            idx_df = idx_ticker.history(period="5d")
            if len(idx_df) >= 2:
                curr_idx = idx_df['Close'].iloc[-1]
                prev_idx = idx_df['Close'].iloc[-2]
                idx_change = curr_idx - prev_idx
                idx_pct = (idx_change / prev_idx) * 100
                idx_cols[i].metric(label=name, value=f"{curr_idx:,.2f}", delta=f"{idx_change:+.2f} ({idx_pct:+.2f}%)")
            else:
                idx_cols[i].metric(label=name, value="데이터 없음")
        except:
            idx_cols[i].metric(label=name, value="데이터 오류")

    st.markdown("<br>", unsafe_allow_html=True)
    
    if not tickers:
        st.info("사이드바에서 조회할 종목 심볼을 입력해 주세요.")
    else:
        if kr_tickers:
            render_charts(kr_tickers, "🇰🇷 한국 주식")
            st.markdown("<br>", unsafe_allow_html=True) 
            
        if us_tickers:
            render_charts(us_tickers, "🇺🇸 미국 주식")

# 대시보드 실행
render_dynamic_dashboard()