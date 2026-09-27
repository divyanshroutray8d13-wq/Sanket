param(
  [string]$TrainNo = "12951",
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

Write-Host "Starting SANKET live API on http://127.0.0.1:$Port ..." -ForegroundColor Cyan
Write-Host "Live responses are cached by the API for 90 seconds to protect RailRadar quota." -ForegroundColor DarkGray

python -m uvicorn src.api.main:app --host 127.0.0.1 --port $Port
