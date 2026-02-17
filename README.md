# Yeonwoo's Bitget Bot (윈도우 실전운영형)

원하신 것처럼 **PowerShell만 열어도 자동 실행**되게 만들 수 있도록,
윈도우 작업 스케줄러 기반 자동시작 스크립트를 포함했습니다.

다만 중요한 점:
- 100% 무오류 자동매매는 불가능합니다.
- 대신 이 저장소는 **실수 방지 장치(보호장치)**를 여러 겹 넣었습니다.

## 0) 진짜 필수 순서(이 순서만 따라하세요)

아래 10단계만 순서대로 하면 됩니다. (중간에 건너뛰지 마세요)

1. PowerShell을 **관리자 권한**으로 실행
2. 프로젝트 폴더 이동: `cd <프로젝트_폴더>`
3. 실행정책 1회 설정: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
4. 자동시작 설치 스크립트 실행: `.\windows\install_autostart.ps1`
5. 생성된 `.env` 파일 열기
6. `BITGET_API_KEY`, `BITGET_API_SECRET`, `BITGET_API_PASSPHRASE` 입력
7. 처음엔 반드시 아래 3개로 저장
   - `DRY_RUN=true`
   - `LIVE_CONFIRM=` (빈값)
   - `ARMED_TRADING=false`
8. 수동 테스트 1회: `.\.venv\Scripts\python.exe bot.py`
9. 로그 확인: `logs/bot.out.log`, `logs/bot.err.log`
10. 3~7일 이상 문제 없을 때만 실전 전환

### 실전 전환은 이 3개를 **동시에** 바꿀 때만

```env
DRY_RUN=false
LIVE_CONFIRM=I_UNDERSTAND_LIVE_TRADING
ARMED_TRADING=true
```

> 셋 중 하나라도 틀리면 실주문은 차단됩니다.

---

## 실전 보호장치

- `DRY_RUN=true` 기본값 (실주문 차단)
- 실주문 2중 잠금 해제:
  - `DRY_RUN=false`
  - `LIVE_CONFIRM=I_UNDERSTAND_LIVE_TRADING`
  - `ARMED_TRADING=true`
- 일일 주문 제한: `MAX_ORDERS_PER_DAY`
- 시그널 쿨다운: `SIGNAL_COOLDOWN_SEC`
- 최소 주문 증거금: `MIN_ORDER_MARGIN_USDT`
- 연속 오류 회로차단: `MAX_CONSECUTIVE_ERRORS` + `ERROR_COOLDOWN_SEC`

---

## 1) 윈도우에서 1회 설치 (자동시작 등록)

PowerShell(관리자 권장)에서:

```powershell
cd <프로젝트_폴더>
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\windows\install_autostart.ps1
```

이 스크립트가 하는 일:
1. 가상환경 생성
2. 패키지 설치
3. `.env` 없으면 자동 생성
4. 작업 스케줄러에 `YeonwooBitgetBot` 등록 (로그온 시 자동 실행)

---

## 2) `.env` 설정 (실전 핵심)

`.env` 파일에 API 키를 넣고, 아래 항목을 확인하세요.

```env
DRY_RUN=true
LIVE_CONFIRM=
ARMED_TRADING=false
```

### 실전 전환 시에만 이렇게 변경

```env
DRY_RUN=false
LIVE_CONFIRM=I_UNDERSTAND_LIVE_TRADING
ARMED_TRADING=true
```

> 위 3개가 동시에 맞아야만 실주문이 나갑니다.

---

## 3) 자동실행 확인

로그 파일:
- `logs/bot.out.log`
- `logs/bot.err.log`

작업 스케줄러 이름:
- `YeonwooBitgetBot`

수동으로 실행해볼 때:

```powershell
.\.venv\Scripts\python.exe bot.py
```

---

## 4) PR 브랜치 바로 받기 (윈도우)

```powershell
git fetch origin pull/123/head:pr-123
git switch pr-123
```

---

## 5) 자주 나는 오류

### `ModuleNotFoundError: No module named 'requests'`

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -c "import requests; print(requests.__version__)"
```

또는 강제 실행:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe bot.py
```

---

## 6) 운영 권장

1. 최소 3~7일 `DRY_RUN=true` 검증
2. 소액 실전부터 시작
3. `LEVERAGE`, `ENTRY_FRACTION` 낮게 시작
4. 손실 급증 시 즉시 중단

---

## 면책

교육/연구용 템플릿입니다. 실거래 손익 책임은 사용자 본인에게 있습니다.
