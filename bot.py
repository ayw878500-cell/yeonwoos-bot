import logging
import time
from dataclasses import dataclass
from datetime import date

from bitget_client import BitgetClient
from config import Settings, load_settings
from risk import calc_position_size
from strategy import EmaCrossStrategy
from telegram_notifier import TelegramNotifier


@dataclass
class Position:
    side: str
    entry_price: float
    margin_usdt: float
    stop_loss: float
    take_profit: float


def setup_logger() -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    return logging.getLogger("bitget-bot")


def close_side(side: str) -> str:
    return "sell" if side == "buy" else "buy"


def pnl_pct(side: str, entry: float, current: float) -> float:
    if side == "buy":
        return (current - entry) / entry
    return (entry - current) / entry


def main() -> None:
    settings = load_settings()
    logger = setup_logger()
    notifier = TelegramNotifier(
        settings.telegram_bot_token,
        settings.telegram_chat_id,
        settings.telegram_enabled,
    )

    client = BitgetClient(
        settings.base_url,
        settings.api_key,
        settings.api_secret,
        settings.api_passphrase,
    )
    strategy = EmaCrossStrategy(fast=settings.fast_ma, slow=settings.slow_ma)

    day = date.today()
    day_start_equity = 0.0
    stoploss_count = 0
    last_signal_ts = 0.0
    position: Position | None = None

    logger.info("[START] DRY_RUN=%s symbol=%s", settings.dry_run, settings.symbol)
    notifier.send(f"🚀 봇 시작: {settings.symbol} / DRY_RUN={settings.dry_run}")

    while True:
        try:
            if date.today() != day:
                day = date.today()
                day_start_equity = 0.0
                stoploss_count = 0
                position = None
                logger.info("[DAILY_RESET] 일일 통계 초기화")
                notifier.send("🗓️ 일자 변경: 일일 통계 초기화")

            price = client.ticker_price(settings.symbol, settings.product_type)
            equity = client.account_equity(settings.symbol, settings.product_type, settings.margin_coin)

            if day_start_equity == 0.0:
                day_start_equity = equity

            daily_return = (equity - day_start_equity) / day_start_equity if day_start_equity > 0 else 0.0

            if daily_return >= settings.daily_target_pct:
                logger.info("[STOP_DAY] 일일 목표 달성: %.2f%%", daily_return * 100)
                notifier.send(f"✅ 일일 목표 달성: {daily_return*100:.2f}% -> 오늘 거래 종료")
                time.sleep(settings.loop_interval_sec)
                continue

            if stoploss_count >= settings.max_daily_stoploss:
                logger.info("[STOP_DAY] 일일 손절 횟수 초과: %s", stoploss_count)
                notifier.send(f"🛑 손절 {stoploss_count}회 도달 -> 오늘 거래 종료")
                time.sleep(settings.loop_interval_sec)
                continue

            if position is not None:
                should_close = False
                reason = ""
                if position.side == "buy":
                    if price <= position.stop_loss:
                        should_close = True
                        reason = "SL"
                    elif price >= position.take_profit:
                        should_close = True
                        reason = "TP"
                else:
                    if price >= position.stop_loss:
                        should_close = True
                        reason = "SL"
                    elif price <= position.take_profit:
                        should_close = True
                        reason = "TP"

                if should_close:
                    trade_pnl = pnl_pct(position.side, position.entry_price, price)
                    if not settings.dry_run:
                        client.place_market_order(
                            symbol=settings.symbol,
                            product_type=settings.product_type,
                            margin_coin=settings.margin_coin,
                            side=close_side(position.side),
                            size_usdt=position.margin_usdt,
                            leverage=settings.leverage,
                        )
                    if reason == "SL":
                        stoploss_count += 1
                    notifier.send(
                        f"📉 청산 {reason} | side={position.side} | entry={position.entry_price:.2f} | close={price:.2f} | pnl={trade_pnl*100:.2f}%"
                    )
                    logger.info("[CLOSE] %s pnl=%.2f%%", reason, trade_pnl * 100)
                    position = None

                time.sleep(settings.loop_interval_sec)
                continue

            signal = strategy.update(price)
            if not signal:
                time.sleep(settings.loop_interval_sec)
                continue

            if (time.time() - last_signal_ts) < settings.signal_cooldown_sec:
                time.sleep(settings.loop_interval_sec)
                continue

            margin_size = calc_position_size(
                equity_usdt=equity,
                entry_fraction=settings.entry_fraction,
                leverage=settings.leverage,
                entry_price=price,
                stop_loss_pct=settings.stop_loss_pct,
                risk_per_trade=settings.risk_per_trade,
            )

            if margin_size < settings.min_order_margin_usdt:
                logger.info("[SKIP] 주문금액 부족: %.4f", margin_size)
                time.sleep(settings.loop_interval_sec)
                continue

            if signal == "buy":
                stop_loss = price * (1 - settings.stop_loss_pct)
                take_profit = price * (1 + settings.take_profit_pct)
            else:
                stop_loss = price * (1 + settings.stop_loss_pct)
                take_profit = price * (1 - settings.take_profit_pct)

            if not settings.dry_run:
                client.place_market_order(
                    symbol=settings.symbol,
                    product_type=settings.product_type,
                    margin_coin=settings.margin_coin,
                    side=signal,
                    size_usdt=margin_size,
                    leverage=settings.leverage,
                )

            position = Position(
                side=signal,
                entry_price=price,
                margin_usdt=margin_size,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
            last_signal_ts = time.time()

            notifier.send(
                f"📌 진입 | side={signal} | price={price:.2f} | margin={margin_size:.2f} | lev={settings.leverage}x | sl={stop_loss:.2f} | tp={take_profit:.2f}"
            )
            logger.info(
                "[OPEN] side=%s price=%.2f margin=%.2f sl=%.2f tp=%.2f",
                signal,
                price,
                margin_size,
                stop_loss,
                take_profit,
            )

        except Exception as exc:
            logger.exception("[ERROR] %s", exc)
            notifier.send(f"⚠️ 에러 발생: {exc}")

        time.sleep(settings.loop_interval_sec)


if __name__ == "__main__":
    main()
