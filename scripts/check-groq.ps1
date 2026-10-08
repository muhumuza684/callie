# Diagnoses why the AI can't reach Groq.  .\scripts\check-groq.ps1
Set-Location (Split-Path $PSScriptRoot -Parent)
Write-Host "1) Windows network test to api.groq.com:443" -ForegroundColor Cyan
Test-NetConnection api.groq.com -Port 443 | Select-Object ComputerName, RemoteAddress, TcpTestSucceeded | Format-List
Write-Host "2) Python (what the server uses)" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe scripts\check_groq.py
