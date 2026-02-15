#!/usr/bin/env python3
"""Bitget futures BTC/ETH bot (signal + optional auto-trade)."""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import ccxt  # type: ignore
except Exception:  # pragma: no cover
    ccxt = None


ALLOWED_SYMBOLS = ("BTC/USDT:USDT", "ETH/USDT:USDT")
STATE_FILE = Path("state.json")


@dataclasses.dataclass
class BotConfig:
    mode: str = "recommend"  # recommend | auto
    timeframe: str = "15m"
    candle_limit: int = 250
    leverage: int = 3

    # risk guardrails
    daily_take_profit: float = 0.10
    max_losing_positions: int = 3
    max_daily_drawdown: float = 0.05
    risk_per_trade: float = 0.01
    sl_atr_mult: float = 1.5
    tp_rr_ratio: float = 2.0

    # filters
    rsi_period: int = 14
    ema_fast: int = 20
    ema_slow: int = 50
    atr_period: int = 14
    min_atr_pct: float = 0.002


@dataclasses.dataclass
class DayState:
    date: str
    daily_pnl: float = 0.0
    losing_positions: int = 0
    trades: int = 0


def utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_state() -> DayState:
    if not STATE_FILE.exists():
        return DayState(date=utc_date())
    data = json.loads(STATE_FILE.read_text())
    state = DayState(**data)
    if state.date != utc_date():
        return DayState(date=utc_date())
    return state


def save_state(state: DayState) -> None:
    STATE_FILE.write_text(json.dumps(dataclasses.asdict(state), indent=2, ensure_ascii=False))


def reset_state() -> DayState:
    state = DayState(date=utc_date())
    save_state(state)
    return state


def ema(values: List[float], period: int) -> List[float]:
    k = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(values: List[float], period: int = 14) -> List[float]:
    gains = [0.0]
    losses = [0.0]
    for i in range(1, len(values)):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    if len(values) <= period + 1:
        return [50.0] * len(values)

    avg_gain = sum(gains[1 : period + 1]) / period
    avg_loss = sum(losses[1 : period + 1]) / period

    out = [50.0] * len(values)
    for i in range(period + 1, len(values)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss else math.inf
        out[i] = 100 - (100 / (1 + rs))
    return out


def atr(high: List[float], low: List[float], close: List[float], period: int = 14) -> List[float]:
    tr = [high[0] - low[0]]
    for i in range(1, len(high)):
        tr.append(max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])))

    out = [tr[0]]
    for i in range(1, len(tr)):
        out.append((out[-1] * (period - 1) + tr[i]) / period)
    return out


def calc_signal(candles: List[List[float]], cfg: BotConfig) -> Tuple[str, Dict[str, float]]:
    min_need = max(cfg.ema_slow + 2, cfg.rsi_period + 2, cfg.atr_period + 2)
    if len(candles) < min_need:
        return "HOLD", {"reason": -2.0, "price": candles[-1][4] if candles else 0.0, "rsi": 50.0, "atr_pct": 0.0}

    close = [c[4] for c in candles]
    high = [c[2] for c in candles]
    low = [c[3] for c in candles]

    ema_fast = ema(close, cfg.ema_fast)
    ema_slow = ema(close, cfg.ema_slow)
    rsi_v = rsi(close, cfg.rsi_period)
    atr_v = atr(high, low, close, cfg.atr_period)

    last_close = close[-1]
    last_rsi = rsi_v[-1]
    last_atr = atr_v[-1]
    atr_pct = last_atr / last_close if last_close else 0.0

    if atr_pct < cfg.min_atr_pct:
        return "HOLD", {"reason": -1.0, "price": last_close, "rsi": last_rsi, "atr_pct": atr_pct}

    fast_now, fast_prev = ema_fast[-1], ema_fast[-2]
    slow_now, slow_prev = ema_slow[-1], ema_slow[-2]

    cross_up = fast_prev <= slow_prev and fast_now > slow_now
    cross_down = fast_prev >= slow_prev and fast_now < slow_now

    if cross_up and 45 <= last_rsi <= 70:
        return "LONG", {"price": last_close, "rsi": last_rsi, "atr": last_atr, "atr_pct": atr_pct}
    if cross_down and 30 <= last_rsi <= 55:
        return "SHORT", {"price": last_close, "rsi": last_rsi, "atr": last_atr, "atr_pct": atr_pct}

    return "HOLD", {"price": last_close, "rsi": last_rsi, "atr": last_atr, "atr_pct": atr_pct}


def position_size(balance: float, entry: float, stop: float, risk_per_trade: float) -> float:
    risk_amount = max(balance, 0.0) * risk_per_trade
    unit_risk = abs(entry - stop)
    if unit_risk <= 0:
        return 0.0
    return risk_amount / unit_risk


def should_stop(cfg: BotConfig, state: DayState) -> Tuple[bool, str]:
    if state.daily_pnl >= cfg.daily_take_profit:
        return True, f"일일 목표 수익 {cfg.daily_take_profit:.0%} 달성"
    if state.losing_positions >= cfg.max_losing_positions:
        return True, f"손실 포지션 {cfg.max_losing_positions}회 도달"
    if state.daily_pnl <= -cfg.max_daily_drawdown:
        return True, f"일일 최대 손실 {cfg.max_daily_drawdown:.0%} 도달"
    return False, ""


def make_exchange() -> "ccxt.bitget":
    if ccxt is None:
        raise RuntimeError("ccxt가 설치되어 있지 않습니다. `pip install -r requirements.txt` 실행 필요")

    key = os.getenv("BITGET_API_KEY", "")
    secret = os.getenv("BITGET_API_SECRET", "")
    password = os.getenv("BITGET_API_PASSPHRASE", "")

    if not key or not secret or not password:
        raise RuntimeError("API 키 환경변수(BITGET_API_KEY/SECRET/PASSPHRASE)를 설정하세요.")

    ex = ccxt.bitget(
        {
            "apiKey": key,
            "secret": secret,
            "password": password,
            "options": {"defaultType": "swap"},
            "enableRateLimit": True,
        }
    )
    ex.load_markets()
    return ex


def normalize_amount(exchange: "ccxt.bitget", symbol: str, qty: float) -> float:
    market = exchange.market(symbol)
    min_amount = market.get("limits", {}).get("amount", {}).get("min")
    amt = float(exchange.amount_to_precision(symbol, qty))
    if min_amount is not None and amt < float(min_amount):
        return 0.0
    return amt


def print_state(state: DayState) -> None:
    print(f"[STATE] date={state.date} daily_pnl={state.daily_pnl:.2%} losing_positions={state.losing_positions} trades={state.trades}")


def run_once(exchange: "ccxt.bitget", symbol: str, cfg: BotConfig, state: DayState, confirm_live: bool) -> None:
    if symbol not in ALLOWED_SYMBOLS:
        print(f"[SKIP] 허용되지 않은 종목: {symbol}")
        return

    stop, reason = should_stop(cfg, state)
    if stop:
        print(f"[STOP] {reason}. 오늘 거래 종료.")
        return

    candles = exchange.fetch_ohlcv(symbol, timeframe=cfg.timeframe, limit=cfg.candle_limit)
    sig, meta = calc_signal(candles, cfg)
    price = meta["price"]

    if sig == "HOLD":
        print(f"[{symbol}] HOLD | price={price:.2f}, rsi={meta.get('rsi', 0):.2f}, atr_pct={meta.get('atr_pct', 0):.4f}")
        return

    atr_v = meta["atr"]
    if sig == "LONG":
        stop_price = price - atr_v * cfg.sl_atr_mult
        take_profit = price + (price - stop_price) * cfg.tp_rr_ratio
        side = "buy"
    else:
        stop_price = price + atr_v * cfg.sl_atr_mult
        take_profit = price - (stop_price - price) * cfg.tp_rr_ratio
        side = "sell"

    balance = exchange.fetch_balance().get("USDT", {}).get("free", 0.0)
    qty = position_size(float(balance), price, stop_price, cfg.risk_per_trade)
    qty = normalize_amount(exchange, symbol, qty)

    if qty <= 0:
        print(f"[{symbol}] SKIP | 계산 수량이 최소 주문 수량 미만입니다.")
        return

    print(
        f"[{symbol}] {sig} signal | entry={price:.2f} sl={stop_price:.2f} tp={take_profit:.2f} "
        f"size={qty:.6f} lev={cfg.leverage}"
    )

    if cfg.mode == "auto":
        if not confirm_live:
            print("  -> auto 모드 차단: --confirm-live 를 추가해야 실주문합니다.")
            return
        params = {"marginMode": "cross"}
        order = exchange.create_order(symbol=symbol, type="market", side=side, amount=qty, params=params)
        state.trades += 1
        print(f"  -> order_id={order.get('id')}")
    else:
        print("  -> recommendation 모드: 주문 미실행")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bitget BTC/ETH futures assistant bot")
    parser.add_argument("--mode", choices=["recommend", "auto"], default="recommend")
    parser.add_argument("--symbols", nargs="+", default=list(ALLOWED_SYMBOLS))
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--loop", action="store_true", help="지속 실행")
    parser.add_argument("--interval", type=int, default=60, help="loop 모드 폴링 간격(초)")
    parser.add_argument("--status", action="store_true", help="오늘 상태(state.json)만 출력")
    parser.add_argument("--reset-day", action="store_true", help="오늘 상태(state.json) 초기화")
    parser.add_argument("--confirm-live", action="store_true", help="auto 모드 실주문 확인 플래그")
    parser.add_argument("--show-config", action="store_true", help="현재 리스크 설정값 출력")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = BotConfig(mode=args.mode, timeframe=args.timeframe)

    if args.show_config:
        print(json.dumps(dataclasses.asdict(cfg), indent=2, ensure_ascii=False))

    if args.reset_day:
        state = reset_state()
        print("[OK] state.json 초기화 완료")
        print_state(state)
        if args.status:
            return

    state = load_state()
    if args.status:
        print_state(state)
        return

    exchange = make_exchange()

    if args.loop:
        while True:
            state = load_state()
            print_state(state)
            for symbol in args.symbols:
                run_once(exchange, symbol, cfg, state, args.confirm_live)
            save_state(state)
            time.sleep(args.interval)
    else:
        print_state(state)
        for symbol in args.symbols:
            run_once(exchange, symbol, cfg, state, args.confirm_live)
        save_state(state)


if __name__ == "__main__":
    main()
