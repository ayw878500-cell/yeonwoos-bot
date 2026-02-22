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
    symbol: str
    side: str
    entry_price: float
    margin_usdt: float
    stop_loss: float
    take_profit: float | None
    partial_take_done: bool = False
    add_count: int = 0
    last_feedback_ts: float = 0.0


@dataclass
class DailyStats:
    entries: int = 0
    closes: int = 0
    win_count: int = 0
    loss_count: int = 0
    skipped_signals: int = 0


@dataclass
class SignalCandidate:
    symbol: str
    signal: any
    price: float
    trend_3m: str | None
    trend_5m: str | None
    trend_15m: str | None


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


def pnl_pct(side: str, entry: float, current: float) -> float | None:
    if side == "buy":
        return (current - entry) / entry
    return (entry - current) / entry




def calc_levels(side: str, entry_price: float, stop_loss_pct: float, take_profit_pct: float) -> tuple[float, float]:
    if side == "buy":
        return entry_price * (1 - stop_loss_pct), entry_price * (1 + take_profit_pct)
    return entry_price * (1 + stop_loss_pct), entry_price * (1 - take_profit_pct)


def feedback_message(side: str, unrealized: float, trend_5m: str | None, trend_15m: str | None) -> str:
    if trend_5m == trend_15m == side:
        trend_comment = "추세는 유지 중"
    elif trend_5m == trend_15m and trend_5m is not None:
        trend_comment = "추세 반대 전환 가능성"
    else:
        trend_comment = "추세 혼조"
    return f"📌 실시간 피드백 | side={side} | 미실현={unrealized*100:.2f}% | 5m={trend_5m} 15m={trend_15m} | {trend_comment}"



def place_order_with_balance_fallback(
    client: BitgetClient,
    settings: Settings,
    logger: logging.Logger,
    notifier: TelegramNotifier,
    symbol: str,
    product_type: str,
    margin_coin: str,
    side: str,
    size_usdt: float,
    leverage: int,
    is_close: bool,
) -> float | None:
    effective_size = size_usdt
    if not is_close:
        available = client.account_available(symbol, product_type, margin_coin)
        if settings.full_balance_entry:
            cap_size = round(max(available, 0.0), 4)
        else:
            cap_size = round(max(available * settings.order_size_buffer, 0.0), 4)
        if cap_size <= 0:
            raise BitgetClientError("가용 잔고가 0이라 주문할 수 없습니다.")
        if effective_size > cap_size:
            logger.warning("[ORDER_CAP] 실시간 가용잔고 기준 주문 축소: %.4f -> %.4f", effective_size, cap_size)
            effective_size = cap_size

    try:
        client.place_market_order(
            symbol=symbol,
            product_type=product_type,
            margin_coin=margin_coin,
            side=side,
            size_usdt=effective_size,
            leverage=leverage,
            position_mode=settings.position_mode,
            is_close=is_close,
        )
        return effective_size
    except BitgetClientError as exc:
        if (not is_close) and "code=40762" in str(exc):
            available = client.account_available(symbol, product_type, margin_coin)
            if settings.full_balance_entry:
                reduced_size = round(max(available * 0.98, 0.0), 4)
            else:
                reduced_size = round(min(effective_size * settings.order_size_buffer, available * settings.order_size_buffer), 4)
            if reduced_size < settings.min_order_margin_usdt:
                logger.info("[ORDER_SKIP] 잔고초과(code=40762) + 최소주문금액 미만으로 주문 스킵")
                notifier.send("⚠️ 잔고 부족으로 주문 스킵(최소주문금액 미만)")
                return None
            logger.warning("[ORDER_RETRY] 잔고초과(code=40762)로 주문 축소 재시도: %.4f -> %.4f", effective_size, reduced_size)
            notifier.send(
                f"⚠️ 주문금액 축소 재시도: {effective_size:.4f} -> {reduced_size:.4f} (잔고초과 code=40762)"
            )
            try:
                client.place_market_order(
                    symbol=symbol,
                    product_type=product_type,
                    margin_coin=margin_coin,
                    side=side,
                    size_usdt=reduced_size,
                    leverage=leverage,
                    position_mode=settings.position_mode,
                    is_close=is_close,
                )
                return reduced_size
            except BitgetClientError as retry_exc:
                if "code=40762" in str(retry_exc):
                    logger.info("[ORDER_SKIP] 축소 재시도 후에도 잔고초과(code=40762)로 주문 스킵")
                    notifier.send("⚠️ 잔고 부족으로 주문 스킵(축소 재시도 실패)")
                    return None
                raise
        raise

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



def configured_symbols(settings: Settings, client: BitgetClient, logger: logging.Logger) -> list[str]:
    if settings.symbols_csv:
        symbols = [s.strip().upper() for s in settings.symbols_csv.split(",") if s.strip()]
        return symbols
    if settings.auto_scan_all_symbols:
        try:
            symbols = client.symbols(settings.product_type)
            symbols = [s for s in symbols if s.endswith("USDT")]
            return symbols[: settings.max_scan_symbols]
        except BitgetClientError as exc:
            logger.warning("[SYMBOL_SCAN] 전체 심볼 조회 실패, 단일 심볼로 대체: %s", exc)
    return [settings.symbol]


def find_signal_candidate(
    symbols: list[str],
    client: BitgetClient,
    settings: Settings,
    strategy: MultiIndicatorStrategy,
    logger: logging.Logger,
) -> SignalCandidate | None:
    for symbol in symbols:
        candles_3m = client.candles(symbol, settings.product_type, "3m", limit=300)
        candles_5m = client.candles(symbol, settings.product_type, "5m", limit=300)
        candles_15m = client.candles(symbol, settings.product_type, "15m", limit=300)

        signal = strategy.evaluate(
            closes=candles_5m["closes"],
            highs=candles_5m["highs"],
            lows=candles_5m["lows"],
            volumes=candles_5m["volumes"],
        )
        if not signal:
            continue

        trend_3m = strategy.trend_direction(candles_3m["closes"])
        trend_5m = strategy.trend_direction(candles_5m["closes"])
        trend_15m = strategy.trend_direction(candles_15m["closes"])

        if trend_5m == trend_15m == signal.side:
            return SignalCandidate(
                symbol=symbol,
                signal=signal,
                price=candles_5m["closes"][-1],
                trend_3m=trend_3m,
                trend_5m=trend_5m,
                trend_15m=trend_15m,
            )

        logger.info(
            "[SKIP] 추세 불일치(5m/15m 기준) symbol=%s signal=%s trend3=%s trend5=%s trend15=%s",
            symbol,
            signal.side,
            trend_3m,
            trend_5m,
            trend_15m,
        )
    return None

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

    logger.info("[START] DRY_RUN=%s symbol=%s position_mode=%s use_available_balance_sizing=%s full_balance_entry=%s", settings.dry_run, settings.symbol, settings.position_mode, settings.use_available_balance_sizing, settings.full_balance_entry)
    notifier.send(f"🚀 봇 시작: DRY_RUN={settings.dry_run}")

    trade_symbols = configured_symbols(settings, client, logger)
    logger.info("[SYMBOLS] 매매 대상 심볼 수: %s", len(trade_symbols))

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

            candles_3m = client.candles(position.symbol if position else settings.symbol, settings.product_type, "3m", limit=300)
            candles_5m = client.candles(position.symbol if position else settings.symbol, settings.product_type, "5m", limit=300)
            candles_15m = client.candles(position.symbol if position else settings.symbol, settings.product_type, "15m", limit=300)

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
                unrealized = pnl_pct(position.side, position.entry_price, price)
                trend_5m = strategy.trend_direction(candles_5m["closes"])
                trend_15m = strategy.trend_direction(candles_15m["closes"])

                if (
                    unrealized <= -settings.loss_feedback_trigger_pct
                    and (time.time() - position.last_feedback_ts) >= settings.feedback_interval_sec
                ):
                    msg = feedback_message(position.side, unrealized, trend_5m, trend_15m)
                    logger.info("[FEEDBACK] %s", msg)
                    notifier.send(msg)
                    position.last_feedback_ts = time.time()

                partial_rr_threshold = settings.stop_loss_pct * settings.partial_take_profit_rr
                if (not position.partial_take_done) and unrealized >= partial_rr_threshold:
                    partial_close_size = round(position.margin_usdt * 0.5, 4)
                    if partial_close_size > 0:
                        if not settings.dry_run:
                            client.place_market_order(
                                symbol=position.symbol,
                                product_type=settings.product_type,
                                margin_coin=settings.margin_coin,
                                side=close_side(position.side),
                                size_usdt=partial_close_size,
                                leverage=settings.leverage,
                                position_mode=settings.position_mode,
                                is_close=True,
                            )
                        position.margin_usdt = max(position.margin_usdt - partial_close_size, 0.0)
                        position.stop_loss = position.entry_price
                        position.take_profit = None
                        position.partial_take_done = True
                        notifier.send(
                            f"✅ 반익절 완료 | side={position.side} | close_size={partial_close_size:.2f} | 남은규모={position.margin_usdt:.2f} | 손절=본절"
                        )
                        logger.info(
                            "[PARTIAL_TP] side=%s size=%.2f remain=%.2f breakeven=%.2f",
                            position.side,
                            partial_close_size,
                            position.margin_usdt,
                            position.stop_loss,
                        )

                if (
                    position.add_count < settings.max_add_count
                    and unrealized <= -settings.add_on_loss_trigger_pct
                    and trend_5m == trend_15m == position.side
                ):
                    add_signal = strategy.evaluate(
                        closes=candles_5m["closes"],
                        highs=candles_5m["highs"],
                        lows=candles_5m["lows"],
                        volumes=candles_5m["volumes"],
                    )
                    if add_signal and add_signal.side == position.side and add_signal.score >= (settings.min_entry_conditions + 1):
                        add_margin = round(position.margin_usdt * settings.add_on_loss_fraction, 4)
                        if add_margin >= settings.min_order_margin_usdt:
                            executed_add_margin = add_margin
                            if not settings.dry_run:
                                result_size = place_order_with_balance_fallback(
                                    client=client,
                                    settings=settings,
                                    logger=logger,
                                    notifier=notifier,
                                    symbol=position.symbol,
                                    product_type=settings.product_type,
                                    margin_coin=settings.margin_coin,
                                    side=position.side,
                                    size_usdt=add_margin,
                                    leverage=settings.leverage,
                                    is_close=False,
                                )
                                if result_size is None:
                                    time.sleep(settings.loop_interval_sec)
                                    continue
                                executed_add_margin = result_size
                            total_margin = position.margin_usdt + executed_add_margin
                            position.entry_price = (
                                (position.entry_price * position.margin_usdt) + (price * executed_add_margin)
                            ) / total_margin
                            position.margin_usdt = total_margin
                            position.stop_loss, position.take_profit = calc_levels(
                                position.side,
                                position.entry_price,
                                settings.stop_loss_pct,
                                settings.take_profit_pct,
                            )
                            position.add_count += 1
                            notifier.send(
                                f"➕ 추가진입 | side={position.side} | add={executed_add_margin:.2f} | avg_entry={position.entry_price:.2f} | add_count={position.add_count}"
                            )
                            logger.info(
                                "[ADD_ON_LOSS] side=%s add=%.2f avg=%.2f count=%s",
                                position.side,
                                executed_add_margin,
                                position.entry_price,
                                position.add_count,
                            )

                should_close = False
                reason = ""
                if position.side == "buy":
                    if price <= position.stop_loss:
                        should_close = True
                        reason = "SL"
                    elif position.take_profit is not None and price >= position.take_profit:
                        should_close = True
                        reason = "TP"
                else:
                    if price >= position.stop_loss:
                        should_close = True
                        reason = "SL"
                    elif position.take_profit is not None and price <= position.take_profit:
                        should_close = True
                        reason = "TP"

                if should_close:
                    trade_pnl = pnl_pct(position.side, position.entry_price, price)
                    if not settings.dry_run:
                        client.place_market_order(
                            symbol=position.symbol,
                            product_type=settings.product_type,
                            margin_coin=settings.margin_coin,
                            side=close_side(position.side),
                            size_usdt=position.margin_usdt,
                            leverage=settings.leverage,
                            position_mode=settings.position_mode,
                            is_close=True,
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

            candidate = find_signal_candidate(
                symbols=trade_symbols,
                client=client,
                settings=settings,
                strategy=strategy,
                logger=logger,
            )
            if not candidate:
                time.sleep(settings.loop_interval_sec)
                continue

            signal = candidate.signal
            price = candidate.price
            trend_3m = candidate.trend_3m
            trend_5m = candidate.trend_5m
            trend_15m = candidate.trend_15m

            if (time.time() - last_signal_ts) < settings.signal_cooldown_sec:
                stats.skipped_signals += 1
                time.sleep(settings.loop_interval_sec)
                continue

            if settings.use_available_balance_sizing:
                available_margin = client.account_available(candidate.symbol, settings.product_type, settings.margin_coin)
                if settings.full_balance_entry:
                    margin_size = round(max(available_margin, 0.0), 4)
                else:
                    margin_size = round(max(available_margin * settings.entry_fraction, 0.0), 4)
            else:
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

            stop_loss, take_profit = calc_levels(
                signal.side,
                price,
                settings.stop_loss_pct,
                settings.take_profit_pct,
            )

            executed_margin_size = margin_size
            if not settings.dry_run:
                result_size = place_order_with_balance_fallback(
                    client=client,
                    settings=settings,
                    logger=logger,
                    notifier=notifier,
                    symbol=candidate.symbol,
                    product_type=settings.product_type,
                    margin_coin=settings.margin_coin,
                    side=signal.side,
                    size_usdt=margin_size,
                    leverage=settings.leverage,
                    is_close=False,
                )
                if result_size is None:
                    stats.skipped_signals += 1
                    last_signal_ts = time.time()
                    logger.info("[SKIP] 잔고 부족 주문 스킵 후 쿨다운 적용: %ss", settings.signal_cooldown_sec)
                    time.sleep(settings.loop_interval_sec)
                    continue
                executed_margin_size = result_size

            position = Position(
                symbol=candidate.symbol,
                side=signal.side,
                entry_price=price,
                margin_usdt=executed_margin_size,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
            last_signal_ts = time.time()
            stats.entries += 1

            notifier.send(
                f"📌 진입 | symbol={candidate.symbol} | side={signal.side} | score={signal.score} | reasons={','.join(signal.reasons)} | "
                f"trend=5m/15m 일치(3m 참고) | price={price:.2f} | margin={executed_margin_size:.2f} | "
                f"lev={settings.leverage}x | sl={stop_loss:.2f} | tp={take_profit:.2f}"
            )
            logger.info(
                "[OPEN] symbol=%s side=%s score=%s reasons=%s trend3=%s trend5=%s trend15=%s price=%.2f margin=%.2f sl=%.2f tp=%.2f",
                candidate.symbol,
                signal.side,
                signal.score,
                ",".join(signal.reasons),
                trend_3m,
                trend_5m,
                trend_15m,
                price,
                executed_margin_size,
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
