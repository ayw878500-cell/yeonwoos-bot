import logging
import time
from datetime import date

from bitget_client import BitgetClient
from config import Settings, load_settings
from risk import calc_position_size, make_plan
from strategy import EmaCrossStrategy


def setup_logger() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    return logging.getLogger("bitget-bot")


def can_order(settings: Settings, last_order_ts: float, orders_today: int) -> tuple[bool, str]:
    if settings.max_orders_per_day <= orders_today:
        return False, "max_orders_per_day limit"
    if last_order_ts > 0 and (time.time() - last_order_ts) < settings.signal_cooldown_sec:
        return False, "signal cooldown"
    return True, "ok"


def main() -> None:
    settings = load_settings()
    logger = setup_logger()

    client = BitgetClient(
        settings.base_url,
        settings.api_key,
        settings.api_secret,
        settings.api_passphrase,
    )
    strategy = EmaCrossStrategy(fast=20, slow=60)

    today = date.today()
    orders_today = 0
    last_order_ts = 0.0
    consecutive_errors = 0

    logger.info(
        "[START] bot running... DRY_RUN=%s ARMED_TRADING=%s",
        settings.dry_run,
        settings.armed_trading,
    )

    while True:
        try:
            if date.today() != today:
                today = date.today()
                orders_today = 0
                logger.info("[DAILY_RESET] orders_today reset")

            price = client.ticker_price(settings.symbol, settings.product_type)
            signal = strategy.update(price)
            if not signal:
                consecutive_errors = 0
                time.sleep(settings.loop_interval_sec)
                continue

            equity_usdt = client.account_equity(
                settings.symbol,
                settings.product_type,
                settings.margin_coin,
            )

            margin_size = calc_position_size(
                equity_usdt=equity_usdt,
                entry_fraction=settings.entry_fraction,
                leverage=settings.leverage,
                entry_price=price,
                stop_loss_pct=settings.stop_loss_pct,
                risk_per_trade=settings.risk_per_trade,
            )

            if margin_size < settings.min_order_margin_usdt:
                logger.info(
                    "[SKIP] margin %.4f below MIN_ORDER_MARGIN_USDT %.4f",
                    margin_size,
                    settings.min_order_margin_usdt,
                )
                consecutive_errors = 0
                time.sleep(settings.loop_interval_sec)
                continue

            allowed, reason = can_order(settings, last_order_ts, orders_today)
            if not allowed:
                logger.info("[SKIP] order blocked: %s", reason)
                consecutive_errors = 0
                time.sleep(settings.loop_interval_sec)
                continue

            plan = make_plan(
                side=signal,
                entry_price=price,
                size_usdt=margin_size,
                stop_loss_pct=settings.stop_loss_pct,
                take_profit_pct=settings.take_profit_pct,
            )
            logger.info(
                "[SIGNAL] side=%s price=%.2f equity=%.2f margin=%.4f sl=%.2f tp=%.2f",
                plan.side,
                price,
                equity_usdt,
                plan.size_usdt,
                plan.stop_loss,
                plan.take_profit,
            )

            if settings.dry_run:
                logger.info("[DRY_RUN] order skipped")
            else:
                result = client.place_market_order(
                    symbol=settings.symbol,
                    product_type=settings.product_type,
                    margin_coin=settings.margin_coin,
                    side=signal,
                    size_usdt=margin_size,
                    leverage=settings.leverage,
                )
                orders_today += 1
                last_order_ts = time.time()
                logger.info("[ORDER] %s", result)

            consecutive_errors = 0

        except Exception as exc:
            consecutive_errors += 1
            logger.exception("[ERROR] %s", exc)
            if consecutive_errors >= settings.max_consecutive_errors:
                logger.error(
                    "[CIRCUIT_BREAKER] %s consecutive errors. sleeping %ss",
                    consecutive_errors,
                    settings.error_cooldown_sec,
                )
                time.sleep(settings.error_cooldown_sec)
                consecutive_errors = 0

        time.sleep(settings.loop_interval_sec)


if __name__ == "__main__":
    main()
