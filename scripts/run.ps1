Set-Location (Split-Path $PSScriptRoot -Parent)
Start-Job { Start-Sleep 3; Start-Process "http://127.0.0.1:8000/" } | Out-Null
& .\.venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload --no-server-header
