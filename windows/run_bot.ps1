$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
if (!(Test-Path $VenvPython)) {
  throw "가상환경 Python을 찾을 수 없습니다: $VenvPython"
}

$LogDir = Join-Path $Root 'logs'
if (!(Test-Path $LogDir)) {
  New-Item -Path $LogDir -ItemType Directory | Out-Null
}

$OutLog = Join-Path $LogDir 'bot.out.log'
$ErrLog = Join-Path $LogDir 'bot.err.log'

while ($true) {
  & $VenvPython bot.py 1>> $OutLog 2>> $ErrLog
  Start-Sleep -Seconds 10
}
