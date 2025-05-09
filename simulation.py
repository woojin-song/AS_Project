import yfinance as yf
import pandas as pd
import time
import pytz
from ai import StockDecisionAI

class StockSimulator:
    def __init__(self, ticker="NVDA", initial_money=1000, model="o4-mini-2025-04-16"):
        self.ticker = ticker
        self.stock = yf.Ticker(ticker)
        self.current_count = 0
        self.current_money = initial_money
        self.prev_res = None
        self.model = model
        self.decision_ai = StockDecisionAI()
        self.ma_5m = None
        self.ma_20m = None
        self.ma_5d = None
        self.ma_20d = None
        self.rows = []  # rows 속성 추가

    # 실시간 1분봉 캔들 데이터 가져오기
    def get_live_candles(self, ticker, interval="1m", lookback="1d"):
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=lookback, interval=interval)
            
            # 'Datetime'을 인덱스로 설정
            df.reset_index(inplace=True)
            df['Datetime'] = pd.to_datetime(df['Datetime'])
            
            # 'Datetime'을 한국 시간(KST)으로 변환
            df['Datetime'] = df['Datetime'].dt.tz_convert('Asia/Seoul')
            
            return df
        except Exception as e:
            return pd.DataFrame()  # 오류가 나면 빈 데이터프레임 반환


    def get_ma_1y(self):
        price_hist_1y = self.stock.history(period="1y", interval="1d")
        price_hist_1y["MA_5"] = price_hist_1y["Close"].rolling(window=5).mean()
        price_hist_1y["MA_20"] = price_hist_1y["Close"].rolling(window=20).mean()

        self.ma_5d = price_hist_1y["MA_5"].iloc[-1] if pd.notna(price_hist_1y["MA_5"].iloc[-1]) else None
        self.ma_20d = price_hist_1y["MA_20"].iloc[-1] if pd.notna(price_hist_1y["MA_20"].iloc[-1]) else None

        return self.ma_5d, self.ma_20d

    def get_ma_recent(self, df):
        if df is not None and not df.empty:
            self.ma_5m = df["Close"].rolling(window=5).mean().iloc[-1]
            self.ma_20m = df["Close"].rolling(window=20).mean().iloc[-1]

    def handle_decision(self, res, current_price):
        action = res.get("action")
        quantity = int(res.get("quantity", 0))  # 기본값으로 0
        price = float(res.get("price", current_price))  # 기본값으로 current_price
        reason = res.get("reason", "사유 없음")  # 기본값으로 "사유 없음"
        risk_type = res.get("risk_type", "없음")  # 기본값으로 "없음"

        # 추가적인 로그나 메시지
        log_messages = [f"[{risk_type}] {reason}"]
        action_result = ""

        # 조건에 따른 행동 결정
        if action == "buy":
            if price * quantity <= self.current_money:
                self.current_money -= price * quantity
                self.current_count += quantity
                action_result = f"🛒 {price:.2f}$에 {quantity}주 매수"
            else:
                action_result = "❌ 자금 부족으로 매수 실패"
        elif action == "sell":
            if quantity <= self.current_count:
                self.current_money += price * quantity
                self.current_count -= quantity
                action_result = f"💰 {price:.2f}$에 {quantity}주 매도"
            else:
                action_result = "❌ 보유 수량 부족으로 매도 실패"
        elif action == "hold":
            action_result = "⏸️ 홀드"
        else:
            action_result = f"❌ 유효하지 않은 액션: {action}"

        self.prev_res = action_result
        total_assets = self.current_money + (self.current_count * current_price)

        # 반환되는 값에서 각 필드를 확인
        return {
            "log": log_messages,
            "decision_summary": {
                "action": action,
                "quantity": quantity,
                "price": price,
                "reason": reason,
                "risk_type": risk_type
            },
            "action_result": action_result,
            "asset_status": {
                "cash": self.current_money,
                "count": self.current_count,
                "total": total_assets
            }
        }

    def run(self):
        while True:  # 루프 시작
            # 실시간 데이터 받아오기
            df = self.get_live_candles(ticker=self.ticker, interval="1m", lookback="1d")
            if df.empty:
                print("No data available")
                time.sleep(60)  # 1분 대기 후 다시 시도
                continue

            # 최근 5분, 20분 이동 평균 계산
            self.get_ma_recent(df)

            # 1년 이동 평균도 가져오기
            ma_5d, ma_20d = self.get_ma_1y()

            # 의사결정 호출
            res = self.decision_ai.get_stock_decision(
                market="US",
                company_name=self.ticker,
                price_hist_1y=df['Close'].to_list(),
                price_hist_10m=df['Close'][-10:].to_list(),
                current_price=df['Close'].iloc[-1],
                current_count=self.current_count,
                current_money=self.current_money,
                ma_5m=self.ma_5m,
                ma_20m=self.ma_20m,
                ma_5d=ma_5d,
                ma_20d=ma_20d,
                prev_res=self.prev_res
            )

            # 의사결정에 따른 행동 처리
            self.handle_decision(res, df['Close'].iloc[-1])

            # 1분마다 반복
            time.sleep(60)