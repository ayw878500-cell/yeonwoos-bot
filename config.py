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

    dry_run: bool
    loop_interval_sec: int


class ConfigError(ValueError):
    pass


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"환경변수 {name} 이(가) 비어 있습니다.")
    return value


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
        dry_run=os.getenv("DRY_RUN", "true").lower() == "true",
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
        raise ConfigError("RISK_PER_TRADE는 0 초과 0.02 이하를 권장/강제합니다.")
    if s.stop_loss_pct <= 0 or s.take_profit_pct <= 0:
        raise ConfigError("STOP_LOSS_PCT 및 TAKE_PROFIT_PCT는 양수여야 합니다.")
