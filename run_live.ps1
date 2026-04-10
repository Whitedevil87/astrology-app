# Start Celestial Arc so it is reachable on your network (not only localhost).
# Open from this PC: http://127.0.0.1:5000
# Open from phone on same Wi‑Fi: http://YOUR_PC_IP:5000  (find IP via ipconfig)

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    .\.venv\Scripts\Activate.ps1
}

$env:FLASK_HOST = "0.0.0.0"
$env:FLASK_PORT = "5000"
$env:FLASK_DEBUG = "true"

Write-Host "Starting server on 0.0.0.0:5000 ..." -ForegroundColor Cyan
Write-Host "Local:  http://127.0.0.1:5000" -ForegroundColor Green

python app.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "If 'python' failed, try: py app.py" -ForegroundColor Yellow
}
