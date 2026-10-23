# Callie launcher: finds the project, offers updates from your Downloads, installs what is missing, starts Callie.
param([ValidateSet("menu", "pc", "phone", "folder", "code", "push", "release", "clean")][string]$Mode = "menu")
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

function Get-Version([string]$s) { if ($s -match 'v(\d+)') { [int]$Matches[1] } else { 0 } }
function Test-Callie { try { Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing -TimeoutSec 2 | Out-Null; $true } catch { $false } }
function Stop-Here($msg) { Write-Host $msg -ForegroundColor Yellow; Read-Host "Press Enter to close" | Out-Null; exit }

$installed = 0
if (Test-Path "$Root\VERSION") { $installed = [int]((Get-Content "$Root\VERSION" -Raw).Trim()) }
Write-Host "Callie v$installed  -  $Root" -ForegroundColor Green

# 1) update from a newer zip in Downloads
$dirs = @("D:\Downloads", (Join-Path $env:USERPROFILE "Downloads")) | Where-Object { Test-Path $_ }
$zip = $dirs | ForEach-Object { Get-ChildItem $_ -Filter "voice-ai-pwa-v*.zip" -ErrorAction SilentlyContinue } |
    Sort-Object { Get-Version $_.Name } -Descending | Select-Object -First 1
if ($zip -and (Get-Version $zip.Name) -gt $installed) {
    $ans = Read-Host "New version found: $($zip.Name). Apply it? (Y/n)"
    if ($ans -ne "n") {
        $tmp = Join-Path $env:TEMP "callie-update"
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
        Expand-Archive $zip.FullName -DestinationPath $tmp -Force
        $src = Get-ChildItem $tmp -Directory | Select-Object -First 1
        robocopy $src.FullName $Root /E /XD .venv data tools /XF .env /NFL /NDL /NJH /NJS /NP | Out-Null
        $stale = Join-Path $Root "scripts\stale.txt"      # files the new version no longer uses: remove them so old rubbish never gets committed
        if (Test-Path $stale) {
            foreach ($rel in (Get-Content $stale | Where-Object { $_.Trim() })) {
                $rel = $rel.Trim()
                if ($rel -notmatch '\.\.' -and $rel -notmatch '^(\.env|data)$') { Remove-Item (Join-Path $Root $rel) -Recurse -Force -ErrorAction SilentlyContinue }
            }
        }
        $installed = Get-Version $zip.Name
        Write-Host "Updated to v$installed (your .env, contacts and settings were kept)." -ForegroundColor Green
    }
}

# 2) Python environment and packages
$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    $sys = Get-Command python -ErrorAction SilentlyContinue
    if (-not $sys) { $sys = Get-Command py -ErrorAction SilentlyContinue }
    if (-not $sys) { Stop-Here "Python is not installed. Install it from python.org (tick 'Add to PATH'), then run this again." }
    & $sys.Source -m venv .venv
}
$hash = (("requirements-base.txt", "requirements-dev.txt") | ForEach-Object { (Get-FileHash (Join-Path $Root $_)).Hash }) -join ""
$stamp = Join-Path $Root ".venv\req.hash"
if (-not (Test-Path $stamp) -or ((Get-Content $stamp -Raw).Trim() -ne $hash)) {
    Write-Host "Installing packages (first time or after an update)..." -ForegroundColor Cyan
    & $py -m pip install -q -r requirements-base.txt -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { Stop-Here "Package install failed. Check your internet and run this again - it continues." }
    Set-Content $stamp $hash
}
if (-not (Test-Path "$Root\.env")) { Copy-Item "$Root\.env.example" "$Root\.env" }
if (-not (Select-String -Path "$Root\.env" -Pattern '^GROQ_API_KEY=\S' -Quiet)) { & "$Root\scripts\configure.ps1" }

# 3) menu
if ($Mode -eq "menu") {
    Write-Host "`n  1) Start Callie on this PC"
    Write-Host "  2) Start Callie + phone link"
    Write-Host "  3) Open the Callie folder"
    Write-Host "  4) Open the Callie folder in VS Code"
    Write-Host "  5) Save and push to GitHub"
    Write-Host "  6) Publish a release (GitHub builds the apps)"
    Write-Host "  7) Free up disk space"
    Write-Host "  8) Change access keys (Groq, Luganda)"
    $c = Read-Host "Choose (Enter = 1)"
    $Mode = switch ($c) { "2" { "phone" } "3" { "folder" } "4" { "code" } "5" { "push" } "6" { "release" } "7" { "clean" } "8" { "keys" } default { "pc" } }
}
if ($Mode -eq "release") { & "$Root\scripts\release.ps1"; return }
if ($Mode -eq "keys") { & "$Root\scripts\configure.ps1"; return }
if ($Mode -eq "clean") { & "$Root\scripts\clean.ps1"; return }
if ($Mode -eq "push") { & "$Root\scripts\push.ps1"; return }
if ($Mode -eq "folder") { Start-Process explorer.exe $Root; return }
if ($Mode -eq "code") {
    if (Get-Command code -ErrorAction SilentlyContinue) { code $Root } else { Start-Process explorer.exe $Root }
    return
}

# 4) start
if (Test-Callie) {
    Write-Host "Callie is already running." -ForegroundColor Green
    Start-Process "http://127.0.0.1:8000/"
} else {
    Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$Root\scripts\run.ps1`""
    for ($i = 0; $i -lt 40 -and -not (Test-Callie); $i++) { Start-Sleep 1 }
    if (Test-Callie) { Write-Host "Callie is running (the browser opens by itself)." -ForegroundColor Green }
    else { Write-Host "Callie did not start - read the other window for the error." -ForegroundColor Yellow }
}
if ($Mode -eq "phone") {
    Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$Root\scripts\phone.ps1`""
    Write-Host "Phone link window opened - scan the QR code it shows." -ForegroundColor Green
}
Write-Host "`nTo stop Callie, close its PowerShell window(s)."
