# 비트겟 선물 자동매매 봇 (요청 반영 버전)

요청 반영:
- 레버리지 10배
- 진입 시드 30%
- 하루 목표 수익 10%
- 하루 손절 3회면 당일 거래 중지
- 텔레그램 알림
- 손익비는 전문 트레이더들이 많이 쓰는 1:2 기본 적용

---

## 1) 먼저 준비할 것

1. Python 설치 (3.10+)
2. 비트겟 API 3개 발급
   - API KEY / SECRET / PASSPHRASE
3. 텔레그램 봇 토큰 + chat id 준비(알림용)

---

## 2) 설치 (윈도우)

### 방법 A (권장)
```powershell
cd <봇파일있는곳>
powershell -NoProfile -ExecutionPolicy Bypass -File .\windows\install_autostart.ps1
```

### 방법 B (PowerShell 보안 막힘 시)
```cmd
cd <봇파일있는곳>
windows\install_autostart.cmd
```

---

## 3) .env 입력 (진짜 중요)

`.env` 파일 열고 아래는 꼭 채우세요.

```env
BITGET_API_KEY=내키
BITGET_API_SECRET=내시크릿
BITGET_API_PASSPHRASE=내패스프레이즈

TELEGRAM_BOT_TOKEN=내텔레그램봇토큰
TELEGRAM_CHAT_ID=내채팅아이디
```

기본값은 이미 요청대로 세팅돼 있습니다.

```env
LEVERAGE=10
ENTRY_FRACTION=0.3
MAX_DAILY_STOPLOSS=3
DAILY_TARGET_PCT=0.1
STOP_LOSS_PCT=0.01
RISK_REWARD_RATIO=2.0
DRY_RUN=false
LIVE_CONFIRM=I_UNDERSTAND_LIVE_TRADING
ARMED_TRADING=true
```

---


## 3-1) 손익비(전문 트레이더 방식) 설정

현재 기본은 **손익비 1:2** 입니다.
- 손절 1%면 익절 2%
- 계산식: `TAKE_PROFIT_PCT = STOP_LOSS_PCT * RISK_REWARD_RATIO`

`.env`에서 이렇게 설정하면 됩니다.

```env
STOP_LOSS_PCT=0.01
RISK_REWARD_RATIO=2.0
```

보통 많이 쓰는 범위:
- 1.5 ~ 3.0 (기본 2.0 권장)

---

## 4) 매매 동작 방식 (복잡하지 않게)

1. EMA(FAST_MA/SLOW_MA) 신호 발생 시 진입
2. 진입 후 손절/익절 가격 자동 계산
3. 가격이 손절선/익절선 닿으면 자동 청산
4. 손절이 하루 3회 되면 오늘 종료
5. 하루 수익이 10% 이상이면 오늘 종료
6. 모든 상태를 텔레그램으로 전송

---

## 5) 원하는 신호로 바꾸는 방법

`.env`에서 아래 두 값만 바꾸면 됩니다.

```env
FAST_MA=20
SLOW_MA=60
```

예:
- 더 빠르게 반응: `FAST_MA=10`, `SLOW_MA=30`
- 더 느리게/보수적: `FAST_MA=30`, `SLOW_MA=90`

---

## 6) 실행 확인

```powershell
cd <봇파일있는곳>
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe bot.py
```

로그 파일:
- `logs/bot.out.log`
- `logs/bot.err.log`

---

## 7) 자주 나는 오류

### (1) 디지털 서명/실행정책 오류
`install_autostart.cmd`로 실행하면 우회됩니다.

### (2) Register-ScheduledTask 액세스 거부(0x80070005)
권한 문제입니다. 스크립트가 자동으로 Startup 방식으로 등록합니다.

---

## 8) 내가 추천하는 프롬프트 추가 항목

다음 요구사항까지 프롬프트에 같이 넣으면 결과물이 더 좋아집니다.

1. **최대 동시 포지션 수**(예: 1개)
2. **하루 최대 손실률**(예: -5% 도달 시 중지)
3. **슬리피지/수수료 포함 백테스트 기준**
4. **거래 가능한 시간대 제한**(뉴스 시간 피하기)
5. **비상 정지 명령어**(텔레그램으로 STOP)
6. **재시작 후 포지션 복구 로직**(기존 포지션 감지)

---

## 면책

실전 손익 책임은 본인에게 있습니다.
