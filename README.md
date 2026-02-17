# 비트겟 자동매매 봇 (완전 쉬운 설명)

이 파일은 **컴퓨터 초보도 따라할 수 있게** 쓴 설명서입니다.
어려운 말은 최대한 빼고, 꼭 필요한 것만 순서대로 적었습니다.

---

## 0. 먼저 꼭 알아야 하는 것

- 이 프로그램은 자동으로 매매를 도와주는 도구예요.
- 돈을 무조건 벌게 해주는 프로그램은 절대 아니에요.
- 그래서 처음에는 **연습모드(DRY_RUN=true)** 로만 사용해야 해요.

---

## 1. 준비물

1) Windows 컴퓨터
2) Python 설치
3) 비트겟 API 정보 3개
- API KEY
- SECRET
- PASSPHRASE

---

## 2. 딱 한 번만 하는 설치 (복붙 순서)

PowerShell을 관리자 권한으로 열고, 아래를 순서대로 입력하세요.

```powershell
cd <프로젝트_폴더>
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\windows\install_autostart.ps1
```

여기까지 하면 자동 실행 준비가 끝나요.

---

## 3. `.env` 파일에 내 정보 넣기

프로젝트 폴더에 있는 `.env` 파일을 열고 아래 3개를 내 값으로 바꾸세요.

- `BITGET_API_KEY=...`
- `BITGET_API_SECRET=...`
- `BITGET_API_PASSPHRASE=...`

그리고 처음에는 아래처럼 꼭 저장하세요.

```env
DRY_RUN=true
LIVE_CONFIRM=
ARMED_TRADING=false
```

이 상태는 **실제 주문이 절대 안 나가는 연습모드**예요.

---

## 4. 실행 확인 (진짜 중요한 확인)

PowerShell에서 아래 실행:

```powershell
.\.venv\Scripts\python.exe bot.py
```

로그 파일도 확인:
- `logs/bot.out.log`
- `logs/bot.err.log`

오류가 없으면 정상이에요.

---

## 5. 자동실행 확인

이 봇은 Windows 로그인하면 자동 실행되도록 되어 있어요.
작업 스케줄러에서 아래 이름을 확인하세요.

- `YeonwooBitgetBot`

---

## 6. 실전으로 바꿀 때 (정말 조심)

아래 3개를 **같이** 바꿔야 실주문이 나가요.

```env
DRY_RUN=false
LIVE_CONFIRM=I_UNDERSTAND_LIVE_TRADING
ARMED_TRADING=true
```

셋 중 하나라도 다르면 실주문이 안 나가게 막아놨어요.

---

## 7. 자주 나는 오류 해결

### `No module named 'requests'` 라고 뜰 때

아래를 그대로 실행하세요.

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -c "import requests; print(requests.__version__)"
```

버전 숫자가 나오면 해결된 거예요.

---

## 8. 꼭 지켜야 하는 안전 순서

1. 연습모드로 3~7일 먼저 돌리기
2. 아주 작은 금액으로 실전 시작
3. 문제 생기면 바로 중지
4. 로그 보고 원인 확인 후 다시 시작

---

## 마지막 한 줄 요약

**처음에는 무조건 DRY_RUN=true, 익숙해진 뒤에만 실전 전환하세요.**

---

## 면책

이 코드는 공부/연습용입니다. 손실 책임은 본인에게 있습니다.
