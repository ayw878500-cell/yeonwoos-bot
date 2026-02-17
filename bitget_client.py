import base64
import hashlib
import hmac
import json
import time
from typing import Any

import requests


class BitgetClient:
    def __init__(self, base_url: str, api_key: str, api_secret: str, api_passphrase: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase

    def _sign(self, timestamp: str, method: str, path: str, body: str) -> str:
        prehash = f"{timestamp}{method.upper()}{path}{body}"
        digest = hmac.new(self.api_secret.encode(), prehash.encode(), hashlib.sha256).digest()
        return base64.b64encode(digest).decode()

    def _headers(self, method: str, path: str, body: str) -> dict[str, str]:
        ts = str(int(time.time() * 1000))
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": self._sign(ts, method, path, body),
            "ACCESS-TIMESTAMP": ts,
            "ACCESS-PASSPHRASE": self.api_passphrase,
            "Content-Type": "application/json",
            "locale": "ko-KR",
        }

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(payload) if payload else ""
        headers = self._headers(method, path, body)
        url = f"{self.base_url}{path}"
        response = requests.request(method, url, headers=headers, data=body, timeout=10)
        response.raise_for_status()
        return response.json()

    def ticker_price(self, symbol: str, product_type: str) -> float:
        path = f"/api/v2/mix/market/ticker?symbol={symbol}&productType={product_type}"
        data = self._request("GET", path)
        return float(data["data"][0]["lastPr"])

    def account_equity(self, symbol: str, product_type: str, margin_coin: str) -> float:
        path = (
            "/api/v2/mix/account/account"
            f"?symbol={symbol}&productType={product_type}&marginCoin={margin_coin}"
        )
        data = self._request("GET", path)
        account = data.get("data") or {}
        # Bitget 응답 버전별 키 명 차이를 대비한 fallbacks
        for key in ("available", "availableBalance", "usdtEquity", "equity"):
            value = account.get(key)
            if value is not None:
                return float(value)
        raise ValueError(f"계좌 잔고 키를 찾지 못했습니다: {account}")

    def place_market_order(
        self,
        symbol: str,
        product_type: str,
        margin_coin: str,
        side: str,
        size_usdt: float,
        leverage: int,
    ) -> dict[str, Any]:
        path = "/api/v2/mix/order/place-order"
        payload = {
            "symbol": symbol,
            "productType": product_type,
            "marginCoin": margin_coin,
            "marginMode": "crossed",
            "side": side,
            "orderType": "market",
            "size": str(size_usdt),
            "lever": str(leverage),
        }
        return self._request("POST", path, payload)
