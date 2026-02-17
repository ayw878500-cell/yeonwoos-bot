# 비트겟 자동매매 봇 (완전 쉬운 설명 + 사전작업부터 끝까지)

이 문서는 **컴퓨터 초보도 그대로 따라할 수 있게** 썼습니다.
이번에는 띄엄띄엄이 아니라, **시작 전에 뭘 준비해야 하는지(사전작업)**부터 순서대로 설명합니다.

---

## 0) 진짜 먼저: 쉬운 단어 설명

- **PowerShell**: 윈도우에서 명령어 입력하는 검은/파란 창
- **폴더**: 파일 들어있는 보관함
- **프로젝트 폴더**: 이 봇 파일들이 들어있는 폴더 (`bot.py`, `README.md` 있는 곳)
- **API KEY / SECRET / PASSPHRASE**: 비트겟 계정과 프로그램을 연결하는 비밀번호 3종 세트
- **.env 파일**: 내 키/설정을 적어두는 메모장 파일
- **실전모드**: 진짜 주문이 나가는 모드
- **로그(log)**: 프로그램이 무슨 일을 했는지 기록한 일지

---

## 1) 사전작업 (이거 먼저 안 하면 뒤에서 막힙니다)

### 1-1. Python 설치
1. 브라우저에서 `python.org` 접속
2. Python 3.10 이상 설치
3. 설치할 때 **Add Python to PATH** 체크

확인 방법(필수):
```powershell
python --version
```
버전 숫자가 나오면 성공입니다.

### 1-2. Git 설치 (PR 내려받을 때 필요)
1. 브라우저에서 `git-scm.com` 접속
2. 기본 옵션으로 설치

확인 방법:
```powershell
git --version
```

### 1-3. 비트겟 API 만들기
비트겟에서 API를 만들고 아래 3개를 따로 메모해두세요.
- API KEY
- SECRET
- PASSPHRASE

> 아주 중요: 출금 권한은 주지 마세요.

### 1-4. 프로젝트 폴더 준비
`프로젝트 폴더`는 **이 봇 파일들이 들어있는 실제 폴더**를 말합니다.
즉, 폴더 안에 최소한 아래 파일이 보여야 합니다.
- `README.md`
- `bot.py`
- `requirements.txt`
- `windows` 폴더

예시 경로:
```text
C:\Users\내이름\Desktop\yeonwoos-bot
```

#### 이미 GitHub에서 받아둔 경우
그 폴더로 이동만 하면 됩니다.

```powershell
cd C:\Users\user\Desktop\yeonwoos-bot
```

#### 아직 폴더가 없는 경우 (처음부터 만드는 법)
아래를 그대로 입력하면 폴더 생성 + 코드 다운로드가 됩니다.

```powershell
cd C:\Users\user\Desktop
git clone <저장소주소> yeonwoos-bot
cd yeonwoos-bot
```

---

## 2) 설치 순서 (복붙용, 한 줄씩 그대로)

PowerShell을 **관리자 권한**으로 열고 아래 순서대로 입력:

### 방법 A (추천, 실행정책 오류 회피)
```powershell
cd <프로젝트_폴더>
powershell -NoProfile -ExecutionPolicy Bypass -File .\windows\install_autostart.ps1
```

### 방법 B (CMD에서 더블클릭/실행)
```cmd
cd <프로젝트_폴더>
windows\install_autostart.cmd
```

> `파일이 디지털 서명되지 않았습니다` 오류가 있으면, 방법 A 또는 B를 사용하면 됩니다.

여기까지 하면:
- 가상환경 생성
- 필요한 패키지 설치
- `.env` 파일 준비
- 윈도우 로그인 시 자동실행 등록
이 끝납니다.

---

## 3) `.env` 파일 채우기 (가장 중요)

프로젝트 폴더의 `.env` 파일을 메모장으로 열고,
아래 3줄을 **내 진짜 값**으로 바꾸세요.

```env
BITGET_API_KEY=여기에_내_API키
BITGET_API_SECRET=여기에_내_SECRET
BITGET_API_PASSPHRASE=여기에_내_패스프레이즈
```

현재 기본값은 요청에 따라 실전모드입니다:

```env
DRY_RUN=false
LIVE_CONFIRM=I_UNDERSTAND_LIVE_TRADING
ARMED_TRADING=true
```

뜻:
- `DRY_RUN=false` = 연습이 아니라 실제 주문 허용
- `LIVE_CONFIRM=...` = 실전모드 확인 문구
- `ARMED_TRADING=true` = 실전모드 스위치 ON

---

## 4) 첫 실행 확인 (무조건 해야 함)

먼저 가상환경 파이썬이 있는지 확인:

```powershell
cd <프로젝트_폴더>
.\.venv\Scripts\python.exe --version
```

버전이 나오면 아래 실행:

```powershell
.\.venv\Scripts\python.exe bot.py
```

이제 로그를 확인하세요:
- `logs/bot.out.log`
- `logs/bot.err.log`

체크 포인트:
1. 에러가 계속 쌓이지 않는지
2. API 인증 오류가 없는지
3. 주문 관련 메시지가 정상적으로 찍히는지

---

## 5) 자동실행 확인 (컴퓨터 켤 때 자동)

1. `작업 스케줄러` 열기
2. `작업 스케줄러 라이브러리` 클릭
3. `YeonwooBitgetBot` 작업 있는지 확인
4. 상태가 Ready/Running인지 확인

---

## 6) 오류 나면 이렇게 해결

### 6-1. `No module named 'requests'`
```powershell
cd <프로젝트_폴더>
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -c "import requests; print(requests.__version__)"
```

### 6-2. PowerShell 실행정책 오류
아래 둘 중 하나로 실행하면 됩니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\windows\install_autostart.ps1
```

```cmd
windows\install_autostart.cmd
```

### 6-3. API 인증 실패
- `.env`의 KEY/SECRET/PASSPHRASE 오타 확인
- 앞뒤 공백 확인
- 비트겟에서 API 권한/상태 확인


### 6-4. `Register-ScheduledTask : 액세스가 거부되었습니다 (0x80070005)`
이건 보통 **작업 스케줄러 등록 권한 부족** 때문에 나옵니다.

이번 스크립트는 이 오류가 나면 자동으로 **시작프로그램(Startup)** 방식으로 바꿔 등록합니다.
그래서 설치를 다시 한 번 실행하면 됩니다.

```powershell
cd <프로젝트_폴더>
powershell -NoProfile -ExecutionPolicy Bypass -File .\windows\install_autostart.ps1
```

설치 후 아래 파일이 생기면 정상입니다.
- `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\YeonwooBitgetBot.cmd`

---

## 7) 진짜 마지막 체크리스트

- [ ] Python 설치 확인했는가? (`python --version`)
- [ ] Git 설치 확인했는가? (`git --version`)
- [ ] `.env`에 내 API 3개 정확히 넣었는가?
- [ ] 로그 파일에서 에러 없는지 봤는가?
- [ ] 자동실행 작업(`YeonwooBitgetBot`)이 등록됐는가?

---

## 면책

이 코드는 교육/연습용입니다. 실거래 손익 책임은 사용자 본인에게 있습니다.
