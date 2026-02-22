# 비트겟 선물 자동매매 봇 (요청 반영 버전)

요청 반영:
- 레버리지 10배
- 진입 시드 100%
- 하루 목표 수익 10%
- 하루 손절 3회면 당일 거래 중지
- 텔레그램 알림
- 손익비는 전문 트레이더들이 많이 쓰는 1:2 기본 적용
- 6개 지표 조합 + 2개 이상 조건 일치 시 진입
- 5m/15m 추세가 같은 방향일 때 최종 진입 (3m은 참고)
- +2R 도달 시 반익절(50%) + 남은 물량 본절 이동
- 손실 구간 추세 회복 시 제한적 추가진입(최대 1회)
- 손실 발생 시 실시간 자가 피드백 텔레그램 알림
- 매일 정각(UTC 기준 설정) 일일 로그 리포트 텔레그램 전송

---

## 빠른 실행 명령어 (복붙용)

### 윈도우 CMD (가장 쉬움)
```cmd
cd <봇파일있는곳>
copy .env.example .env
windows\start_now.cmd
```

### 윈도우 PowerShell (수동 실행)
```powershell
cd <봇파일있는곳>
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
copy .env.example .env
notepad .env
python bot.py
```

- 최초 점검은 `.env`에서 `DRY_RUN=true`로 먼저 실행 후, 실전 전환 시 `DRY_RUN=false`로 바꾸세요.
- 멀티 심볼 자동 진입은 `.env`에 `AUTO_SCAN_ALL_SYMBOLS=true`를 두면 됩니다.

---

### PowerShell에서 `activate`/`pip` 오류가 날 때
```powershell
cd <봇파일있는곳>
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python bot.py
```
- `activate`는 `Activate.ps1`로 실행해야 합니다.
- `pip`가 안 잡히면 `python -m pip ...` 형태로 실행하세요.

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


### 방법 C (초보자 한방 실행)
```cmd
cd <봇파일있는곳>
windows\start_now.cmd
```
- 설치 + 가상환경 확인 + 즉시 실행을 한 번에 처리합니다.
- 명령어를 한 줄에 이어 쓰다가 생기는 오류를 줄일 수 있습니다.

---


## 2-1) 비트겟 연동 최적화 체크리스트 (오류 최소화)

아래 6가지를 먼저 맞추면 연동 오류가 크게 줄어듭니다.

1. **API 권한**: 선물 거래/조회 권한을 켭니다.
2. **패스프레이즈 오타 확인**: 복사 시 공백이 섞이지 않게 주의합니다.
3. **IP 화이트리스트 사용 시**: 현재 PC 공인 IP를 비트겟에 등록합니다.
4. **시스템 시간 자동 동기화**: Windows 시간 자동 설정 ON (서명 오류 예방).
5. **심볼/상품타입 확인**: `BITGET_SYMBOL`, `BITGET_PRODUCT_TYPE` 값 일치 확인.
6. **포지션 모드 일치**: `POSITION_MODE=hedge`(양방향) 또는 `oneway`(단방향)을 계정과 맞춤.
7. **멀티 심볼 모드 확인**: `AUTO_SCAN_ALL_SYMBOLS=true`, `MAX_SCAN_SYMBOLS=20` 또는 `SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT`
8. **최초 실행은 DRY_RUN 권장**: 연동 점검 후 실전 전환.

봇은 시작 시 자동으로 비트겟 연결 점검(ping + 계좌조회)을 수행하고,
실패하면 자동 재시도(backoff)합니다.

---

## 3) .env 입력 (진짜 중요)

`.env` 파일 열고 아래는 꼭 채우세요.

```env
BITGET_API_KEY=내키
BITGET_API_SECRET=내시크릿
BITGET_API_PASSPHRASE=내패스프레이즈
POSITION_MODE=hedge
AUTO_SCAN_ALL_SYMBOLS=true
MAX_SCAN_SYMBOLS=20
SYMBOLS=

TELEGRAM_BOT_TOKEN=내텔레그램봇토큰
TELEGRAM_CHAT_ID=내채팅아이디
```

기본값은 이미 요청대로 세팅돼 있습니다.

```env
LEVERAGE=10
ENTRY_FRACTION=1.0
USE_AVAILABLE_BALANCE_SIZING=true
FULL_BALANCE_ENTRY=true
MAX_DAILY_STOPLOSS=3
DAILY_TARGET_PCT=0.1
STOP_LOSS_PCT=0.01
RISK_REWARD_RATIO=2.0
MIN_ENTRY_CONDITIONS=2
ORDER_SIZE_BUFFER=0.9
REPORT_HOUR_UTC=0
DRY_RUN=false
POSITION_MODE=hedge
AUTO_SCAN_ALL_SYMBOLS=true
MAX_SCAN_SYMBOLS=20
SYMBOLS=
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
PARTIAL_TAKE_PROFIT_RR=2.0
```

보통 많이 쓰는 범위:
- `RISK_REWARD_RATIO`: 1.5 ~ 3.0 (기본 2.0 권장)
- `PARTIAL_TAKE_PROFIT_RR`: 1.5 ~ 3.0 (기본 2.0 권장)

---


추가(손실 관리):
```env
ADD_ON_LOSS_TRIGGER_PCT=0.006
ADD_ON_LOSS_FRACTION=0.25
MAX_ADD_COUNT=1
LOSS_FEEDBACK_TRIGGER_PCT=0.004
FEEDBACK_INTERVAL_SEC=300
```
- 손실 -0.6% 이상에서 추세/신호가 다시 맞으면 최대 1회 추가진입
- 손실 -0.4% 이상이면 5분마다 실시간 피드백 알림

## 4) 매매 동작 방식 (복잡하지 않게)

1. 비트겟 캔들 데이터를 받아 6개 지표를 계산합니다.
   - BB(20, 2.4), EMA Cross(9/21), EMA200(EMA3 스무딩), VWAP(hlc3), RSI(7/EMA3), Stoch(5,3,3)
2. 5m 기준으로 매수/매도 조건 중 **2개 이상** 같은 방향이면 진입 후보가 됩니다.
3. 5m/15m 추세가 같은 방향인지 확인하고, 같을 때만 진입합니다. (3m은 참고용 로그)
4. 기본 모드(`FULL_BALANCE_ENTRY=true`)에서는 신호 발생 시 실시간 가용잔고(`available`) 전액으로 바로 진입 시도합니다.
   잔고초과(code=40762)가 발생하면 실시간 가용잔고를 재조회해서 소액(0.01 USDT) 단위로만 줄여 최대 5회 자동 재시도합니다.
5. `FULL_BALANCE_ENTRY=false`일 때는 실시간 가용잔고(`available`) × `ENTRY_FRACTION` 방식으로 진입합니다.
6. 쿨다운/최소주문금액/일일손절횟수 검사를 통과하면 진입합니다.
7. 진입 후 손절/익절 자동 관리, SL/TP 도달 시 자동 청산합니다.
8. +2R(기본 2.0R) 도달 시 50% 반익절 후 남은 포지션 손절가를 본절(진입가)로 이동합니다.
9. 손실이 커지는 구간에서는 5m/15m 추세 재정렬 + 신호강도 조건 충족 시 최대 `MAX_ADD_COUNT`만큼만 추가진입합니다.
10. 손실이 `LOSS_FEEDBACK_TRIGGER_PCT`를 넘으면 `FEEDBACK_INTERVAL_SEC`마다 실시간 피드백 알림을 텔레그램으로 보냅니다.
11. 매일 `REPORT_HOUR_UTC` 정각에 일일 리포트(승률/손익/보완사항)를 텔레그램으로 보냅니다.

### 4-1) 내가 요청한 지표를 실제로 어떻게 쓰는지 (쉬운 설명)

아래처럼 **각 지표를 점수 1개**로 보고, 같은 방향 점수가 `MIN_ENTRY_CONDITIONS` 이상일 때만 진입 후보가 됩니다.

1. **BB(20, 2.4)**
   - 가격이 아래 밴드에 닿으면: 매수 쪽 점수 +1
   - 가격이 위 밴드에 닿으면: 매도 쪽 점수 +1

2. **EMA Cross(9/21)**
   - EMA9가 EMA21을 위로 뚫으면: 매수 점수 +1
   - EMA9가 EMA21을 아래로 뚫으면: 매도 점수 +1

3. **EMA200 + EMA3 스무딩**
   - 현재 가격이 EMA200(EMA3으로 부드럽게 만든 값) 위면: 매수 점수 +1
   - 아래면: 매도 점수 +1

4. **VWAP(hlc3, session)**
   - 현재 hlc3가 VWAP 위면: 매수 점수 +1
   - 아래면: 매도 점수 +1

5. **RSI(7) + EMA3 스무딩**
   - RSI(스무딩) < 30: 매수 점수 +1
   - RSI(스무딩) > 70: 매도 점수 +1

6. **Stoch(5,3,3)**
   - K가 D를 아래에서 위로 뚫고 K<30이면: 매수 점수 +1
   - K가 D를 위에서 아래로 뚫고 K>70이면: 매도 점수 +1

마지막으로, 위 점수로 나온 방향이 **5m/15m 추세 방향과 같을 때만** 실제 주문으로 진행합니다. (3m은 참고)

---

## 4-2) 멀티 심볼 자동 진입

- 기본은 `AUTO_SCAN_ALL_SYMBOLS=true`로 USDT 선물 심볼을 자동 스캔합니다.
- `MAX_SCAN_SYMBOLS` 만큼만 스캔해서 과부하를 막습니다.
- 특정 심볼만 쓰고 싶으면 `SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT` 처럼 직접 지정하세요.

---

## 5) 원하는 신호로 바꾸는 방법

`.env`에서 아래 핵심값을 조정하면 됩니다.

```env
MIN_ENTRY_CONDITIONS=2
REPORT_HOUR_UTC=0
STOP_LOSS_PCT=0.01
RISK_REWARD_RATIO=2.0
```

- `MIN_ENTRY_CONDITIONS`: 진입에 필요한 최소 조건 수 (2~6)
- 타임프레임은 5m/15m 추세 일치를 필수로 사용하고, 3m은 참고 로그로 사용합니다.
- `REPORT_HOUR_UTC`: 일일 리포트 텔레그램 전송 시각(UTC)

---

## 6) 실행 확인

```powershell
cd <봇파일있는곳>
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe bot.py
```

로그 파일:
- `logs/bot.log` (일별 롤링)
- `logs/bot.out.log`
- `logs/bot.err.log`

실행 직후 아래 문구가 뜨면 연동 성공입니다.
- `[CHECK] 비트겟 API 연결 확인 완료`
- 텔레그램 `✅ 비트겟 연동 확인 완료` 메시지

---

## 7) 자주 나는 오류

### (1) 디지털 서명/실행정책 오류
`install_autostart.cmd`로 실행하면 우회됩니다.

### (2) Register-ScheduledTask 액세스 거부(0x80070005)
권한 문제입니다. 스크립트가 자동으로 Startup 방식으로 등록합니다.


### (3) 명령어를 한 줄에 붙여쓴 경우 오류
`powershell ... .ps1Test-Path ...`처럼 붙으면 PowerShell이 파일명을 잘못 읽습니다.
명령어는 반드시 **줄바꿈해서 한 줄씩** 실행하세요. 가장 쉬운 방법은 `windows\start_now.cmd` 한 줄 실행입니다.

### (4) `-File ... 경로에 잘못된 문자가 있습니다` 오류
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



### (5) `400 Client Error: Bad Request` 주문 오류
이제 로그에 `status/code/msg/payload`가 같이 찍히도록 보강했습니다.

이 오류가 나오면 아래 순서로 점검하세요.
1) `.env`의 `BITGET_SYMBOL`, `BITGET_PRODUCT_TYPE`, `BITGET_MARGIN_COIN` 값이 거래창과 같은지
2) API 권한(선물 거래/조회) + IP 화이트리스트 설정
3) 포지션 모드(원웨이/헤지)와 `POSITION_MODE` 값 일치 여부
4) 주문 size 단위(USDT/계약수) 규칙 확인
5) 주문 직전에 실시간 가용잔고를 다시 조회해 주문금액을 자동 상한 처리합니다.
6) `FULL_BALANCE_ENTRY=true`에서는 가용잔고(`available`) 전액으로 먼저 주문합니다.
7) `code=40762`가 나면 가용잔고를 다시 조회해 0.01 USDT씩만 줄여 최대 5회 자동 재시도합니다.
8) 그래도 실패하면 해당 신호를 스킵합니다.
9) `FULL_BALANCE_ENTRY=false` 모드에서는 기존처럼 `ORDER_SIZE_BUFFER` 기반 1회 축소 재시도를 사용합니다.
10) 잔고 부족 스킵이 발생하면 `SIGNAL_COOLDOWN_SEC` 쿨다운을 강제로 적용해 같은 실패 알림 반복을 줄입니다.


### (6) `UnicodeDecodeError: 'utf-8' codec can't decode ...` 오류
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
