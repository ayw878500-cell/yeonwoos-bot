from dataclasses import dataclass


@dataclass
class PositionPlan:
    side: str
    size_usdt: float
    stop_loss: float
    take_profit: float


def calc_position_size(
    equity_usdt: float,
    entry_fraction: float,
    leverage: int,
    entry_price: float,
    stop_loss_pct: float,
    risk_per_trade: float,
) -> float:
    """
    둘 중 더 작은 값을 사용:
    1) 계좌 배분 기반 진입금액
    2) 손절 시 계좌 위험한도(risk_per_trade) 기반 진입금액
    """
    by_allocation = equity_usdt * entry_fraction

    # 손절 손실금 = 포지션명목 * stop_loss_pct / leverage
    # 위험한도 내 포지션명목 = equity*risk / stop_loss_pct * leverage
    if stop_loss_pct <= 0:
        return 0.0
    by_risk = (equity_usdt * risk_per_trade / stop_loss_pct) * leverage

    notion = min(by_allocation * leverage, by_risk)
    margin_used = notion / leverage
    return max(margin_used, 0.0)


def make_plan(
    side: str,
    entry_price: float,
    size_usdt: float,
    stop_loss_pct: float,
    take_profit_pct: float,
) -> PositionPlan:
    if side == "buy":
        stop_loss = entry_price * (1 - stop_loss_pct)
        take_profit = entry_price * (1 + take_profit_pct)
    else:
        stop_loss = entry_price * (1 + stop_loss_pct)
        take_profit = entry_price * (1 - take_profit_pct)

    return PositionPlan(
        side=side,
        size_usdt=round(size_usdt, 4),
        stop_loss=round(stop_loss, 2),
        take_profit=round(take_profit, 2),
    )
