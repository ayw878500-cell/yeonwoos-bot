$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

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

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description 'Auto start Bitget bot on logon' -Force | Out-Null
Write-Host "[OK] 작업 스케줄러 등록 완료: $TaskName"
Write-Host '[NEXT] .env에서 DRY_RUN/LIVE_CONFIRM/ARMED_TRADING 설정 후 테스트하세요.'
