# Saves your free Groq API key into .env  (get one at https://console.groq.com/keys)
Set-Location (Split-Path $PSScriptRoot -Parent)
$key = (Read-Host "Paste your Groq API key (starts with gsk_)").Trim()
if (-not $key) { Write-Host "No key entered. Run .\scripts\configure.ps1 again when you have it." -ForegroundColor Yellow; return }
$lines = Get-Content .env.example | ForEach-Object { if ($_ -like "GROQ_API_KEY=*") { "GROQ_API_KEY=$key" } else { $_ } }
Set-Content -Path .env -Value $lines -Encoding ascii
Write-Host "Saved to .env" -ForegroundColor Green
