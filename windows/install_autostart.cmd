@echo off
setlocal
set SCRIPT_DIR=%~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%install_autostart.ps1"
if %ERRORLEVEL% NEQ 0 (
  echo.
  echo [ERROR] install_autostart.ps1 실행에 실패했습니다.
  exit /b %ERRORLEVEL%
)
echo.
echo [OK] 설치 스크립트 실행 완료
