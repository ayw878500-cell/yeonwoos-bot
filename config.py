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

    fast_ma: int
    slow_ma: int

    max_daily_stoploss: int
    daily_target_pct: float
    min_order_margin_usdt: float
    signal_cooldown_sec: int

    dry_run: bool
    live_confirm: str
    armed_trading: bool
    loop_interval_sec: int

    telegram_bot_token: str
    telegram_chat_id: str
    telegram_enabled: bool


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

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    settings = Settings(
        api_key=_require("BITGET_API_KEY"),
        api_secret=_require("BITGET_API_SECRET"),
        api_passphrase=_require("BITGET_API_PASSPHRASE"),
        base_url=os.getenv("BITGET_BASE_URL", "https://api.bitget.com").strip(),
        symbol=os.getenv("BITGET_SYMBOL", "BTCUSDT").strip(),
        product_type=os.getenv("BITGET_PRODUCT_TYPE", "USDT-FUTURES").strip(),
        margin_coin=os.getenv("BITGET_MARGIN_COIN", "USDT").strip(),
        leverage=int(os.getenv("LEVERAGE", "10")),
        entry_fraction=float(os.getenv("ENTRY_FRACTION", "0.3")),
        risk_per_trade=float(os.getenv("RISK_PER_TRADE", "0.01")),
        stop_loss_pct=float(os.getenv("STOP_LOSS_PCT", "0.01")),
        take_profit_pct=float(os.getenv("TAKE_PROFIT_PCT", "0.02")),
        fast_ma=int(os.getenv("FAST_MA", "20")),
        slow_ma=int(os.getenv("SLOW_MA", "60")),
        max_daily_stoploss=int(os.getenv("MAX_DAILY_STOPLOSS", "3")),
        daily_target_pct=float(os.getenv("DAILY_TARGET_PCT", "0.1")),
        min_order_margin_usdt=float(os.getenv("MIN_ORDER_MARGIN_USDT", "5")),
        signal_cooldown_sec=int(os.getenv("SIGNAL_COOLDOWN_SEC", "120")),
        dry_run=_to_bool(os.getenv("DRY_RUN", "false")),
        live_confirm=os.getenv("LIVE_CONFIRM", "").strip(),
        armed_trading=_to_bool(os.getenv("ARMED_TRADING", "true")),
        loop_interval_sec=int(os.getenv("LOOP_INTERVAL_SEC", "5")),
        telegram_bot_token=token,
        telegram_chat_id=chat_id,
        telegram_enabled=bool(token and chat_id),
    )

    _validate(settings)
    return settings


def _validate(s: Settings) -> None:
    if s.leverage < 1 or s.leverage > 10:
        raise ConfigError("LEVERAGE는 1~10 범위여야 합니다.")
    if not (0 < s.entry_fraction <= 1):
        raise ConfigError("ENTRY_FRACTION은 0 초과 1 이하로 입력하세요.")
    if s.stop_loss_pct <= 0 or s.take_profit_pct <= 0:
        raise ConfigError("STOP_LOSS_PCT, TAKE_PROFIT_PCT는 양수여야 합니다.")
    if s.fast_ma < 2 or s.slow_ma <= s.fast_ma:
        raise ConfigError("FAST_MA < SLOW_MA 형태로 설정하세요.")
    if s.max_daily_stoploss < 1:
        raise ConfigError("MAX_DAILY_STOPLOSS는 1 이상이어야 합니다.")
    if s.daily_target_pct <= 0:
        raise ConfigError("DAILY_TARGET_PCT는 양수여야 합니다.")
    if s.min_order_margin_usdt <= 0:
        raise ConfigError("MIN_ORDER_MARGIN_USDT는 양수여야 합니다.")
    if s.signal_cooldown_sec < 0:
        raise ConfigError("SIGNAL_COOLDOWN_SEC는 0 이상이어야 합니다.")

    if not s.dry_run:
        if s.live_confirm != LIVE_CONFIRM_TEXT:
            raise ConfigError(
                "실전 주문을 하려면 LIVE_CONFIRM=I_UNDERSTAND_LIVE_TRADING 를 설정하세요."
            )
        if not s.armed_trading:
            raise ConfigError("실전 주문을 하려면 ARMED_TRADING=true 를 설정하세요.")
