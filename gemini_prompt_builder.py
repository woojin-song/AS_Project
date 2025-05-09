import google.generativeai as genai
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
import os
import json
from stock_data_fetcher import fetch_stock_data

# 환경 변수 로드
load_dotenv()

# 상수 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = "gemini-1.5-flash"

# API 키 유효성 검사
if not GEMINI_API_KEY:
    raise EnvironmentError("환경 변수 'GEMINI_API_KEY'가 설정되지 않았습니다.")

# Gemini 구성
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(model_name=GEMINI_MODEL_NAME)


def build_gemini_prompt(
    market: str,
    company_name: str,
    ticker_symbol: str,
    current_count: int,
    current_money: float,
    current_price: float,
    ma_5m: Optional[float],
    ma_20m: Optional[float],
    ma_5d: Optional[float],
    ma_20d: Optional[float],
    price_hist_1y: str,
    price_hist_10m: str,
    prev_res: str = ""
) -> str:
    def make_ma_summary() -> str:
        summaries = [
            f"5분 이동 평균: {ma_5m}달러" if ma_5m is not None else None,
            f"20분 이동 평균: {ma_20m}달러" if ma_20m is not None else None,
            f"최근 5일 이동 평균: {ma_5d}달러" if ma_5d is not None else None,
            f"최근 20일 이동 평균: {ma_20d}달러" if ma_20d is not None else None,
        ]
        return "\n".join(filter(None, summaries))

    chat = model.start_chat()

    rule_message = "# 규칙\n당신은 AI 주식 트레이너입니다."

    request_message = f"""# 요청
{market}의 {company_name} 종목에 대해 이야기할 거야.
현재 {company_name}의 주가는 1주당 {current_price}달러이고,
나는 {current_count}주를 보유 중이며, 보유 현금은 {current_money}달러야.

## 이동 평균
{make_ma_summary()}

## 이전 주가 정보
최근 1년간 일별 변동:
{price_hist_1y}

최근 10분간 분별 변동:
{price_hist_10m}

참고로 너는 10분 전에 "{prev_res}"라고 판단했어.
"""

    question_message = """# 질문
지금은 어떤 타이밍이니? 매수/매도/보유 중에서 선택해줘.
몇 주를 어떤 가격에 거래할지도 구체적으로 말해줘.
최종 판단은 인간이 해, 너는 조언만 해주는 역할이야."""

    output_format_message = """# 출력 형식
출력은 Python에서 사용 가능한 JSON 형식으로 해줘.
JSON을 마크다운이나 텍스트로 감싸지 말고, 순수하게 객체만 출력해.

형식 예시는 다음과 같아:
{
  "reason": "...이유 설명...",
  "risk_type": "안정적" or "공격적",
  "action": "buy" or "sell" or "hold",
  "quantity": 정수,  # 주식 수
  "price": 실수      # 거래 가격
}

`reason`을 우선 생각한 후, 단계적으로 분석해줘.
"""

    try:
        messages = [
            rule_message,
            request_message,
            question_message,
            output_format_message,
        ]

        for idx, msg in enumerate(messages, start=1):
            chat.send_message(msg)

        # Gemini 응답을 받아서 리턴
        return chat.last.text

    except Exception as e:
        return f"[오류] Gemini 응답 중 {idx}번째 메시지 전송 실패: {e}"


def get_gemini_decision(market, company_name, ticker_symbol, current_count, current_money, prev_res=""):
    # 데이터 수집
    data = fetch_stock_data(ticker_symbol)

    # Debugging: Print data to verify
    print("Stock Data:", data)

    # Gemini 응답 받기
    response = build_gemini_prompt(
        market=market,
        company_name=company_name,
        ticker_symbol=ticker_symbol,
        current_count=current_count,
        current_money=current_money,
        current_price=data["current_price"],
        ma_5m=data["ma_5m"],
        ma_20m=data["ma_20m"],
        ma_5d=data["ma_5d"],
        ma_20d=data["ma_20d"],
        price_hist_1y=data["price_hist_1y"],
        price_hist_10m=data["price_hist_10m"],
        prev_res=prev_res
    )

    # Debugging: Print the response
    print("Gemini Response:", response)

    # JSON 파싱
    try:
        decision = json.loads(response)
        return decision
    except json.JSONDecodeError:
        print("Gemini 응답을 파싱할 수 없습니다.")
        print(response)  # To see the full response if it's not valid JSON
        return None