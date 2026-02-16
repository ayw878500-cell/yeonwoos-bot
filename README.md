# yeonwoos-bot

비트겟 선물(BTC/ETH 전용) 자동매매/매매추천 봇 예제입니다.

## 핵심 규칙(요청사항 반영)
- BTC, ETH만 매매 (`BTC/USDT:USDT`, `ETH/USDT:USDT`)
- 일일 누적 수익률 `+10%` 이상이면 당일 매매 종료
- 당일 손실 포지션 `3회` 이상이면 당일 매매 종료
- 추가 보호장치: 일일 최대 손실 `-5%` 도달 시 종료

> ⚠️ 중요: 시장에서 “하루 10% 무조건”은 보장할 수 없습니다. 이 봇은 **리스크 관리 우선**으로 목표 달성 시 거래를 멈추도록 설계했습니다.

## 진짜로 "이제 어떻게 하면 되나요?" (빠른 시작)
1. 가상환경/의존성 설치
2. Bitget API 키 환경변수 설정
3. `recommend` 모드로 1~2일 모니터링
4. 상태값 확인 (`--status`) + 필요시 초기화 (`--reset-day`)
5. 소액으로만 `auto --confirm-live` 전환

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export BITGET_API_KEY="..."
export BITGET_API_SECRET="..."
export BITGET_API_PASSPHRASE="..."
```

### 추천 모드 실행 (안전)
```bash
python trader_bot.py --mode recommend --symbols BTC/USDT:USDT ETH/USDT:USDT --timeframe 15m --loop --interval 60
```

### 상태 확인/초기화
```bash
python trader_bot.py --status
python trader_bot.py --reset-day --status
```

### 자동매매 실행 (실주문, 확인 플래그 필수)
```bash
python trader_bot.py --mode auto --confirm-live --symbols BTC/USDT:USDT ETH/USDT:USDT --timeframe 15m --loop --interval 60
```

### 시드(자본)와 1회 리스크 직접 지정
```bash
python trader_bot.py --mode recommend --account-size 1000 --risk-per-trade 0.01 --symbols BTC/USDT:USDT ETH/USDT:USDT
```
- `--account-size 1000` = 포지션 계산용 시드를 1000 USDT로 고정
- `--risk-per-trade 0.01` = 1회 트레이드 최대 손실 허용 1%



### 뉴스/이벤트 필터 (CPI/FOMC)
`events.json`에 이벤트 시간을 UTC(ISO8601)로 넣으면, 전후 구간 신규 진입을 차단합니다.

```bash
python trader_bot.py --mode recommend --events-file events.json --block-before-min 90 --block-after-min 90
```

`events.json` 예시:
```json
{
  "events": [
    {"name": "US CPI", "at": "2026-03-12T12:30:00Z"},
    {"name": "FOMC Rate Decision", "at": "2026-03-18T18:00:00Z"}
  ]
}
```

### 텔레그램 알림 연결 (선택)
```bash
export TELEGRAM_BOT_TOKEN="123456:ABC..."
export TELEGRAM_CHAT_ID="123456789"

python trader_bot.py --mode recommend --loop --interval 60
```
- LONG/SHORT 신호 발생 시 텔레그램으로 알림이 전송됩니다.
- auto 모드에서 주문이 체결되면 주문 ID도 알림으로 전송됩니다.

## 동작 방식
- 신호: EMA(20/50) 크로스 + RSI + ATR(변동성 필터)
- 손절: ATR 기반 (`SL = 1.5 * ATR`)
- 익절: 손익비 1:2
- 포지션 사이즈: 계좌의 `1%`만 리스크로 계산
- 실주문 안전장치: `--confirm-live` 없으면 auto 모드라도 주문 차단
- 뉴스/이벤트 필터: CPI/FOMC 등 이벤트 전후 지정 시간 신규 진입 차단
- 기본 레버리지: 10배

## 파일
- `trader_bot.py`: 실행 스크립트
- `requirements.txt`: 의존성
- `state.json`: 일일 상태 저장(자동 생성)

## 주요 CLI 옵션
- `--mode recommend|auto`
- `--symbols BTC/USDT:USDT ETH/USDT:USDT`
- `--loop --interval 60`
- `--status`: 오늘 상태 출력
- `--reset-day`: 오늘 상태 초기화
- `--show-config`: 현재 기본 리스크 설정값 출력
- `--confirm-live`: auto 모드 실주문 허용 플래그
- `--account-size`: 포지션 계산용 시드(USDT), 0이면 거래소 USDT 잔고 사용
- `--risk-per-trade`: 1회 트레이드 리스크 비율
- `--telegram-bot-token`: 텔레그램 봇 토큰 (미지정 시 환경변수 사용)
- `--telegram-chat-id`: 텔레그램 chat id (미지정 시 환경변수 사용)
- `--events-file`: 이벤트 JSON 파일 경로
- `--block-before-min`: 이벤트 이전 차단 분 (기본 60)
- `--block-after-min`: 이벤트 이후 차단 분 (기본 60)

## 추가 추천(강력 권장)
1. **뉴스/이벤트 필터**: CPI/FOMC 전후 일정 시간 신규 진입 금지
2. **슬리피지 한도**: 스프레드/슬리피지가 기준 초과 시 주문 취소
3. **쿨다운 규칙**: 연속 손실 2회면 2~4시간 거래 중지
4. **최대 보유시간**: 포지션 6~8시간 초과 시 강제 청산
5. **백테스트/워크포워드**: 최소 1년치 데이터로 샤프/승률/최대낙폭 검증
6. **실거래 전 paper-trading**: 최소 2주 검증 후 소액 실거래 전환

## 주의
- 본 코드는 교육/연구 목적 예제입니다.
- 실거래 전 반드시 소액/테스트넷으로 검증하세요.
