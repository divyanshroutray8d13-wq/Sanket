$ErrorActionPreference = 'Stop'

Write-Host 'Starting SANKET API on http://localhost:8000 ...' -ForegroundColor Green
$api = Start-Process powershell -ArgumentList '-NoExit', '-Command', 'python -m uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000' -PassThru

Start-Sleep -Seconds 2

Write-Host 'Starting SANKET dashboard on http://localhost:5173 ...' -ForegroundColor Green
Set-Location frontend
npm run dev -- --host 127.0.0.1

try {
    Wait-Process -Id $api.Id
} finally {
    if (!$api.HasExited) { Stop-Process -Id $api.Id -Force }
}
