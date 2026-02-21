from dataclasses import dataclass


@dataclass
class SignalResult:
    side: str
    score: int
    reasons: list[str]


def _ema(values: list[float], length: int) -> list[float]:
    if not values:
        return []
    k = 2 / (length + 1)
    out = [values[0]]
    for value in values[1:]:
        out.append((value * k) + (out[-1] * (1 - k)))
    return out


def _sma(values: list[float], length: int) -> list[float]:
    out: list[float] = []
    for i in range(len(values)):
        if i + 1 < length:
            out.append(values[i])
        else:
            window = values[i + 1 - length : i + 1]
            out.append(sum(window) / length)
    return out


def _std(values: list[float]) -> float:
    if not values:
        return 0.0
    m = sum(values) / len(values)
    v = sum((x - m) ** 2 for x in values) / len(values)
    return v ** 0.5


class MultiIndicatorStrategy:
    def __init__(self, min_conditions: int = 2):
        self.min_conditions = min_conditions

    def trend_direction(self, closes: list[float]) -> str | None:
        if len(closes) < 220:
            return None
        ema9 = _ema(closes, 9)
        ema21 = _ema(closes, 21)
        ema200 = _ema(closes, 200)
        ema200_smoothed = _ema(ema200, 3)

        if closes[-1] > ema200_smoothed[-1] and ema9[-1] > ema21[-1]:
            return "buy"
        if closes[-1] < ema200_smoothed[-1] and ema9[-1] < ema21[-1]:
            return "sell"
        return None

    def evaluate(self, closes: list[float], highs: list[float], lows: list[float], volumes: list[float]) -> SignalResult | None:
        if len(closes) < 220:
            return None

        reasons_buy: list[str] = []
        reasons_sell: list[str] = []

        bb_len = 20
        bb_mult = 2.4
        bb_basis = _sma(closes, bb_len)[-1]
        bb_std = _std(closes[-bb_len:])
        bb_upper = bb_basis + bb_mult * bb_std
        bb_lower = bb_basis - bb_mult * bb_std
        last_close = closes[-1]
        if last_close <= bb_lower:
            reasons_buy.append("BB_LOWER_TOUCH")
        if last_close >= bb_upper:
            reasons_sell.append("BB_UPPER_TOUCH")

        ema9 = _ema(closes, 9)
        ema21 = _ema(closes, 21)
        if ema9[-1] > ema21[-1] and ema9[-2] <= ema21[-2]:
            reasons_buy.append("EMA9_21_GOLDEN")
        if ema9[-1] < ema21[-1] and ema9[-2] >= ema21[-2]:
            reasons_sell.append("EMA9_21_DEAD")

        ema200 = _ema(closes, 200)
        ema200_smoothed = _ema(ema200, 3)
        if last_close > ema200_smoothed[-1]:
            reasons_buy.append("EMA200_TREND_UP")
        else:
            reasons_sell.append("EMA200_TREND_DOWN")

        hlc3 = [(h + l + c) / 3 for h, l, c in zip(highs, lows, closes)]
        cumulative_pv = 0.0
        cumulative_v = 0.0
        for p, v in zip(hlc3, volumes):
            cumulative_pv += p * max(v, 0.0)
            cumulative_v += max(v, 0.0)
        vwap = cumulative_pv / cumulative_v if cumulative_v > 0 else hlc3[-1]
        if hlc3[-1] > vwap:
            reasons_buy.append("VWAP_ABOVE")
        else:
            reasons_sell.append("VWAP_BELOW")

        rsi = self._rsi(closes, 7)
        rsi_smooth = _ema(rsi, 3)
        if rsi_smooth[-1] < 30:
            reasons_buy.append("RSI_OVERSOLD")
        if rsi_smooth[-1] > 70:
            reasons_sell.append("RSI_OVERBOUGHT")

        k, d = self._stoch(highs, lows, closes, 5, 3, 3)
        if k[-1] > d[-1] and k[-2] <= d[-2] and k[-1] < 30:
            reasons_buy.append("STOCH_BULL_CROSS")
        if k[-1] < d[-1] and k[-2] >= d[-2] and k[-1] > 70:
            reasons_sell.append("STOCH_BEAR_CROSS")

        buy_score = len(reasons_buy)
        sell_score = len(reasons_sell)

        if buy_score >= self.min_conditions and buy_score > sell_score:
            return SignalResult(side="buy", score=buy_score, reasons=reasons_buy)
        if sell_score >= self.min_conditions and sell_score > buy_score:
            return SignalResult(side="sell", score=sell_score, reasons=reasons_sell)
        return None

    def _rsi(self, closes: list[float], length: int) -> list[float]:
        gains = [0.0]
        losses = [0.0]
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0.0))
            losses.append(max(-diff, 0.0))
        avg_gain = _ema(gains, length)
        avg_loss = _ema(losses, length)

        rsi: list[float] = []
        for g, l in zip(avg_gain, avg_loss):
            if l == 0:
                rsi.append(100.0)
            else:
                rs = g / l
                rsi.append(100 - (100 / (1 + rs)))
        return rsi

    def _stoch(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        k_length: int,
        k_smoothing: int,
        d_smoothing: int,
    ) -> tuple[list[float], list[float]]:
        raw_k: list[float] = []
        for i in range(len(closes)):
            if i + 1 < k_length:
                raw_k.append(50.0)
                continue
            hh = max(highs[i + 1 - k_length : i + 1])
            ll = min(lows[i + 1 - k_length : i + 1])
            if hh == ll:
                raw_k.append(50.0)
            else:
                raw_k.append(((closes[i] - ll) / (hh - ll)) * 100)

        smooth_k = _sma(raw_k, k_smoothing)
        smooth_d = _sma(smooth_k, d_smoothing)
        return smooth_k, smooth_d
