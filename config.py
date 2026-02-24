import os
from io import StringIO
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


@dataclass
class Settings:
    api_key: str
    api_secret: str
    api_passphrase: str
    base_url: str

    symbol: str
    symbols_csv: str
    auto_scan_all_symbols: bool
    max_scan_symbols: int
    product_type: str
    margin_coin: str

    leverage: int
    entry_fraction: float
    risk_per_trade: float
    stop_loss_pct: float
    risk_reward_ratio: float
    take_profit_pct: float

    fast_ma: int
    slow_ma: int

    max_daily_stoploss: int
    daily_target_pct: float
    min_order_margin_usdt: float
    signal_cooldown_sec: int
    min_entry_conditions: int
    candle_granularity: str
    report_hour_utc: int
    position_mode: str
    partial_take_profit_rr: float
    add_on_loss_trigger_pct: float
    add_on_loss_fraction: float
    max_add_count: int
    loss_feedback_trigger_pct: float
    feedback_interval_sec: int
    order_size_buffer: float
    use_available_balance_sizing: bool
    full_balance_entry: bool

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


def _load_dotenv_with_fallback() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        load_dotenv()
        return

    raw = env_path.read_bytes()
    decoded = None
    used_encoding = None
    for encoding in ("utf-8-sig", "cp949"):
        try:
            decoded = raw.decode(encoding)
            used_encoding = encoding
            break
        except UnicodeDecodeError:
            continue

    if decoded is None:
        raise ConfigError(
            ".env 파일 인코딩을 읽지 못했습니다. 메모장에서 .env를 열고 '다른 이름으로 저장' → 인코딩 UTF-8 로 저장 후 다시 실행하세요."
        )

    if used_encoding != "utf-8-sig":
        print("[WARN] .env 파일이 UTF-8이 아니라서 cp949로 읽었습니다. 가능하면 UTF-8로 저장하세요.")

    values = dotenv_values(stream=StringIO(decoded))
    for key, value in values.items():
        if key and value is not None and key not in os.environ:
            os.environ[key] = value


def load_settings() -> Settings:
    _load_dotenv_with_fallback()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    settings = Settings(
        api_key=_require("BITGET_API_KEY"),
        api_secret=_require("BITGET_API_SECRET"),
        api_passphrase=_require("BITGET_API_PASSPHRASE"),
        base_url=os.getenv("BITGET_BASE_URL", "https://api.bitget.com").strip(),
        symbol=os.getenv("BITGET_SYMBOL", "BTCUSDT").strip(),
        symbols_csv=os.getenv("SYMBOLS", "").strip(),
        auto_scan_all_symbols=_to_bool(os.getenv("AUTO_SCAN_ALL_SYMBOLS", "true")),
        max_scan_symbols=int(os.getenv("MAX_SCAN_SYMBOLS", "20")),
        product_type=os.getenv("BITGET_PRODUCT_TYPE", "USDT-FUTURES").strip(),
        margin_coin=os.getenv("BITGET_MARGIN_COIN", "USDT").strip(),
        leverage=int(os.getenv("LEVERAGE", "10")),
        entry_fraction=float(os.getenv("ENTRY_FRACTION", "1.0")),
        risk_per_trade=float(os.getenv("RISK_PER_TRADE", "0.01")),
        stop_loss_pct=float(os.getenv("STOP_LOSS_PCT", "0.01")),
        risk_reward_ratio=float(os.getenv("RISK_REWARD_RATIO", "2.0")),
        take_profit_pct=0.0,
        fast_ma=int(os.getenv("FAST_MA", "20")),
        slow_ma=int(os.getenv("SLOW_MA", "60")),
        max_daily_stoploss=int(os.getenv("MAX_DAILY_STOPLOSS", "3")),
        daily_target_pct=float(os.getenv("DAILY_TARGET_PCT", "0.1")),
        min_order_margin_usdt=float(os.getenv("MIN_ORDER_MARGIN_USDT", "5")),
        signal_cooldown_sec=int(os.getenv("SIGNAL_COOLDOWN_SEC", "120")),
        min_entry_conditions=int(os.getenv("MIN_ENTRY_CONDITIONS", "2")),
        candle_granularity=os.getenv("CANDLE_GRANULARITY", "5m").strip(),
        report_hour_utc=int(os.getenv("REPORT_HOUR_UTC", "0")),
        position_mode=os.getenv("POSITION_MODE", "hedge").strip().lower(),
        partial_take_profit_rr=float(os.getenv("PARTIAL_TAKE_PROFIT_RR", "2.0")),
        add_on_loss_trigger_pct=float(os.getenv("ADD_ON_LOSS_TRIGGER_PCT", "0.006")),
        add_on_loss_fraction=float(os.getenv("ADD_ON_LOSS_FRACTION", "0.25")),
        max_add_count=int(os.getenv("MAX_ADD_COUNT", "1")),
        loss_feedback_trigger_pct=float(os.getenv("LOSS_FEEDBACK_TRIGGER_PCT", "0.004")),
        feedback_interval_sec=int(os.getenv("FEEDBACK_INTERVAL_SEC", "300")),
        order_size_buffer=float(os.getenv("ORDER_SIZE_BUFFER", "0.9")),
        use_available_balance_sizing=_to_bool(os.getenv("USE_AVAILABLE_BALANCE_SIZING", "true")),
        full_balance_entry=_to_bool(os.getenv("FULL_BALANCE_ENTRY", "true")),
        dry_run=_to_bool(os.getenv("DRY_RUN", "false")),
        live_confirm=os.getenv("LIVE_CONFIRM", "").strip(),
        armed_trading=_to_bool(os.getenv("ARMED_TRADING", "true")),
        loop_interval_sec=int(os.getenv("LOOP_INTERVAL_SEC", "5")),
        telegram_bot_token=token,
        telegram_chat_id=chat_id,
        telegram_enabled=bool(token and chat_id),
    )

    settings.take_profit_pct = settings.stop_loss_pct * settings.risk_reward_ratio

    _validate(settings)
    return settings


def _validate(s: Settings) -> None:
    if s.leverage < 1 or s.leverage > 10:
        raise ConfigError("LEVERAGE는 1~10 범위여야 합니다.")
    if s.max_scan_symbols < 1 or s.max_scan_symbols > 200:
        raise ConfigError("MAX_SCAN_SYMBOLS는 1~200 범위로 설정하세요.")
    if not (0 < s.entry_fraction <= 1):
        raise ConfigError("ENTRY_FRACTION은 0 초과 1 이하로 입력하세요.")
    if s.stop_loss_pct <= 0:
        raise ConfigError("STOP_LOSS_PCT는 양수여야 합니다.")
    if s.risk_reward_ratio < 1.5 or s.risk_reward_ratio > 4.0:
        raise ConfigError("RISK_REWARD_RATIO는 1.5~4.0 범위(전문가들이 자주 쓰는 구간)로 설정하세요.")
    if s.take_profit_pct <= 0:
        raise ConfigError("계산된 TAKE_PROFIT_PCT가 0 이하입니다. STOP_LOSS_PCT/RISK_REWARD_RATIO를 확인하세요.")
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
    if s.min_entry_conditions < 2 or s.min_entry_conditions > 6:
        raise ConfigError("MIN_ENTRY_CONDITIONS는 2~6 범위로 설정하세요.")
    if s.report_hour_utc < 0 or s.report_hour_utc > 23:
        raise ConfigError("REPORT_HOUR_UTC는 0~23 범위여야 합니다.")
    if s.position_mode not in {"hedge", "oneway"}:
        raise ConfigError("POSITION_MODE는 hedge 또는 oneway로 설정하세요.")
    if s.partial_take_profit_rr < 1.0 or s.partial_take_profit_rr > 5.0:
        raise ConfigError("PARTIAL_TAKE_PROFIT_RR는 1.0~5.0 범위로 설정하세요.")
    if s.add_on_loss_trigger_pct <= 0 or s.add_on_loss_trigger_pct > 0.05:
        raise ConfigError("ADD_ON_LOSS_TRIGGER_PCT는 0 초과 0.05 이하로 설정하세요.")
    if s.add_on_loss_fraction <= 0 or s.add_on_loss_fraction > 1:
        raise ConfigError("ADD_ON_LOSS_FRACTION은 0 초과 1 이하로 설정하세요.")
    if s.max_add_count < 0 or s.max_add_count > 3:
        raise ConfigError("MAX_ADD_COUNT는 0~3 범위로 설정하세요.")
    if s.loss_feedback_trigger_pct <= 0 or s.loss_feedback_trigger_pct > 0.05:
        raise ConfigError("LOSS_FEEDBACK_TRIGGER_PCT는 0 초과 0.05 이하로 설정하세요.")
    if s.feedback_interval_sec < 10:
        raise ConfigError("FEEDBACK_INTERVAL_SEC는 10초 이상으로 설정하세요.")
    if s.order_size_buffer <= 0 or s.order_size_buffer > 1:
        raise ConfigError("ORDER_SIZE_BUFFER는 0 초과 1 이하로 설정하세요.")
    if not s.candle_granularity:
        raise ConfigError("CANDLE_GRANULARITY를 입력하세요.")

    if not s.dry_run:
        if s.live_confirm != LIVE_CONFIRM_TEXT:
            raise ConfigError(
                "실전 주문을 하려면 LIVE_CONFIRM=I_UNDERSTAND_LIVE_TRADING 를 설정하세요."
            )
        if not s.armed_trading:
            raise ConfigError("실전 주문을 하려면 ARMED_TRADING=true 를 설정하세요.")
