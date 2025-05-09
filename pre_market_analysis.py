import os
import datetime
import pytz
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import alpaca_trade_api as tradeapi

load_dotenv()

# 시간 설정
kst = pytz.timezone("Asia/Seoul")
now_kst = datetime.datetime.now(kst)
one_day_ago = now_kst - datetime.timedelta(days=1)

# 날짜 포맷
start_date = one_day_ago.strftime('%Y-%m-%d')
end_date = now_kst.strftime('%Y-%m-%d')

# Alpaca API Key 설정
ALPACA_API_KEY = os.getenv("ALPACA_NORMAL_KEY")
print(f"ALPACA_API_KEY: {ALPACA_API_KEY}")  # 디버깅용 로그
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = "https://data.alpaca.markets"

# Alpaca API 객체 생성
def get_alpaca_api():
    return tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL)

# 카드 UI 출력 함수
def card(title, content):
    st.markdown(
        f"""
        <div style='background-color: #f9f9f9; padding: 15px; border-radius: 10px;
         box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 10px;'>
            <h5 style='margin-bottom: 8px;'>{title}</h5>
            <div style='font-size: 15px;'>{content}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# 기업 분석 탭
def display_company_analysis(ticker):
    st.subheader(f"💡 {ticker} 기업 분석")

    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        tab1, tab2, tab3 = st.tabs(["🏢 회사 정보", "📈 주가 차트", "📰 뉴스"])

        # 회사 정보
        with tab1:
            st.markdown("#### 🔍 기본 정보")
            st.write("기업명 :", info.get('longName', 'N/A'))
            st.write("섹터 :", info.get('sector', 'N/A'))
            st.write("산업 :", info.get('industry', 'N/A'))

            st.markdown("#### 💵 재무 지표")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("시가총액", f"{info.get('marketCap', 0):,}")
                st.metric("주가수익비율 (PER)", f"{info.get('trailingPE', 'N/A')}")
                st.metric("주당순이익 (EPS)", f"{info.get('trailingEps', 'N/A')}")
            with col2:
                dividend_yield = info.get('dividendYield', 0) or 0
                st.metric("배당수익률", f"{dividend_yield * 100:.2f}%")
                st.metric("부채비율", f"{info.get('debtToEquity', 'N/A')}")

        # 주가 차트
        with tab2:
            st.markdown("#### 📈 주가 차트 옵션")
            period = st.selectbox("기간 (period)", ["1d", "1mo", "6mo", "1y", "5y", "max"], index=2)
            interval = st.selectbox("간격 (interval)", ["1d", "60m", "15m", "5m", "1m"], index=0)

            df = stock.history(period=period, interval=interval)

            if not df.empty:
                df.reset_index(inplace=True)
                st.markdown(f"### 📉 주가 차트(Close, 최근 {period} 기준, {interval} 간격)")
                st.line_chart(df.set_index("Date")["Close"], height=300)

                st.markdown("#### 🕯️ 캔들차트")
                fig = go.Figure(data=[go.Candlestick(
                    x=df["Date"],
                    open=df["Open"],
                    high=df["High"],
                    low=df["Low"],
                    close=df["Close"]
                )])
                fig.update_layout(template="plotly_white", height=500)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("📉 차트 데이터가 없습니다.")

        # 뉴스 탭
        with tab3:
            st.markdown("#### 📰 관련 뉴스 기사")
            try:
                # 날짜를 URL-safe하게 인코딩된 ISO 8601로 변환
                start_iso = quote(one_day_ago.strftime('%Y-%m-%dT00:00:00Z'))
                end_iso = quote(now_kst.strftime('%Y-%m-%dT00:00:00Z'))

                url = (
                    f"https://data.alpaca.markets/v1beta1/news"
                    f"?start={start_iso}&end={end_iso}"
                    f"&sort=desc&symbols={ticker}&limit=5&include_content=true"
                )

                headers = {
                    "accept": "application/json",
                    "APCA-API-KEY-ID": ALPACA_API_KEY,
                    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY
                }

                response = requests.get(url, headers=headers)
                response.raise_for_status()
                news_data = response.json().get("news", [])

                if news_data:
                    for article in news_data:
                        headline = article.get("headline", "제목 없음")
                        summary = article.get("summary", "")
                        url_link = article.get("url", "#")
                        content_html = article.get("content", "")
                        content_clean = BeautifulSoup(content_html, "html.parser").get_text().strip()

                        card(
                            headline,
                            f"{summary}<br><br><b>내용 일부:</b><br>{content_clean[:300]}...<br>"
                            f"<a href='{url_link}' target='_blank'>[기사 전체 보기]</a>"
                        )
                else:
                    st.info("🔍 1일 전 기준 뉴스가 없습니다.")
            except Exception as e:
                st.error(f"❗ Alpaca 뉴스 불러오기 오류: {e}")

    except Exception as e:
        st.error(f"분석 중 오류 발생: {e}")