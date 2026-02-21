
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-Not (Test-Path ".venv")) {
  python -m venv .venv
}

if ($env:OS -eq "Windows_NT") {
  . .venv\Scripts\Activate.ps1
} else {
  . .venv/bin/activate
}

python -m pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt

python -m telegram_bot
