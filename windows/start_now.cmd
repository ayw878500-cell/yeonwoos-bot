@echo off
setlocal

set SCRIPT_DIR=%~dp0
set ROOT_DIR=%SCRIPT_DIR%..

cd /d "%ROOT_DIR%"
if %ERRORLEVEL% NEQ 0 (
  echo [ERROR] 봇 폴더로 이동 실패: %ROOT_DIR%
  exit /b 1
)

echo [STEP] 설치 스크립트 실행
call "%SCRIPT_DIR%install_autostart.cmd"
if %ERRORLEVEL% NEQ 0 (
  echo [ERROR] 설치 실패
  exit /b %ERRORLEVEL%
)

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv\Scripts\python.exe 파일이 없습니다.
  echo [HINT] python 설치 여부를 확인하고 다시 실행하세요.
  exit /b 1
)

echo [STEP] 봇 즉시 실행
".venv\Scripts\python.exe" bot.py
