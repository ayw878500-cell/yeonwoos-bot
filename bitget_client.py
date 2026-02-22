import base64
import hashlib
import hmac
import json
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class BitgetClientError(RuntimeError):
    pass


class BitgetClient:
    def __init__(self, base_url: str, api_key: str, api_secret: str, api_passphrase: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase

        retry = Retry(
            total=3,
            connect=3,
            read=3,
            status=3,
            backoff_factor=0.5,
            allowed_methods=frozenset(["GET", "POST"]),
            status_forcelist=[429, 500, 502, 503, 504],
        )
        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

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

    def _extract_error_detail(self, response: requests.Response | None) -> str:
        if response is None:
            return "response=none"
        status = response.status_code
        text = (response.text or "").strip()
        if not text:
            return f"status={status}, body=empty"
        try:
            parsed = response.json()
            code = parsed.get("code")
            msg = parsed.get("msg")
            if code is not None or msg is not None:
                return f"status={status}, code={code}, msg={msg}"
            return f"status={status}, body={str(parsed)[:300]}"
        except ValueError:
            return f"status={status}, body={text[:300]}"

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(payload) if payload else ""
        headers = self._headers(method, path, body)
        url = f"{self.base_url}{path}"

        response: requests.Response | None = None
        try:
            response = self.session.request(method, url, headers=headers, data=body, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            detail = self._extract_error_detail(getattr(exc, "response", response))
            raise BitgetClientError(
                f"비트겟 요청 실패: {method} {path} | {detail} | payload={payload}"
            ) from exc
        except ValueError as exc:
            snippet = (response.text[:300] if response is not None else "")
            raise BitgetClientError(
                f"비트겟 응답 JSON 파싱 실패: {method} {path} | body={snippet}"
            ) from exc

        code = str(data.get("code", ""))
        if code and code != "00000":
            msg = data.get("msg", "unknown error")
            raise BitgetClientError(
                f"비트겟 API 오류: code={code}, msg={msg}, path={path}, payload={payload}"
            )
        return data

    def ping(self) -> None:
        self._request("GET", "/api/v2/public/time")

    def validate_account_access(self, symbol: str, product_type: str, margin_coin: str) -> float:
        return self.account_equity(symbol, product_type, margin_coin)

    def ticker_price(self, symbol: str, product_type: str) -> float:
        path = f"/api/v2/mix/market/ticker?symbol={symbol}&productType={product_type}"
        data = self._request("GET", path)
        return float(data["data"][0]["lastPr"])

    def symbols(self, product_type: str) -> list[str]:
        path = f"/api/v2/mix/market/tickers?productType={product_type}"
        data = self._request("GET", path)
        rows = data.get("data") or []
        out: list[str] = []
        for row in rows:
            symbol = row.get("symbol") if isinstance(row, dict) else None
            if symbol:
                out.append(str(symbol))
        if not out:
            raise BitgetClientError("심볼 목록을 가져오지 못했습니다.")
        return out

    def account_equity(self, symbol: str, product_type: str, margin_coin: str) -> float:
        path = (
            "/api/v2/mix/account/account"
            f"?symbol={symbol}&productType={product_type}&marginCoin={margin_coin}"
        )
        data = self._request("GET", path)
        account = data.get("data") or {}
        for key in ("available", "availableBalance", "usdtEquity", "equity"):
            value = account.get(key)
            if value is not None:
                return float(value)
        raise BitgetClientError(f"계좌 잔고 키를 찾지 못했습니다: {account}")

    def account_available(self, symbol: str, product_type: str, margin_coin: str) -> float:
        path = (
            "/api/v2/mix/account/account"
            f"?symbol={symbol}&productType={product_type}&marginCoin={margin_coin}"
        )
        data = self._request("GET", path)
        account = data.get("data") or {}
        for key in ("available", "availableBalance", "maxOpenPosAvailable"):
            value = account.get(key)
            if value is not None:
                return float(value)
        for key in ("usdtEquity", "equity"):
            value = account.get(key)
            if value is not None:
                return float(value)
        raise BitgetClientError(f"가용 잔고 키를 찾지 못했습니다: {account}")

    def candles(self, symbol: str, product_type: str, granularity: str, limit: int = 300) -> dict[str, list[float]]:
        path = (
            "/api/v2/mix/market/candles"
            f"?symbol={symbol}&productType={product_type}&granularity={granularity}&limit={limit}"
        )
        data = self._request("GET", path)
        rows = data.get("data") or []

        closes: list[float] = []
        highs: list[float] = []
        lows: list[float] = []
        volumes: list[float] = []

        for row in rows:
            if not isinstance(row, list) or len(row) < 6:
                continue
            highs.append(float(row[2]))
            lows.append(float(row[3]))
            closes.append(float(row[4]))
            volumes.append(float(row[5]))

        if len(closes) < 20:
            raise BitgetClientError("캔들 데이터가 부족합니다. 심볼/상품유형/네트워크 상태를 확인하세요.")

        return {
            "closes": closes,
            "highs": highs,
            "lows": lows,
            "volumes": volumes,
        }

    def place_market_order(
        self,
        symbol: str,
        product_type: str,
        margin_coin: str,
        side: str,
        size_usdt: float,
        leverage: int,
        position_mode: str = "hedge",
        is_close: bool = False,
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
        if position_mode == "hedge":
            payload["tradeSide"] = "close" if is_close else "open"
        return self._request("POST", path, payload)
