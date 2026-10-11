# Frees disk space safely. It never touches your key (.env), contacts or memory.
#   .\scripts\clean.ps1                 caches, logs, build leftovers, temp files
#   .\scripts\clean.ps1 -Tools          also the phone-link tool (about 50 MB, downloads again when needed)
#   .\scripts\clean.ps1 -Downloads      also old voice-ai-pwa-v*.zip files in Downloads (keeps the newest)
#   .\scripts\clean.ps1 -Venv           also the Python environment (Callie.cmd rebuilds it)
param([switch]$Tools, [switch]$Downloads, [switch]$Venv)
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

function Get-Bytes($path) {
    if (-not (Test-Path $path)) { return 0 }
    $m = Get-ChildItem $path -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum
    if ($m.Sum) { return [int64]$m.Sum } else { return 0 }
}
$freed = [int64]0
function Remove-Counted($path) {
    if (Test-Path $path) { $script:freed += (Get-Bytes $path); Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue }
}

Get-ChildItem $Root -Recurse -Directory -Force -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notlike "*\.venv\*" } | ForEach-Object { Remove-Counted $_.FullName }
foreach ($p in ".pytest_cache", "build", "dist") { Remove-Counted (Join-Path $Root $p) }
Get-ChildItem (Join-Path $Root "logs") -Filter "*.log*" -ErrorAction SilentlyContinue | ForEach-Object { Remove-Counted $_.FullName }
Get-ChildItem $env:TEMP -Filter "callie-*" -ErrorAction SilentlyContinue | ForEach-Object { Remove-Counted $_.FullName }
if (Test-Path ".venv\Scripts\python.exe") { & .\.venv\Scripts\python.exe -m pip cache purge 2>$null | Out-Null }

if ($Tools) { Remove-Counted (Join-Path $Root "tools") }
if ($Venv) { Remove-Counted (Join-Path $Root ".venv") }
if ($Downloads) {
    $dirs = @("D:\Downloads", (Join-Path $env:USERPROFILE "Downloads")) | Where-Object { Test-Path $_ }
    $zips = $dirs | ForEach-Object { Get-ChildItem $_ -Filter "voice-ai-pwa-v*.zip" -ErrorAction SilentlyContinue } |
        Sort-Object { if ($_.Name -match 'v(\d+)') { [int]$Matches[1] } else { 0 } } -Descending
    $zips | Select-Object -Skip 1 | ForEach-Object { Remove-Counted $_.FullName }
}

Write-Host ("Freed about {0:N1} MB." -f ($freed / 1MB)) -ForegroundColor Green
Write-Host "`nBiggest items in the Callie folder:"
Get-ChildItem $Root -Force -ErrorAction SilentlyContinue | ForEach-Object { [pscustomobject]@{ MB = [math]::Round((Get-Bytes $_.FullName) / 1MB, 1); Name = $_.Name } } |
    Sort-Object MB -Descending | Select-Object -First 6 | Format-Table -AutoSize
Write-Host "Tip: if this folder is inside OneDrive, OneDrive keeps a second copy of everything. Move the project out of OneDrive, or finish with the desktop app and delete the folder."
