$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# 활성화 스크립트를 실행하지 않고 venv python을 직접 사용 (실행정책 이슈 회피)
python -m venv .venv
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
if (!(Test-Path $VenvPython)) {
  throw "가상환경 Python 생성 실패: $VenvPython"
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements.txt

if (!(Test-Path '.env')) {
  Copy-Item '.env.example' '.env'
  Write-Host '[INFO] .env 파일을 생성했습니다. 키 입력 후 재실행하세요.'
}

# 요청 반영: 기본값을 실전모드로 강제
(Get-Content '.env') `
  -replace '^DRY_RUN=.*', 'DRY_RUN=false' `
  -replace '^LIVE_CONFIRM=.*', 'LIVE_CONFIRM=I_UNDERSTAND_LIVE_TRADING' `
  -replace '^ARMED_TRADING=.*', 'ARMED_TRADING=true' | Set-Content '.env'
Write-Host '[WARN] .env가 실전모드(DRY_RUN=false)로 설정되었습니다.'

$TaskName = 'YeonwooBitgetBot'
$ScriptPath = Join-Path $Root 'windows\run_bot.ps1'

$Action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

try {
  Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description 'Auto start Bitget bot on logon' -Force | Out-Null
  Write-Host "[OK] 작업 스케줄러 등록 완료: $TaskName"
} catch {
  Write-Host "[WARN] 작업 스케줄러 등록 실패(권한 문제 가능): $($_.Exception.Message)"
  Write-Host '[WARN] 시작프로그램(Startup) 방식으로 자동실행을 등록합니다.'

  $startupDir = [Environment]::GetFolderPath('Startup')
  $startupCmd = Join-Path $startupDir 'YeonwooBitgetBot.cmd'
  $cmdLine = "powershell -NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""
  Set-Content -Path $startupCmd -Value $cmdLine -Encoding ASCII

  Write-Host "[OK] 시작프로그램 등록 완료: $startupCmd"
}

Write-Host '[NEXT] .env API 키를 반드시 확인하고 테스트하세요.'
