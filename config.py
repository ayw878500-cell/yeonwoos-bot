import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Settings:
    api_key: str
    api_secret: str
    api_passphrase: str
    base_url: str

    symbol: str
    product_type: str
    margin_coin: str

    leverage: int
    entry_fraction: float
    risk_per_trade: float
    stop_loss_pct: float
    take_profit_pct: float

    min_order_margin_usdt: float
    max_orders_per_day: int
    signal_cooldown_sec: int

    max_consecutive_errors: int
    error_cooldown_sec: int

    dry_run: bool
    live_confirm: str
    armed_trading: bool
    loop_interval_sec: int


class ConfigError(ValueError):
    pass


LIVE_CONFIRM_TEXT = "I_UNDERSTAND_LIVE_TRADING"


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"환경변수 {name} 이(가) 비어 있습니다.")
    return value


def _to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def load_settings() -> Settings:
    load_dotenv()

    settings = Settings(
        api_key=_require("BITGET_API_KEY"),
        api_secret=_require("BITGET_API_SECRET"),
        api_passphrase=_require("BITGET_API_PASSPHRASE"),
        base_url=os.getenv("BITGET_BASE_URL", "https://api.bitget.com").strip(),
        symbol=os.getenv("BITGET_SYMBOL", "BTCUSDT").strip(),
        product_type=os.getenv("BITGET_PRODUCT_TYPE", "USDT-FUTURES").strip(),
        margin_coin=os.getenv("BITGET_MARGIN_COIN", "USDT").strip(),
        leverage=int(os.getenv("LEVERAGE", "3")),
        entry_fraction=float(os.getenv("ENTRY_FRACTION", "0.1")),
        risk_per_trade=float(os.getenv("RISK_PER_TRADE", "0.01")),
        stop_loss_pct=float(os.getenv("STOP_LOSS_PCT", "0.01")),
        take_profit_pct=float(os.getenv("TAKE_PROFIT_PCT", "0.02")),
        min_order_margin_usdt=float(os.getenv("MIN_ORDER_MARGIN_USDT", "5")),
        max_orders_per_day=int(os.getenv("MAX_ORDERS_PER_DAY", "4")),
        signal_cooldown_sec=int(os.getenv("SIGNAL_COOLDOWN_SEC", "300")),
        max_consecutive_errors=int(os.getenv("MAX_CONSECUTIVE_ERRORS", "5")),
        error_cooldown_sec=int(os.getenv("ERROR_COOLDOWN_SEC", "120")),
        dry_run=_to_bool(os.getenv("DRY_RUN", "true")),
        live_confirm=os.getenv("LIVE_CONFIRM", "").strip(),
        armed_trading=_to_bool(os.getenv("ARMED_TRADING", "false")),
        loop_interval_sec=int(os.getenv("LOOP_INTERVAL_SEC", "15")),
    )

    _validate(settings)
    return settings


def _validate(s: Settings) -> None:
    if s.leverage < 1 or s.leverage > 10:
        raise ConfigError("LEVERAGE는 1~10 범위여야 합니다.")
    if not (0 < s.entry_fraction <= 0.5):
        raise ConfigError("ENTRY_FRACTION은 0 초과 0.5 이하로 제한됩니다.")
    if not (0 < s.risk_per_trade <= 0.02):
        raise ConfigError("RISK_PER_TRADE는 0 초과 0.02 이하로 제한됩니다.")
    if s.stop_loss_pct <= 0 or s.take_profit_pct <= 0:
        raise ConfigError("STOP_LOSS_PCT 및 TAKE_PROFIT_PCT는 양수여야 합니다.")
    if s.min_order_margin_usdt <= 0:
        raise ConfigError("MIN_ORDER_MARGIN_USDT는 양수여야 합니다.")
    if s.max_orders_per_day < 1:
        raise ConfigError("MAX_ORDERS_PER_DAY는 1 이상이어야 합니다.")
    if s.signal_cooldown_sec < 0:
        raise ConfigError("SIGNAL_COOLDOWN_SEC는 0 이상이어야 합니다.")
    if s.max_consecutive_errors < 1:
        raise ConfigError("MAX_CONSECUTIVE_ERRORS는 1 이상이어야 합니다.")
    if s.error_cooldown_sec < 1:
        raise ConfigError("ERROR_COOLDOWN_SEC는 1 이상이어야 합니다.")

    if not s.dry_run:
        if s.live_confirm != LIVE_CONFIRM_TEXT:
            raise ConfigError(
                "실전 주문을 하려면 LIVE_CONFIRM=I_UNDERSTAND_LIVE_TRADING 를 설정하세요."
            )
        if not s.armed_trading:
            raise ConfigError("실전 주문을 하려면 ARMED_TRADING=true 를 설정하세요.")
