from collections import deque
from statistics import fmean


class EmaCrossStrategy:
    def __init__(self, fast: int = 20, slow: int = 60):
        self.fast = fast
        self.slow = slow
        self.prices = deque(maxlen=slow + 5)
        self.prev_state = None

    def update(self, price: float) -> str | None:
        self.prices.append(price)
        if len(self.prices) < self.slow:
            return None

        fast_ma = fmean(list(self.prices)[-self.fast :])
        slow_ma = fmean(list(self.prices)[-self.slow :])

        current_state = "above" if fast_ma > slow_ma else "below"
        signal = None

        if self.prev_state is not None and current_state != self.prev_state:
            signal = "buy" if current_state == "above" else "sell"

        self.prev_state = current_state
        return signal
