# One-shot setup:  .\scripts\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) { throw "Python not found. Install Python 3.10+ from python.org (tick 'Add to PATH')." }
if (-not (Test-Path .venv)) { & $py.Source -m venv .venv }
$vpy = ".\.venv\Scripts\python.exe"

& $vpy -m pip install -r requirements-base.txt -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency install failed - re-run this script (it resumes)." }

if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Groq retired llama-3.1-8b-instant for free keys - migrate an old .env
(Get-Content .env) -replace 'GROQ_LLM_MODEL=llama-3.1-8b-instant','GROQ_LLM_MODEL=openai/gpt-oss-20b' -replace 'GREETING=Hello! How can I help\?','GREETING=Hi, it''s Callie. How can I help?' | Set-Content .env -Encoding ascii

Write-Host "`nRunning tests..." -ForegroundColor Cyan
& $vpy -m pytest -q tests --ignore=tests/test_audio.py
if ($LASTEXITCODE -ne 0) { throw "Tests failed - paste the output above into the chat." }

if (-not (Select-String -Path .env -Pattern '^GROQ_API_KEY=\S' -Quiet)) { & .\scripts\configure.ps1 }
Write-Host "`nSetup OK. Start with:  .\scripts\run.ps1" -ForegroundColor Green
