#!/usr/bin/env python3
"""Bitget futures BTC/ETH bot (signal + optional auto-trade)."""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import ccxt  # type: ignore
except Exception:  # pragma: no cover
    ccxt = None


ALLOWED_SYMBOLS = ("BTC/USDT:USDT", "ETH/USDT:USDT")
STATE_FILE = Path("state.json")
EVENTS_FILE = Path("events.json")


@dataclasses.dataclass
class BotConfig:
    mode: str = "recommend"  # recommend | auto
    timeframe: str = "5m"
    candle_limit: int = 250
    leverage: int = 30
    account_size_override: float = 0.0  # 0이면 거래소 USDT 잔고 사용

    # risk guardrails
    daily_take_profit: float = 0.03
    max_losing_positions: int = 2
    max_daily_drawdown: float = 0.03
    risk_per_trade: float = 0.005
    balance_allocation: float = 0.3  # 기본: 시드 30% 사용
    sl_atr_mult: float = 1.5
    tp_rr_ratio: float = 2.0

    # filters
    rsi_period: int = 14
    ema_fast: int = 20
    ema_slow: int = 50
    atr_period: int = 14
    min_atr_pct: float = 0.002
    breakout_lookback: int = 20
    min_body_atr_ratio: float = 0.2
    max_ema_distance_atr: float = 1.2
    fvg_min_gap_atr: float = 0.10
    signal_score_threshold: float = 3.0
    margin_mode: str = "cross"
    position_mode: str = "oneway"  # oneway | hedge
    allow_other_symbols: bool = False


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
    min_need = max(cfg.ema_slow + 2, cfg.rsi_period + 2, cfg.atr_period + 2, cfg.breakout_lookback + 3)
    if len(candles) < min_need:
        return "HOLD", {"reason": -2.0, "price": candles[-1][4] if candles else 0.0, "rsi": 50.0, "atr_pct": 0.0}

    open_ = [c[1] for c in candles]
    close = [c[4] for c in candles]
    high = [c[2] for c in candles]
    low = [c[3] for c in candles]

    ema_fast = ema(close, cfg.ema_fast)
    ema_slow = ema(close, cfg.ema_slow)
    rsi_v = rsi(close, cfg.rsi_period)
    atr_v = atr(high, low, close, cfg.atr_period)

    last_close = close[-1]
    last_open = open_[-1]
    last_rsi = rsi_v[-1]
    last_atr = atr_v[-1]
    atr_pct = last_atr / last_close if last_close else 0.0

    if atr_pct < cfg.min_atr_pct:
        return "HOLD", {"reason": -1.0, "price": last_close, "rsi": last_rsi, "atr_pct": atr_pct}

    fast_now = ema_fast[-1]
    slow_now = ema_slow[-1]

    trend_up = fast_now > slow_now
    trend_down = fast_now < slow_now

    recent_high = max(high[-(cfg.breakout_lookback + 1):-1])
    recent_low = min(low[-(cfg.breakout_lookback + 1):-1])
    breakout_up = last_close > recent_high
    breakout_down = last_close < recent_low

    body_size = abs(last_close - last_open)
    body_ok = body_size >= (last_atr * cfg.min_body_atr_ratio)
    ema_distance_ok = abs(last_close - fast_now) <= (last_atr * cfg.max_ema_distance_atr)

    # FVG (3-candle inefficiency)
    bullish_fvg_gap = max(0.0, low[-1] - high[-3])
    bearish_fvg_gap = max(0.0, low[-3] - high[-1])
    bullish_fvg = bullish_fvg_gap >= (last_atr * cfg.fvg_min_gap_atr)
    bearish_fvg = bearish_fvg_gap >= (last_atr * cfg.fvg_min_gap_atr)

    # Order-block proxy: previous candle opposite + current candle sweep/break
    bullish_ob = close[-2] < open_[-2] and close[-1] > high[-2]
    bearish_ob = close[-2] > open_[-2] and close[-1] < low[-2]

    rsi_long_ok = 48 <= last_rsi <= 72
    rsi_short_ok = 28 <= last_rsi <= 52

    # 조건 유동 점수화(모든 조건 강제 X)
    long_score = (
        (1.0 if trend_up else 0.0)
        + (1.0 if breakout_up else 0.0)
        + (0.7 if body_ok else 0.0)
        + (0.5 if ema_distance_ok else 0.0)
        + (0.9 if bullish_fvg else 0.0)
        + (0.9 if bullish_ob else 0.0)
        + (0.8 if rsi_long_ok else 0.0)
    )
    short_score = (
        (1.0 if trend_down else 0.0)
        + (1.0 if breakout_down else 0.0)
        + (0.7 if body_ok else 0.0)
        + (0.5 if ema_distance_ok else 0.0)
        + (0.9 if bearish_fvg else 0.0)
        + (0.9 if bearish_ob else 0.0)
        + (0.8 if rsi_short_ok else 0.0)
    )

    threshold = cfg.signal_score_threshold

    if long_score >= threshold and long_score > short_score:
        return "LONG", {
            "price": last_close,
            "rsi": last_rsi,
            "atr": last_atr,
            "atr_pct": atr_pct,
            "fvg": 1.0 if bullish_fvg else 0.0,
            "ob": 1.0 if bullish_ob else 0.0,
            "score": long_score,
            "threshold": threshold,
        }

    if short_score >= threshold and short_score > long_score:
        return "SHORT", {
            "price": last_close,
            "rsi": last_rsi,
            "atr": last_atr,
            "atr_pct": atr_pct,
            "fvg": 1.0 if bearish_fvg else 0.0,
            "ob": 1.0 if bearish_ob else 0.0,
            "score": short_score,
            "threshold": threshold,
        }

    return "HOLD", {
        "price": last_close,
        "rsi": last_rsi,
        "atr": last_atr,
        "atr_pct": atr_pct,
        "long_score": long_score,
        "short_score": short_score,
        "threshold": threshold,
    }


def position_size(
    balance: float,
    entry: float,
    stop: float,
    risk_per_trade: float,
    leverage: int,
    allocation: float,
) -> float:
    # 기본: 시드의 allocation(기본 100%)를 레버리지 반영해 진입 수량 계산
    allocated = max(balance, 0.0) * max(min(allocation, 1.0), 0.0)
    notional = allocated * max(leverage, 1)
    if entry <= 0:
        return 0.0
    qty = notional / entry

    # allocation이 0이거나 계산상 비정상이면 기존 리스크 방식으로 fallback
    if qty <= 0:
        risk_amount = max(balance, 0.0) * max(min(risk_per_trade, 1.0), 0.0)
        unit_risk = abs(entry - stop)
        if unit_risk <= 0:
            return 0.0
        return risk_amount / unit_risk
    return qty


def should_stop(cfg: BotConfig, state: DayState) -> Tuple[bool, str]:
    if state.daily_pnl >= cfg.daily_take_profit:
        return True, f"일일 목표 수익 {cfg.daily_take_profit:.0%} 달성"
    if state.losing_positions >= cfg.max_losing_positions:
        return True, f"손실 포지션 {cfg.max_losing_positions}회 도달"
    if state.daily_pnl <= -cfg.max_daily_drawdown:
        return True, f"일일 최대 손실 {cfg.max_daily_drawdown:.0%} 도달"
    return False, ""


def parse_event_iso8601(value: str) -> datetime:
    """Parse event time string as UTC-aware datetime."""
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_symbols_file(file_path: Path) -> List[str]:
    if not file_path.exists():
        return []
    try:
        raw = file_path.read_text().strip()
    except Exception:
        return []
    if not raw:
        return []

    # JSON 배열 또는 줄단위 텍스트 둘 다 허용
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                out = []
                for item in parsed:
                    if isinstance(item, str) and item.strip():
                        out.append(item.strip())
                return out
        except Exception:
            return []

    out = []
    for line in raw.splitlines():
        item = line.strip()
        if not item or item.startswith("#"):
            continue
        out.append(item)
    return out


def load_block_events(file_path: Path) -> List[dict]:
    if not file_path.exists():
        return []
    try:
        data = json.loads(file_path.read_text())
    except Exception:
        return []

    if isinstance(data, dict):
        events = data.get("events", [])
    elif isinstance(data, list):
        events = data
    else:
        return []

    out: List[dict] = []
    for item in events:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "event")).strip()
        at = item.get("at")
        if not at:
            continue
        try:
            event_time = parse_event_iso8601(str(at))
        except Exception:
            continue
        out.append({"name": name, "at": event_time})
    return out


def in_event_block_window(events: List[dict], before_min: int, after_min: int) -> Tuple[bool, str]:
    now = datetime.now(timezone.utc)
    before = timedelta(minutes=max(before_min, 0))
    after = timedelta(minutes=max(after_min, 0))
    for event in events:
        event_time = event["at"]
        start = event_time - before
        end = event_time + after
        if start <= now <= end:
            return True, event.get("name", "event")
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


def normalize_price(exchange: "ccxt.bitget", symbol: str, price: float) -> float:
    try:
        return float(exchange.price_to_precision(symbol, price))
    except Exception:
        return price


def place_exit_orders(
    exchange: "ccxt.bitget",
    symbol: str,
    entry_side: str,
    qty: float,
    take_profit: float,
    stop_price: float,
    cfg: BotConfig,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Try to place TP/SL reduce-only orders with Bitget/ccxt fallback params.

    Returns (tp_order_id, sl_order_id, error_text).
    """
    close_side = "sell" if entry_side == "buy" else "buy"
    tp = normalize_price(exchange, symbol, take_profit)
    sl = normalize_price(exchange, symbol, stop_price)
    base_params = {"marginMode": cfg.margin_mode, "reduceOnly": True}
    if cfg.position_mode == "oneway":
        base_params["oneWayMode"] = True

    tp_order_id: Optional[str] = None
    sl_order_id: Optional[str] = None
    errors: List[str] = []

    # TP: reduce-only limit
    try:
        tp_order = exchange.create_order(
            symbol=symbol,
            type="limit",
            side=close_side,
            amount=qty,
            price=tp,
            params=base_params,
        )
        tp_order_id = str(tp_order.get("id"))
    except Exception as exc:
        errors.append(f"TP:{format_error(exc)}")

    # SL: stop market, try several param styles for exchange/ccxt variations.
    sl_param_candidates = [
        {**base_params, "stopPrice": sl, "triggerPrice": sl, "closeOnTrigger": True},
        {**base_params, "stopPrice": sl, "closeOnTrigger": True},
        {**base_params, "triggerPrice": sl, "closeOnTrigger": True},
    ]
    for params in sl_param_candidates:
        try:
            sl_order = exchange.create_order(
                symbol=symbol,
                type="market",
                side=close_side,
                amount=qty,
                params=params,
            )
            sl_order_id = str(sl_order.get("id"))
            break
        except Exception as exc:
            errors.append(f"SL:{format_error(exc)}")

    if tp_order_id and sl_order_id:
        return tp_order_id, sl_order_id, None
    return tp_order_id, sl_order_id, " | ".join(errors) if errors else "TP/SL 주문 생성 실패"


def print_state(state: DayState) -> None:
    print(f"[STATE] date={state.date} daily_pnl={state.daily_pnl:.2%} losing_positions={state.losing_positions} trades={state.trades}")


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        _ = resp.read()


def maybe_notify(bot_token: Optional[str], chat_id: Optional[str], text: str) -> None:
    if not bot_token or not chat_id:
        return
    try:
        send_telegram_message(bot_token, chat_id, text)
    except Exception as exc:
        print(f"[WARN] 텔레그램 알림 실패: {exc}")


def format_error(exc: Exception) -> str:
    text = str(exc).strip()
    return text if text else exc.__class__.__name__


def run_once(
    exchange: "ccxt.bitget",
    symbol: str,
    cfg: BotConfig,
    state: DayState,
    confirm_live: bool,
    tg_bot_token: Optional[str],
    tg_chat_id: Optional[str],
    events: List[dict],
    block_before_min: int,
    block_after_min: int,
) -> None:
    if (not cfg.allow_other_symbols) and symbol not in ALLOWED_SYMBOLS:
        print(f"[SKIP] 허용되지 않은 종목: {symbol} (기본 허용: BTC/ETH, 확장: --allow-other-symbols)")
        return

    stop, reason = should_stop(cfg, state)
    if stop:
        message = f"[STOP] {reason}. 오늘 거래 종료."
        print(message)
        maybe_notify(tg_bot_token, tg_chat_id, message)
        return

    blocked, event_name = in_event_block_window(events, block_before_min, block_after_min)
    if blocked:
        print(f"[{symbol}] SKIP | 뉴스/이벤트 필터 활성화: {event_name} 전후 차단 구간")
        return

    try:
        candles = exchange.fetch_ohlcv(symbol, timeframe=cfg.timeframe, limit=cfg.candle_limit)
    except Exception as exc:
        err = format_error(exc)
        print(f"[{symbol}] DATA FAIL | {err}")
        maybe_notify(tg_bot_token, tg_chat_id, f"[{symbol}] 시세 조회 실패: {err}")
        return
    sig, meta = calc_signal(candles, cfg)
    price = meta["price"]

    if sig == "HOLD":
        print(
            f"[{symbol}] HOLD | price={price:.2f}, rsi={meta.get('rsi', 0):.2f}, atr_pct={meta.get('atr_pct', 0):.4f} "
            f"long_score={meta.get('long_score', 0):.2f} short_score={meta.get('short_score', 0):.2f} "
            f"threshold={meta.get('threshold', 0):.2f}"
        )
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

    try:
        exchange_balance = float(exchange.fetch_balance().get("USDT", {}).get("free", 0.0))
    except Exception as exc:
        err = format_error(exc)
        print(f"[{symbol}] BALANCE FAIL | {err}")
        maybe_notify(tg_bot_token, tg_chat_id, f"[{symbol}] 잔고 조회 실패: {err}")
        return
    effective_balance = cfg.account_size_override if cfg.account_size_override > 0 else exchange_balance
    risk_usdt = effective_balance * cfg.risk_per_trade
    qty = position_size(effective_balance, price, stop_price, cfg.risk_per_trade, cfg.leverage, cfg.balance_allocation)
    qty = normalize_amount(exchange, symbol, qty)

    if qty <= 0:
        print(f"[{symbol}] SKIP | 계산 수량이 최소 주문 수량 미만입니다.")
        return

    structure = f"FVG={int(meta.get('fvg', 0))} OB={int(meta.get('ob', 0))}"
    signal_message = (
        f"[{symbol}] {sig} signal | entry={price:.2f} sl={stop_price:.2f} tp={take_profit:.2f} "
        f"size={qty:.6f} lev={cfg.leverage} alloc={cfg.balance_allocation:.0%} base_capital={effective_balance:.2f}USDT risk={risk_usdt:.2f}USDT "
        f"score={meta.get('score', 0):.2f}/{meta.get('threshold', 0):.2f} {structure}"
    )
    print(signal_message)
    maybe_notify(tg_bot_token, tg_chat_id, signal_message)

    if cfg.mode == "auto":
        if not confirm_live:
            print("  -> 안내: 현재 설정은 auto 모드에서 신호 발생 시 바로 주문합니다(확인 플래그 미사용).")
        params = {"marginMode": cfg.margin_mode}
        # Bitget one-way(unilateral) 계정에서는 oneWayMode=true 파라미터가 필요할 수 있음.
        if cfg.position_mode == "oneway":
            params["oneWayMode"] = True

        try:
            order = exchange.create_order(symbol=symbol, type="market", side=side, amount=qty, params=params)
        except Exception as exc:
            msg = format_error(exc)
            if cfg.position_mode == "oneway" and ("40774" in msg or "unilateral" in msg.lower()):
                # 일부 계정/ccxt 조합에서는 문자열 oneWayMode + tradeSide=open이 필요.
                retry_params = {"marginMode": cfg.margin_mode, "oneWayMode": "true", "tradeSide": "open"}
                try:
                    order = exchange.create_order(symbol=symbol, type="market", side=side, amount=qty, params=retry_params)
                except Exception as retry_exc:
                    retry_msg = format_error(retry_exc)
                    print(f"[{symbol}] ORDER FAIL | {retry_msg}")
                    print("  -> 해결 가이드: 비트겟 포지션 모드를 '단방향(One-way)'으로 맞추거나, --position-mode 값을 확인하세요.")
                    maybe_notify(tg_bot_token, tg_chat_id, f"[{symbol}] 주문 실패: {retry_msg}")
                    return
            else:
                print(f"[{symbol}] ORDER FAIL | {msg}")
                maybe_notify(tg_bot_token, tg_chat_id, f"[{symbol}] 주문 실패: {msg}")
                return
        state.trades += 1
        order_message = f"  -> order_id={order.get('id')}"
        print(order_message)
        maybe_notify(tg_bot_token, tg_chat_id, f"[{symbol}] 실주문 완료 {order_message}")

        tp_order_id, sl_order_id, exit_err = place_exit_orders(
            exchange=exchange,
            symbol=symbol,
            entry_side=side,
            qty=qty,
            take_profit=take_profit,
            stop_price=stop_price,
            cfg=cfg,
        )

        if tp_order_id and sl_order_id:
            exit_message = f"  -> exit_orders tp_id={tp_order_id} sl_id={sl_order_id}"
            print(exit_message)
            maybe_notify(tg_bot_token, tg_chat_id, f"[{symbol}] 익절/손절 주문 등록 완료 {exit_message}")
        else:
            warn_msg = f"[{symbol}] EXIT ORDER WARN | TP/SL 주문 일부 또는 전체 실패"
            print(warn_msg)
            if exit_err:
                print(f"  -> detail: {exit_err}")
            maybe_notify(tg_bot_token, tg_chat_id, f"[{symbol}] 익절/손절 주문 등록 실패: {exit_err or 'unknown'}")
    else:
        print("  -> recommendation 모드: 주문 미실행")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bitget BTC/ETH futures assistant bot")
    parser.add_argument("--mode", choices=["recommend", "auto"], default="recommend")
    parser.add_argument("--symbols", nargs="+", default=list(ALLOWED_SYMBOLS))
    parser.add_argument("--symbols-file", default="", help="심볼 목록 파일(.txt/.json). 줄단위 또는 JSON 배열")
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--loop", action="store_true", help="지속 실행")
    parser.add_argument("--interval", type=int, default=60, help="loop 모드 폴링 간격(초)")
    parser.add_argument("--status", action="store_true", help="오늘 상태(state.json)만 출력")
    parser.add_argument("--reset-day", action="store_true", help="오늘 상태(state.json) 초기화")
    parser.add_argument("--confirm-live", action="store_true", help="auto 모드 실주문 확인 플래그")
    parser.add_argument("--show-config", action="store_true", help="현재 리스크 설정값 출력")
    parser.add_argument("--account-size", type=float, default=0.0, help="포지션 계산용 시드(USDT). 0이면 거래소 잔고 사용")
    parser.add_argument("--risk-per-trade", type=float, default=0.005, help="1회 트레이드 리스크 비율(예: 0.005=0.5%%)")
    parser.add_argument("--balance-allocation", type=float, default=0.3, help="시드 사용 비율(기본 0.3=30%%)")
    parser.add_argument("--telegram-bot-token", default=os.getenv("TELEGRAM_BOT_TOKEN", ""), help="텔레그램 봇 토큰")
    parser.add_argument("--telegram-chat-id", default=os.getenv("TELEGRAM_CHAT_ID", ""), help="텔레그램 chat id")
    parser.add_argument("--events-file", default=str(EVENTS_FILE), help="CPI/FOMC 등 이벤트 파일(JSON)")
    parser.add_argument("--block-before-min", type=int, default=60, help="이벤트 이전 차단 분")
    parser.add_argument("--block-after-min", type=int, default=60, help="이벤트 이후 차단 분")
    parser.add_argument("--margin-mode", choices=["cross", "isolated"], default="cross", help="주문 마진 모드")
    parser.add_argument("--position-mode", choices=["oneway", "hedge"], default="oneway", help="비트겟 포지션 모드")
    parser.add_argument("--allow-other-symbols", action="store_true", help="BTC/ETH 외 심볼 허용")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = BotConfig(
        mode=args.mode,
        timeframe=args.timeframe,
        account_size_override=max(args.account_size, 0.0),
        risk_per_trade=max(min(args.risk_per_trade, 1.0), 0.0),
        balance_allocation=max(min(args.balance_allocation, 1.0), 0.0),
        margin_mode=args.margin_mode,
        position_mode=args.position_mode,
        allow_other_symbols=args.allow_other_symbols or bool(args.symbols_file),
    )

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

    symbols = list(args.symbols)
    if args.symbols_file:
        file_symbols = load_symbols_file(Path(args.symbols_file))
        if file_symbols:
            merged = []
            for sym in symbols + file_symbols:
                if sym not in merged:
                    merged.append(sym)
            symbols = merged
        else:
            print(f"[WARN] symbols-file 로드 실패 또는 비어있음: {args.symbols_file}")

    exchange = make_exchange()
    events = load_block_events(Path(args.events_file))
    if events:
        print(f"[INFO] 이벤트 {len(events)}개 로드, 차단 윈도우: -{max(args.block_before_min,0)}m/+{max(args.block_after_min,0)}m")
    if args.telegram_bot_token and args.telegram_chat_id:
        maybe_notify(args.telegram_bot_token, args.telegram_chat_id, f"봇 시작: mode={cfg.mode}, timeframe={cfg.timeframe}")

    if args.loop:
        while True:
            state = load_state()
            print_state(state)
            for symbol in symbols:
                try:
                    run_once(exchange, symbol, cfg, state, args.confirm_live, args.telegram_bot_token or None, args.telegram_chat_id or None, events, max(args.block_before_min,0), max(args.block_after_min,0))
                except Exception as exc:
                    err = format_error(exc)
                    print(f"[{symbol}] RUN FAIL | {err}")
                    maybe_notify(args.telegram_bot_token or None, args.telegram_chat_id or None, f"[{symbol}] 실행 실패: {err}")
            save_state(state)
            time.sleep(args.interval)
    else:
        print_state(state)
        for symbol in symbols:
            try:
                run_once(exchange, symbol, cfg, state, args.confirm_live, args.telegram_bot_token or None, args.telegram_chat_id or None, events, max(args.block_before_min,0), max(args.block_after_min,0))
            except Exception as exc:
                err = format_error(exc)
                print(f"[{symbol}] RUN FAIL | {err}")
                maybe_notify(args.telegram_bot_token or None, args.telegram_chat_id or None, f"[{symbol}] 실행 실패: {err}")
        save_state(state)


if __name__ == "__main__":
    main()
