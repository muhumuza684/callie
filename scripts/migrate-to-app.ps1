# Copies your key, contacts, schedule and memory into the desktop app's folder, so you can delete this project folder
# and keep using Callie.exe with everything exactly as it is now.
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
$dest = Join-Path $env:APPDATA "Callie"
New-Item -ItemType Directory -Force (Join-Path $dest "data") | Out-Null
if (Test-Path "$Root\.env") { Copy-Item "$Root\.env" (Join-Path $dest ".env") -Force; Write-Host "Copied your access key" }
foreach ($f in "store.json", "memory.json", "profile.json") {
    if (Test-Path "$Root\data\$f") { Copy-Item "$Root\data\$f" (Join-Path $dest "data\$f") -Force; Write-Host "Copied data\$f" }
}
Write-Host "`nSaved to: $dest" -ForegroundColor Green

if (Get-Command git -ErrorAction SilentlyContinue) {
    $dirty = git status --porcelain
    $unpushed = git log origin/main..HEAD --oneline 2>$null
    if ($dirty -or $unpushed) {
        Write-Host "`nWait - some work is not on GitHub yet. Run .\scripts\push.ps1 before deleting this folder." -ForegroundColor Yellow
    } else {
        Write-Host "Everything is on GitHub. After you have checked that Callie.exe works, you can delete this folder." -ForegroundColor Green
    }
}
