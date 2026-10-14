"""GitHub Actions daily-close strategy check: Yahoo Finance -> Bark."""
import argparse
from datetime import datetime, time
import json
import logging
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf
import pandas_market_calendars as mcal
from strategy import TICKERS, check_signal

LOG = logging.getLogger("us-stock-bark-alerts")
STATE_FILE = Path(__file__).with_name("state.json")
NY = ZoneInfo("America/New_York")

def push_bark(title: str, body: str, link: str | None = None) -> None:
    key = os.environ.get("BARK_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing BARK_KEY: add repository Actions secret")
    base = (os.environ.get("BARK_SERVER") or "https://api.day.app").rstrip("/")
    if not base.startswith("https://"):
        raise ValueError("BARK_SERVER must start with https://")
    data = {"device_key": key, "title": title, "body": body,
            "group": "美股策略信号", "level": "timeSensitive"}
    if link:
        data["url"] = link
    response = requests.post(f"{base}/push", json=data, timeout=15)
    response.raise_for_status()
    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError("Bark returned invalid JSON") from exc
    if not isinstance(result, dict) or result.get("code") not in (200, 0):
        raise RuntimeError(f"Bark rejected push: {result}")

def today_session(now: datetime, manual: bool) -> str | None:
    now_ny = now.astimezone(NY)
    if now_ny.time() < time(16, 30) or (not manual and now_ny.time() > time(17, 10)):
        LOG.info("Not in NY after-close monitoring window")
        return None
    date = now_ny.date()
    if len(mcal.get_calendar("NYSE").valid_days(start_date=date, end_date=date)) == 0:
        LOG.info("NYSE closed on %s", date)
        return None
    return date.isoformat()

def fetch_closes(ticker: str, expected_session: str) -> pd.Series:
    candles = yf.Ticker(ticker).history(period="2y", interval="1d",
                  auto_adjust=True, actions=False, prepost=False, timeout=20)
    if candles is None or candles.empty or "Close" not in candles:
        raise RuntimeError(f"{ticker}: empty Yahoo Finance history")
    closes = pd.to_numeric(candles["Close"], errors="coerce").dropna()
    if closes.empty:
        raise RuntimeError(f"{ticker}: no prices")
    closes.index = pd.DatetimeIndex([pd.Timestamp(x).date() for x in closes.index])
    closes = closes[~closes.index.duplicated(keep="last")].sort_index()
    closes = closes.loc[closes.index <= pd.Timestamp(expected_session)]
    latest = closes.index[-1].date().isoformat() if not closes.empty else "none"
    if latest != expected_session:
        raise RuntimeError(f"{ticker}: latest date {latest}, expected {expected_session}")
    return closes

def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"sent": {}}
    data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("sent"), dict):
        raise ValueError("Invalid state.json")
    return data

def save_state(state: dict) -> None:
    today = datetime.now(NY).date()
    state["sent"] = {k: v for k,v in state["sent"].items()
                      if (today - pd.Timestamp(k.split(":",1)[0]).date()).days <= 120}
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2,
                                   sort_keys=True) + "\n", encoding="utf-8")

def run(*, dry_run: bool = False, manual: bool = False) -> int:
    session = today_session(datetime.now(NY), manual)
    if session is None:
        return 0
    state = load_state()
    errors = []
    emitted = 0
    for ticker in TICKERS:
        try:
            signal = check_signal(ticker, fetch_closes(ticker, session))
        except Exception as exc:
            LOG.exception("Ticker check failed: %s", ticker)
            errors.append(f"{ticker}: {exc}")
            continue
        if signal is None:
            LOG.info("%s: no new crossover", ticker)
            continue
        if signal.key in state["sent"]:
            LOG.info("%s: already sent", signal.key)
            continue
        LOG.info("Triggered: %s \n%s", signal.title, signal.body)
        if dry_run:
            continue
        try:
            push_bark(signal.title, signal.body,
                      f"https://finance.yahoo.com/quote/{ticker}/")
        except Exception as exc:
            LOG.exception("Notification failed")
            errors.append(f"Bark {ticker}: {exc}")
            continue
        state["sent"][signal.key] = datetime.now(NY).isoformat()
        save_state(state)
        emitted += 1
    if errors:
        raise RuntimeError("One or more checks failed:\n" + "\n".join(errors))
    LOG.info("%s: pushed %s new signals", session, emitted)
    return emitted

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--manual", action="store_true")
    parser.add_argument("--test-bark", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.test_bark:
        push_bark("✅ 美股策略提醒已连接",
                  "Bark 测试成功。后续收盘确认均线穿越时提醒；不自动交易。")
    else:
        run(dry_run=args.dry_run, manual=args.manual)

if __name__ == "__main__":
    main()
