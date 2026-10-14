"""Daily US-stock moving-average crossover signals. No order execution."""
from dataclasses import dataclass
from typing import Literal
import pandas as pd

GROWTH_NAMES = {"AAPL":"苹果","SPY":"标普500 ETF","QQQ":"纳斯达克100 ETF","NVDA":"英伟达"}
DEFENSIVE = ("WM","WMT","TSCO","LOW","MCD","TLT")
TICKERS = ("TSLA", *GROWTH_NAMES)

@dataclass(frozen=True)
class Signal:
    ticker: str
    session: str
    direction: Literal["BUY","SELL"]
    price: float
    ma_fast: float | None = None
    ma_slow: float | None = None
    threshold: float | None = None

    @property
    def key(self):
        return f"{self.session}:{self.ticker}:{self.direction}"

    @property
    def title(self):
        label = "特斯拉" if self.ticker == "TSLA" else GROWTH_NAMES[self.ticker]
        return f"{'🟢 买入' if self.direction == 'BUY' else '🔴 卖出'}信号｜{label} {self.ticker}"

    @property
    def body(self):
        if self.ticker == "TSLA":
            cross = "MA5 上穿 MA30" if self.direction == "BUY" else "MA5 下穿 MA30"
            trades = "卖出 ORLY → 买入 TSLA" if self.direction == "BUY" else "卖出 TSLA → 买入 ORLY"
            return (f"交易日：{self.session}（美东）\\n{cross}\\n"
                    f"TSLA 收盘：${self.price:.2f}\\nMA5：${self.ma_fast:.2f}｜MA30：${self.ma_slow:.2f}\\n"
                    f"策略提醒：{trades}\\n仅提醒，不自动下单；请确认持仓与成本。")
        cross = "上穿 MA225×1.01" if self.direction == "BUY" else "下穿 MA225×0.99"
        defensive = "/".join(DEFENSIVE)
        trades = (f"减持防御组合 {defensive} → 买入 {self.ticker}" if self.direction == "BUY"
                  else f"卖出 {self.ticker} → 买入防御组合 {defensive}")
        return (f"交易日：{self.session}（美东）\\n{cross}\\n"
                f"{self.ticker} 收盘：${self.price:.2f}\\n"
                f"MA225：${self.ma_slow:.2f}｜触发线：${self.threshold:.2f}\\n"
                f"策略提醒：{trades}\\n多个成长标的可能同时出现反向信号，需人工确认仓位。")

def check_signal(ticker: str, closes: pd.Series) -> Signal | None:
    if ticker not in TICKERS:
        raise ValueError(f"Unknown ticker: {ticker}")
    closes = pd.to_numeric(closes, errors="coerce").dropna()
    needed = 31 if ticker == "TSLA" else 226
    if len(closes) < needed:
        raise ValueError(f"{ticker}: need {needed} closes, got {len(closes)}")
    prev, curr = float(closes.iloc[-2]), float(closes.iloc[-1])
    session = str(pd.Timestamp(closes.index[-1]).date())
    if ticker == "TSLA":
        fast = closes.rolling(5).mean()
        slow = closes.rolling(30).mean()
        prev_diff, curr_diff = float(fast.iloc[-2]-slow.iloc[-2]), float(fast.iloc[-1]-slow.iloc[-1])
        direction = "BUY" if prev_diff <= 0 < curr_diff else ("SELL" if prev_diff >= 0 > curr_diff else None)
        return Signal(ticker, session, direction, curr, float(fast.iloc[-1]), float(slow.iloc[-1])) if direction else None
    ma = closes.rolling(225).mean()
    prior_upper, upper = float(ma.iloc[-2])*1.01, float(ma.iloc[-1])*1.01
    prior_lower, lower = float(ma.iloc[-2])*0.99, float(ma.iloc[-1])*0.99
    if prev <= prior_upper and curr > upper:
        return Signal(ticker, session, "BUY", curr, ma_slow=float(ma.iloc[-1]), threshold=upper)
    if prev >= prior_lower and curr < lower:
        return Signal(ticker, session, "SELL", curr, ma_slow=float(ma.iloc[-1]), threshold=lower)
    return None
