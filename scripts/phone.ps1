# Free secure (https) link to Callie for your phone.  Run Callie first (.\scripts\run.ps1), then in a 2nd window:  .\scripts\phone.ps1
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force tools | Out-Null
$exe = ".\tools\cloudflared.exe"

if (-not (Test-Path $exe) -or (Get-Item $exe).Length -lt 10MB) {
    Write-Host "Downloading the tunnel tool once (about 40 MB). If it stops, run this script again - it continues." -ForegroundColor Cyan
    curl.exe -L -C - --retry 30 --retry-delay 3 -o $exe "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    if ($LASTEXITCODE -ne 0) { Write-Host "Download interrupted - run .\scripts\phone.ps1 again." -ForegroundColor Yellow; return }
}

try { Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing -TimeoutSec 3 | Out-Null }
catch { Write-Host "Callie is not running. In another PowerShell window run:  .\scripts\run.ps1" -ForegroundColor Yellow; return }

$log = Join-Path $env:TEMP "callie-tunnel.log"
Remove-Item $log, "$log.out" -ErrorAction SilentlyContinue
Write-Host "Opening the secure link..." -ForegroundColor Cyan
$p = Start-Process $exe -ArgumentList "tunnel", "--url", "http://127.0.0.1:8000", "--no-autoupdate" `
    -RedirectStandardError $log -RedirectStandardOutput "$log.out" -PassThru -WindowStyle Hidden

$url = $null
for ($i = 0; $i -lt 90 -and -not $url; $i++) {
    Start-Sleep 1
    $url = Get-Content $log -ErrorAction SilentlyContinue |
        Select-String -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -AllMatches |
        ForEach-Object { $_.Matches.Value } | Where-Object { $_ -notlike 'https://api.*' } | Select-Object -First 1
}
if (-not $url) {
    if (-not $p.HasExited) { $p | Stop-Process }
    Write-Host "No link yet. Check your internet (VPN off) and run this again." -ForegroundColor Yellow; return
}

Write-Host "`nOpen this on your phone:" -ForegroundColor Green
Write-Host "  $url`n" -ForegroundColor Green
& .\.venv\Scripts\python.exe scripts\qr.py $url
Write-Host "Keep this window open while you test. Press Ctrl+C to close the link."
try { while (-not $p.HasExited) { Start-Sleep 2 } } finally { if (-not $p.HasExited) { $p | Stop-Process } }
