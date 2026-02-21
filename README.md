# 비트겟 선물 자동매매 봇 (요청 반영 버전)

요청 반영:
- 레버리지 10배
- 진입 시드 30%
- 하루 목표 수익 10%
- 하루 손절 3회면 당일 거래 중지
- 텔레그램 알림
- 손익비는 전문 트레이더들이 많이 쓰는 1:2 기본 적용
- 6개 지표 조합 + 2개 이상 조건 일치 시 진입
- 매일 정각(UTC 기준 설정) 일일 로그 리포트 텔레그램 전송

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
MIN_ENTRY_CONDITIONS=2
CANDLE_GRANULARITY=5m
REPORT_HOUR_UTC=0
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

1. 비트겟 캔들 데이터를 받아 6개 지표를 계산합니다.
   - BB(20, 2.4), EMA Cross(9/21), EMA200(EMA3 스무딩), VWAP(hlc3), RSI(7/EMA3), Stoch(5,3,3)
2. 매수/매도 조건 중 **2개 이상** 같은 방향으로 맞으면 진입 후보가 됩니다.
3. 쿨다운/최소주문금액/일일손절횟수 검사를 통과하면 진입합니다.
4. 진입 후 손절/익절 자동 관리, SL/TP 도달 시 자동 청산합니다.
5. 매일 `REPORT_HOUR_UTC` 정각에 일일 리포트(승률/손익/보완사항)를 텔레그램으로 보냅니다.

---

## 5) 원하는 신호로 바꾸는 방법

`.env`에서 아래 핵심값을 조정하면 됩니다.

```env
MIN_ENTRY_CONDITIONS=2
CANDLE_GRANULARITY=5m
REPORT_HOUR_UTC=0
STOP_LOSS_PCT=0.01
RISK_REWARD_RATIO=2.0
```

- `MIN_ENTRY_CONDITIONS`: 진입에 필요한 최소 조건 수 (2~6)
- `CANDLE_GRANULARITY`: 신호 계산 캔들 주기
- `REPORT_HOUR_UTC`: 일일 리포트 텔레그램 전송 시각(UTC)

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


### (3) `-File ... 경로에 잘못된 문자가 있습니다` 오류
이 오류는 보통 아래 이유로 발생합니다.
- 복사 과정에서 따옴표가 일반 따옴표가 아니라 특수문자 따옴표(스마트 따옴표)로 바뀜
- 현재 위치가 `봇파일있는곳`이 아님
- 경로 앞뒤에 보이지 않는 공백이 들어감

아래 명령을 **그대로** 입력하세요. (작은따옴표/큰따옴표 없이)

```powershell
cd C:\Users\user\Desktop\yeonwoos-bot
powershell -NoProfile -ExecutionPolicy Bypass -File .\windows\install_autostart.ps1
```

그래도 안 되면 전체 경로로 실행하세요.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\user\Desktop\yeonwoos-bot\windows\install_autostart.ps1
```

마지막 우회 방법(CMD):

```cmd
cd C:\Users\user\Desktop\yeonwoos-bot
windows\install_autostart.cmd
```



### (4) `UnicodeDecodeError: 'utf-8' codec can't decode ...` 오류
이건 대부분 `.env` 파일 인코딩이 UTF-8이 아닐 때 발생합니다.

아래 순서대로 바로 해결하세요.

1) `.env`를 메모장으로 열기  
2) **파일 > 다른 이름으로 저장**  
3) 인코딩을 **UTF-8**로 선택 후 저장  
4) 다시 실행

```powershell
cd C:\Users\user\Desktop\yeonwoos-bot
.\.venv\Scripts\python.exe bot.py
```

빠른 복구(새로 생성) 방법:

```powershell
cd C:\Users\user\Desktop\yeonwoos-bot
del .env
copy .env.example .env
```

그 다음 `.env`에 본인 API 키를 다시 넣고 실행하세요.

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
