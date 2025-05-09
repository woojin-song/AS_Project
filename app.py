import streamlit as st
from simulation import StockSimulator
import plotly.graph_objects as go
import datetime
import pytz
import json
import time

# 기본 설정
st.set_page_config(page_title="📊 AI-based stock analysis", layout="wide")
st.title("📊 AI-based stock analysis")

simulator = StockSimulator(ticker="NVDA")

# 시간 설정
kst = pytz.timezone("Asia/Seoul")
now_kst = datetime.datetime.now(kst)

est = pytz.timezone("US/Eastern")
now_est = datetime.datetime.now(est)
market_open_time = now_est.replace(hour=9, minute=30, second=0, microsecond=0)
market_close_time = now_est.replace(hour=16, minute=0, second=0, microsecond=0)

# 헤더 시간 정보
st.markdown(f"🕒 현재 시각 (한국): **{now_kst.strftime('%Y-%m-%d %H:%M:%S')}**")
st.markdown(f"🕒 현재 시각 (뉴욕): **{now_est.strftime('%Y-%m-%d %H:%M:%S')}**")

# 프리마켓 상태 확인
if now_est < market_open_time or now_est > market_close_time:
    st.info(f"⏳ 현재는 프리마켓입니다 (한국 기준 {now_kst.strftime('%H:%M')})")
    # 여기서 새로고침을 60초마다 할 수 있습니다
    time.sleep(60)  # 1분 동안 대기 후 새로고침

else:
    st.success(f"✅ 정규장입니다 (한국 기준 {now_kst.strftime('%H:%M')})")
    ticker = st.text_input("티커", value="NVDA")

    # 1분봉 데이터 가져오기
    df = simulator.get_live_candles(ticker)

    if not df.empty:
        # 📈 실시간 1분봉 차트
        st.subheader(f"📈 실시간 1분봉 차트 ({ticker})")

        # 이동평균선 표시 여부 선택
        show_ma_5 = st.checkbox("5일 이동평균선 표시")
        show_ma_20 = st.checkbox("20일 이동평균선 표시")

        # 차트 그리기
        fig = go.Figure(data=[go.Candlestick(
            x=df['Datetime'],
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            increasing_line_color='green',
            decreasing_line_color='red'
        )])

        # 이동평균선 추가 (선택된 경우에만)
        if show_ma_5:
            df['MA_5'] = df['Close'].rolling(window=5).mean()
            fig.add_trace(go.Scatter(
                x=df['Datetime'], 
                y=df['MA_5'], 
                mode='lines', 
                name='5일 이동평균선', 
                line=dict(color='blue', width=2)
            ))

        if show_ma_20:
            df['MA_20'] = df['Close'].rolling(window=20).mean()
            fig.add_trace(go.Scatter(
                x=df['Datetime'], 
                y=df['MA_20'], 
                mode='lines', 
                name='20일 이동평균선', 
                line=dict(color='orange', width=2)
            ))

        # 차트 레이아웃 설정
        fig.update_layout(
            template="plotly_white",
            height=600,
            xaxis_title="시간 (KST)",
            xaxis_rangeslider_visible=False,
            xaxis=dict(
                tickformat="%H:%M:%S",
                tickangle=0
            ),
            yaxis_title="가격 (USD)"
        )

        # 컬럼을 사용하여 차트와 GPT 판단을 나눔
        col1, col2 = st.columns([3, 1])  # 차지 비율 3:1로 설정

        # 첫 번째 컬럼에 차트 표시
        with col1:
            st.plotly_chart(fig, use_container_width=True)

            # 현재 주가 텍스트로 표시
            current_price = df['Close'].iloc[-1]
            st.markdown(f"**현재 주가 (마지막 1분봉):** ${current_price:,.2f}")

        # 두 번째 컬럼에 GPT 판단 표시
        with col2:
            # GPT 판단 처리 부분
            st.subheader("🧠 GPT 투자 판단")

            try:
                # GPT 판단 결과 획득
                res = simulator.decision_ai.get_stock_decision(
                    market="US",
                    company_name=ticker,
                    price_hist_1y=df['Close'].to_list(),
                    price_hist_10m=df['Close'][-10:].to_list(),
                    current_price=current_price,
                    current_count=simulator.current_count,
                    current_money=simulator.current_money,
                    ma_5m=simulator.ma_5m,
                    ma_20m=simulator.ma_20m,
                    ma_5d=simulator.ma_5d,
                    ma_20d=simulator.ma_20d,
                    prev_res=simulator.prev_res
                )

                if not isinstance(res, dict):
                    raise ValueError("GPT 응답이 딕셔너리 형식이 아닙니다.")

                result = simulator.handle_decision(res, current_price)

                # 판단 요약 표시
                summary_data = {
                    "action": result.get("action", "hold"),  # 기본값 'hold' 설정
                    "quantity": result.get("quantity", 0),  # 기본값 0 설정
                    "price": result.get("price", 0.0),  # 기본값 0.0 설정
                    "reason": result.get("reason", "사유 없음"),
                    "risk_type": result.get("risk_type", "없음")
                }

                st.subheader("📊 판단 요약")
                st.code(json.dumps(summary_data, indent=2, ensure_ascii=False), language="json")

                # 자산 상태 표시
                if 'asset_status' in result:
                    st.subheader("💰 현재 자산 상태")
                    st.metric("현금", f"${result['asset_status'].get('cash', 0):.2f}")
                    st.metric("보유 수량", f"{result['asset_status'].get('count', 0)}주")
                    st.metric("총 자산", f"${result['asset_status'].get('total', 0):.2f}")
                    st.metric("현재 주가", f"${result.get('current_price', 0):.2f}")
                else:
                    st.error("❗ 자산 상태 정보를 불러올 수 없습니다.")

                # 액션 결과 메시지
                action = result.get("action", "hold")
                if action == "buy":
                    st.success(f"🚀 매수 추천: {result['action_result']}")
                elif action == "sell":
                    st.warning(f"⚠️ 매도 추천: {result['action_result']}")
                else:
                    st.info(f"⏸️ 판단: {result['action_result']}")

            except json.JSONDecodeError:
                st.error("❗ JSON 디코딩 중 오류 발생 - 응답이 올바른 형식인지 확인하세요.")
            except Exception as e:
                st.error(f"❗ GPT 판단 처리 중 오류 발생: {e}")

        # 새로고침을 부드럽게 하기 위해 데이터가 변경된 후만 새로고침
        st.rerun()