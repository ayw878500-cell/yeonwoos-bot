import logging
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from bitget_client import BitgetClient, BitgetClientError
from config import Settings, load_settings
from risk import calc_position_size
from strategy import MultiIndicatorStrategy
from telegram_notifier import TelegramNotifier


@dataclass
class Position:
    side: str
    entry_price: float
    margin_usdt: float
    stop_loss: float
    take_profit: float


@dataclass
class DailyStats:
    entries: int = 0
    closes: int = 0
    win_count: int = 0
    loss_count: int = 0
    skipped_signals: int = 0


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("bitget-bot")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    Path("logs").mkdir(parents=True, exist_ok=True)
    file_handler = TimedRotatingFileHandler(
        filename="logs/bot.log",
        when="midnight",
        backupCount=14,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return logger


def close_side(side: str) -> str:
    return "sell" if side == "buy" else "buy"


def pnl_pct(side: str, entry: float, current: float) -> float:
    if side == "buy":
        return (current - entry) / entry
    return (entry - current) / entry


def daily_report_text(settings: Settings, stats: DailyStats, daily_return: float, stoploss_count: int) -> str:
    win_rate = (stats.win_count / stats.closes * 100) if stats.closes else 0.0
    suggestions: list[str] = []

    if win_rate < 45 and stats.closes >= 3:
        suggestions.append("승률이 낮음: MIN_ENTRY_CONDITIONS를 3으로 올리거나 손절폭 축소 검토")
    if stoploss_count >= settings.max_daily_stoploss:
        suggestions.append("손절 제한 도달: 다음날 포지션 크기/신호 강도 보수화 권장")
    if daily_return < 0:
        suggestions.append("일일 손익 음수: 3m 비중을 줄이고 5m/15m 추세 우선 확인 권장")
    if not suggestions:
        suggestions.append("현재 설정 유지 가능. 로그에서 진입 사유(reasons) 일관성 점검")

    return (
        f"📊 일일 리포트\n"
        f"- Symbol: {settings.symbol}\n"
        f"- 진입: {stats.entries}회 / 청산: {stats.closes}회\n"
        f"- 승/패: {stats.win_count}/{stats.loss_count} (승률 {win_rate:.1f}%)\n"
        f"- 손절횟수: {stoploss_count}/{settings.max_daily_stoploss}\n"
        f"- 스킵신호: {stats.skipped_signals}회\n"
        f"- 일일수익률: {daily_return*100:.2f}%\n"
        f"- 보완사항: {' | '.join(suggestions)}"
    )




def wait_for_bitget_connection(
    client: BitgetClient,
    settings: Settings,
    logger: logging.Logger,
    notifier: TelegramNotifier,
) -> None:
    logger.info("[CHECK] 비트겟 API 연결 점검 시작")
    delay = 2
    while True:
        try:
            client.ping()
            equity_check = client.validate_account_access(
                settings.symbol,
                settings.product_type,
                settings.margin_coin,
            )
            logger.info("[CHECK] 비트겟 API 연결 확인 완료 | equity=%.4f", equity_check)
            notifier.send(f"✅ 비트겟 연동 확인 완료 | equity={equity_check:.4f} {settings.margin_coin}")
            return
        except BitgetClientError as exc:
            logger.warning("[CHECK_RETRY] 연결 점검 실패: %s | %ss 후 재시도", exc, delay)
            time.sleep(delay)
            delay = min(delay * 2, 30)

def main() -> None:
    settings = load_settings()
    logger = setup_logger()
    notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id, settings.telegram_enabled)

    client = BitgetClient(settings.base_url, settings.api_key, settings.api_secret, settings.api_passphrase)
    strategy = MultiIndicatorStrategy(min_conditions=settings.min_entry_conditions)

    wait_for_bitget_connection(client, settings, logger, notifier)

    day = date.today()
    day_start_equity = 0.0
    stoploss_count = 0
    last_signal_ts = 0.0
    last_report_date: date | None = None
    position: Position | None = None
    stats = DailyStats()
    error_backoff_sec = settings.loop_interval_sec

    logger.info("[START] DRY_RUN=%s symbol=%s", settings.dry_run, settings.symbol)
    notifier.send(f"🚀 봇 시작: {settings.symbol} / DRY_RUN={settings.dry_run}")

    while True:
        try:
            if date.today() != day:
                day = date.today()
                day_start_equity = 0.0
                stoploss_count = 0
                position = None
                stats = DailyStats()
                last_report_date = None
                logger.info("[DAILY_RESET] 일일 통계 초기화")

            candles_3m = client.candles(settings.symbol, settings.product_type, "3m", limit=300)
            candles_5m = client.candles(settings.symbol, settings.product_type, "5m", limit=300)
            candles_15m = client.candles(settings.symbol, settings.product_type, "15m", limit=300)

            price = candles_5m["closes"][-1]
            equity = client.account_equity(settings.symbol, settings.product_type, settings.margin_coin)

            if day_start_equity == 0.0:
                day_start_equity = equity
            daily_return = (equity - day_start_equity) / day_start_equity if day_start_equity > 0 else 0.0
            error_backoff_sec = settings.loop_interval_sec

            now_utc = datetime.now(UTC)
            if (
                now_utc.hour == settings.report_hour_utc
                and now_utc.minute == 0
                and last_report_date != now_utc.date()
            ):
                report = daily_report_text(settings, stats, daily_return, stoploss_count)
                logger.info("[DAILY_REPORT] %s", report.replace("\n", " | "))
                notifier.send(report)
                last_report_date = now_utc.date()

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
                        stats.loss_count += 1
                    else:
                        stats.win_count += 1
                    stats.closes += 1
                    notifier.send(
                        f"📉 청산 {reason} | side={position.side} | entry={position.entry_price:.2f} | close={price:.2f} | pnl={trade_pnl*100:.2f}%"
                    )
                    logger.info("[CLOSE] %s pnl=%.2f%%", reason, trade_pnl * 100)
                    position = None

                time.sleep(settings.loop_interval_sec)
                continue

            signal = strategy.evaluate(
                closes=candles_5m["closes"],
                highs=candles_5m["highs"],
                lows=candles_5m["lows"],
                volumes=candles_5m["volumes"],
            )
            if not signal:
                time.sleep(settings.loop_interval_sec)
                continue

            trend_3m = strategy.trend_direction(candles_3m["closes"])
            trend_5m = strategy.trend_direction(candles_5m["closes"])
            trend_15m = strategy.trend_direction(candles_15m["closes"])

            if not (trend_5m == trend_15m == signal.side):
                logger.info(
                    "[SKIP] 추세 불일치(5m/15m 기준) signal=%s trend3=%s trend5=%s trend15=%s",
                    signal.side,
                    trend_3m,
                    trend_5m,
                    trend_15m,
                )
                stats.skipped_signals += 1
                time.sleep(settings.loop_interval_sec)
                continue

            if (time.time() - last_signal_ts) < settings.signal_cooldown_sec:
                stats.skipped_signals += 1
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
                stats.skipped_signals += 1
                time.sleep(settings.loop_interval_sec)
                continue

            if signal.side == "buy":
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
                    side=signal.side,
                    size_usdt=margin_size,
                    leverage=settings.leverage,
                )

            position = Position(
                side=signal.side,
                entry_price=price,
                margin_usdt=margin_size,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
            last_signal_ts = time.time()
            stats.entries += 1

            notifier.send(
                f"📌 진입 | side={signal.side} | score={signal.score} | reasons={','.join(signal.reasons)} | "
                f"trend=5m/15m 일치(3m 참고) | price={price:.2f} | margin={margin_size:.2f} | "
                f"lev={settings.leverage}x | sl={stop_loss:.2f} | tp={take_profit:.2f}"
            )
            logger.info(
                "[OPEN] side=%s score=%s reasons=%s trend3=%s trend5=%s trend15=%s price=%.2f margin=%.2f sl=%.2f tp=%.2f",
                signal.side,
                signal.score,
                ",".join(signal.reasons),
                trend_3m,
                trend_5m,
                trend_15m,
                price,
                margin_size,
                stop_loss,
                take_profit,
            )

        except BitgetClientError as exc:
            logger.exception("[API_ERROR] %s", exc)
            notifier.send(f"⚠️ 비트겟 연동 오류: {exc}")
            time.sleep(error_backoff_sec)
            error_backoff_sec = min(error_backoff_sec * 2, 60)
            continue
        except Exception as exc:
            logger.exception("[ERROR] %s", exc)
            notifier.send(f"⚠️ 에러 발생: {exc}")
            time.sleep(error_backoff_sec)
            error_backoff_sec = min(error_backoff_sec * 2, 60)
            continue

        time.sleep(settings.loop_interval_sec)


if __name__ == "__main__":
    main()
