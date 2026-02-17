# Yeonwoo's Bitget Bot (초간단 적용 가이드)

이 프로젝트는 **Bitget 선물 자동매매 봇 템플릿**입니다.

> ⚠️ 먼저 꼭 읽기: `10배 레버리지 + 시드 50% 진입 + 일 10% 꾸준 수익`은 현실적으로 매우 위험합니다. 이 코드는 “돈 복사기”가 아니라, **실수/과도한 리스크를 줄이기 위한 연습용 구조**입니다.

---

## 0. 딱 1분 요약 (진짜 쉬운 버전)

1. 컴퓨터에 Python 설치
2. 이 폴더에서 터미널 열기
3. 아래 명령어 5줄 그대로 입력
4. `.env` 파일에 내 Bitget 키 입력
5. `DRY_RUN=true`로 먼저 연습 실행
6. 로그가 잘 나오면 아주 소액으로만 테스트

---

## 1. 준비물 (초등학생 버전)

- **Python 3.10+**
- **Bitget API 키 3개**
  - API Key
  - Secret Key
  - Passphrase
- 인터넷 되는 컴퓨터

---

## 2. 윈도우에서 실행할 명령어 (복붙용)

아래는 **Windows PowerShell 기준**입니다.

### 2-1) PowerShell (추천)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
copy .env.example .env
python bot.py
```

### 2-2) CMD(명령 프롬프트)

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
copy .env.example .env
python bot.py
```

> 만약 PowerShell에서 실행 정책 오류가 나오면, PowerShell을 관리자 권한으로 열고 아래 1회 실행 후 다시 시도하세요.

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```


## 2-3) 오류 해결: `ModuleNotFoundError: No module named 'requests'`

이 에러는 대부분 **다른 파이썬**으로 실행했을 때 발생합니다.
(예: 설치는 전역 파이썬에 했는데 실행은 가상환경 파이썬으로 하거나 그 반대)

아래 4줄을 그대로 다시 실행하세요.

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -c "import requests; print(requests.__version__)"
```

버전 숫자가 출력되면 정상입니다. 그다음 실행:

```powershell
python bot.py
```

가상환경 활성화가 헷갈리면, 아래처럼 **가상환경 파이썬을 직접 지정**해서 실행하면 가장 안전합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe bot.py
```

---

## 2-4) PR(브랜치)로 바로 내려받기 가능한가?

가능합니다. 다만 **ZIP 다운로드보다 Git으로 받는 방식**이 가장 안전합니다.

### 방법 A) 현재 브랜치(최신 커밋) 그대로 받기

```powershell
git clone <YOUR_REPO_URL>
cd yeonwoos-bot
git pull
```

### 방법 B) 특정 PR 번호를 바로 받아서 테스트하기

원격이 `origin`이고 PR 번호가 `123`일 때:

```powershell
git fetch origin pull/123/head:pr-123
git switch pr-123
```

그 다음 실행:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python bot.py
```

> 참고: 위 `git fetch origin pull/<번호>/head:<로컬브랜치>` 방식은 GitHub 저장소에서 PR 내용을 바로 내려받는 표준 패턴입니다.

---

성공하면 이런 느낌 로그가 나옵니다.

- `[START] bot running... DRY_RUN= True`
- `[SIGNAL] ...`
- `[DRY_RUN] order skipped`

`DRY_RUN`이 True면 **실제 주문은 안 들어갑니다**.

---

## 3. `.env` 파일 입력 방법 (가장 중요)

`.env` 파일을 열어서 아래 값을 내 정보로 바꾸세요.

```env
BITGET_API_KEY=여기에_내_API_KEY
BITGET_API_SECRET=여기에_내_SECRET
BITGET_API_PASSPHRASE=여기에_내_PASSPHRASE

BITGET_BASE_URL=https://api.bitget.com
BITGET_SYMBOL=BTCUSDT
BITGET_PRODUCT_TYPE=USDT-FUTURES
BITGET_MARGIN_COIN=USDT

LEVERAGE=3
ENTRY_FRACTION=0.1
RISK_PER_TRADE=0.01
STOP_LOSS_PCT=0.01
TAKE_PROFIT_PCT=0.02

DRY_RUN=true
LOOP_INTERVAL_SEC=15
```

### 값 뜻 쉽게 설명

- `LEVERAGE=3` → 레버리지 3배
- `ENTRY_FRACTION=0.1` → 내 자산의 10%만 한 번에 사용
- `RISK_PER_TRADE=0.01` → 한 번 트레이드에서 전체 자산의 1%만 위험 허용
- `STOP_LOSS_PCT=0.01` → -1% 가면 손절
- `TAKE_PROFIT_PCT=0.02` → +2% 가면 익절
- `DRY_RUN=true` → 종이매매(연습모드), 주문 안 나감

---

## 4. “언제 진입하냐?” (전략)

현재 예시 전략은 단순합니다.

- 최근 가격의 평균선 20개(빠른선)와 60개(느린선)를 비교
- 빠른선이 느린선 위로 올라가면 `buy`
- 아래로 내려가면 `sell`

즉, **EMA(20/60) 크로스 예제**입니다.

---

## 5. 안전장치 (코드가 자동으로 막는 것)

코드에서 아래를 강제로 체크합니다.

- `LEVERAGE`는 **1~10**만 허용
- `ENTRY_FRACTION`은 **0~0.5 이하**만 허용
- `RISK_PER_TRADE`는 **0~0.02 이하**만 허용

이 값 이상으로 올리면 실행 중 에러로 막습니다.

---

## 6. 실전 적용 순서 (아주 중요)

아래 순서를 꼭 지키세요.

1. **DRY_RUN=true** 로 최소 며칠 로그 확인
2. 진입/청산 신호가 내가 이해한 것과 맞는지 확인
3. 그 다음 **아주 소액**으로 테스트
4. 이상 없을 때만 천천히 사이즈 증가
5. 손실 커지면 즉시 중지하고 원인 점검

---

## 7. 자주 하는 실수 5개

1. API 키 권한을 과하게 줌 (출금 권한 금지)
2. DRY_RUN 끄고 바로 큰 금액 진입
3. 손절/익절 숫자를 비정상으로 입력
4. 서버 시간/네트워크 오류 무시
5. 백테스트 없이 실전부터 시작

---

## 8. 파일 구조

- `bot.py`: 메인 실행 루프
- `config.py`: `.env` 읽기 + 값 검증
- `risk.py`: 포지션 크기/손절/익절 계산
- `strategy.py`: EMA 20/60 시그널
- `bitget_client.py`: Bitget API 서명/요청
- `.env.example`: 환경변수 샘플

---

## 9. 마지막 체크리스트

- [ ] `.env`에 내 키를 정확히 넣었는가?
- [ ] `DRY_RUN=true` 상태로 먼저 실행했는가?
- [ ] 로그를 보고 전략 동작을 이해했는가?
- [ ] 첫 실전 금액을 매우 작게 잡았는가?

---

## 면책

이 코드는 교육/연구 목적입니다. 투자 손실 책임은 사용자에게 있습니다.
