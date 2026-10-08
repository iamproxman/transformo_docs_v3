Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " Starting TransformoDocs Server with Virtual Environment" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan
Set-Location -Path $PSScriptRoot
& ".\.venv\Scripts\uvicorn.exe" app.main:app --reload --host 127.0.0.1 --port 8000
