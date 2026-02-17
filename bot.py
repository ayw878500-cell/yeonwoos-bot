import time

from bitget_client import BitgetClient
from config import load_settings
from risk import calc_position_size, make_plan
from strategy import EmaCrossStrategy


def main() -> None:
    settings = load_settings()
    client = BitgetClient(
        settings.base_url,
        settings.api_key,
        settings.api_secret,
        settings.api_passphrase,
    )
    strategy = EmaCrossStrategy(fast=20, slow=60)

    # 데모값: 실제로는 API에서 계좌 가용잔고 조회 후 반영 권장
    equity_usdt = 1000.0

    print("[START] bot running... DRY_RUN=", settings.dry_run)
    while True:
        try:
            price = client.ticker_price(settings.symbol, settings.product_type)
            signal = strategy.update(price)
            if signal:
                size = calc_position_size(
                    equity_usdt=equity_usdt,
                    entry_fraction=settings.entry_fraction,
                    leverage=settings.leverage,
                    entry_price=price,
                    stop_loss_pct=settings.stop_loss_pct,
                    risk_per_trade=settings.risk_per_trade,
                )
                plan = make_plan(
                    side=signal,
                    entry_price=price,
                    size_usdt=size,
                    stop_loss_pct=settings.stop_loss_pct,
                    take_profit_pct=settings.take_profit_pct,
                )
                print(f"[SIGNAL] {signal=} {price=} {plan=}")

                if not settings.dry_run and size > 0:
                    result = client.place_market_order(
                        symbol=settings.symbol,
                        product_type=settings.product_type,
                        margin_coin=settings.margin_coin,
                        side=signal,
                        size_usdt=size,
                        leverage=settings.leverage,
                    )
                    print("[ORDER]", result)
                else:
                    print("[DRY_RUN] order skipped")

        except Exception as exc:
            print("[ERROR]", exc)

        time.sleep(settings.loop_interval_sec)


if __name__ == "__main__":
    main()
