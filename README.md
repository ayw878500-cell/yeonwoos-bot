# Yeonwoo's Bitget Bot (윈도우 + 실전매매 운영형 가이드)

> ⚠️ 고지: 이 코드는 실전 운영 보조 템플릿입니다. 수익을 보장하지 않으며, 선물/레버리지는 큰 손실 위험이 있습니다.

## 1) 실전 운영형으로 바뀐 점

- 계좌 잔고를 Bitget API에서 직접 조회해서 포지션 크기 계산
- 일일 주문 횟수 제한(`MAX_ORDERS_PER_DAY`)
- 연속 진입 쿨다운(`SIGNAL_COOLDOWN_SEC`)
- 최소 주문 증거금(`MIN_ORDER_MARGIN_USDT`) 미만 주문 차단
- 실전모드 2중 확인: `DRY_RUN=false` + `LIVE_CONFIRM=I_UNDERSTAND_LIVE_TRADING`

---

## 2) 윈도우 실행 (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
copy .env.example .env
```

그 다음 `.env` 파일을 수정하고 실행:

```powershell
python bot.py
```

실행 정책 오류 시(1회):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

---

## 3) `.env` 실전매매용 설명

```env
BITGET_API_KEY=...
BITGET_API_SECRET=...
BITGET_API_PASSPHRASE=...

BITGET_BASE_URL=https://api.bitget.com
BITGET_SYMBOL=BTCUSDT
BITGET_PRODUCT_TYPE=USDT-FUTURES
BITGET_MARGIN_COIN=USDT

LEVERAGE=3
ENTRY_FRACTION=0.1
RISK_PER_TRADE=0.01
STOP_LOSS_PCT=0.01
TAKE_PROFIT_PCT=0.02

MIN_ORDER_MARGIN_USDT=5
MAX_ORDERS_PER_DAY=4
SIGNAL_COOLDOWN_SEC=300

DRY_RUN=true
LIVE_CONFIRM=
LOOP_INTERVAL_SEC=15
```

### 핵심 변수
- `DRY_RUN=true` : 연습모드(실주문 없음)
- `DRY_RUN=false` : 실주문 가능 상태
- `LIVE_CONFIRM=I_UNDERSTAND_LIVE_TRADING` : 실주문 보호문구 (이 값이 정확히 맞아야 실주문 허용)
- `ENTRY_FRACTION` : 한 번 진입 시 사용할 계좌 비율
- `RISK_PER_TRADE` : 손절 기준으로 허용하는 계좌 리스크
- `MAX_ORDERS_PER_DAY` : 하루 최대 주문 횟수

---

## 4) 실전 전환 순서 (권장)

1. `DRY_RUN=true`로 3~7일 로그 검증
2. API 키 권한 점검 (출금 권한 금지)
3. `LEVERAGE` 낮게 유지 (예: 2~3)
4. `ENTRY_FRACTION` 0.05~0.1부터 시작
5. 아주 작은 금액으로 실전 테스트
6. 문제 없을 때 천천히 증액

---

## 5) PR 브랜치 바로 내려받기 (윈도우)

PR 번호가 123이면:

```powershell
git fetch origin pull/123/head:pr-123
git switch pr-123
```

---

## 6) 자주 나는 오류

### `ModuleNotFoundError: No module named 'requests'`

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -c "import requests; print(requests.__version__)"
python bot.py
```

또는 강제 실행:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe bot.py
```

---

## 7) 면책

교육/연구용 예제입니다. 투자 손실 책임은 사용자 본인에게 있습니다.
