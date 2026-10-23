# Saves your access keys into .env. Run it any time: press Enter to keep what is already there.
#   Groq key    https://console.groq.com/keys   (starts with gsk_)
#   Luganda     https://api.sunbird.ai          (optional token from Sunbird AI)
#   One line, no questions:  .\scripts\configure.ps1 -Sunbird "TOKEN"   (or -Groq "KEY", or both)
param([string]$Groq = "", [string]$Sunbird = "")
Set-Location (Split-Path $PSScriptRoot -Parent)

function Get-Setting($name) {
    if (Test-Path .env) {
        $m = Select-String -Path .env -Pattern "^$name=(.*)$" | Select-Object -First 1
        if ($m) { return $m.Matches[0].Groups[1].Value.Trim() }
    }
    return ""
}
function Set-Setting($name, $value) {
    $lines = @()
    if (Test-Path .env) { $lines = @(Get-Content .env) } elseif (Test-Path .env.example) { $lines = @(Get-Content .env.example) }
    $found = $false
    $out = @($lines | ForEach-Object { if ($_ -match "^$name=") { $found = $true; "$name=$value" } else { $_ } })
    if (-not $found) { $out += "$name=$value" }
    Set-Content -Path .env -Value $out -Encoding ascii
}

if ($Groq.Trim() -or $Sunbird.Trim()) {
    if ($Groq.Trim()) { Set-Setting "GROQ_API_KEY" $Groq.Trim() }
    if ($Sunbird.Trim()) { Set-Setting "SUNBIRD_API_TOKEN" $Sunbird.Trim() }
    Write-Host "Saved to .env" -ForegroundColor Green
    Write-Host "If Callie is running, close its window and start it again so the new keys are used." -ForegroundColor Cyan
    return
}

$groq = Get-Setting "GROQ_API_KEY"
if ($groq) { $new = (Read-Host "Groq access key (Enter to keep the current one)").Trim() } else { $new = (Read-Host "Paste your Groq access key (starts with gsk_)").Trim() }
if ($new) { Set-Setting "GROQ_API_KEY" $new; $groq = $new }
if (-not $groq) { Write-Host "No key entered. Run .\scripts\configure.ps1 again when you have it." -ForegroundColor Yellow; return }

$sun = (Read-Host "Luganda token from Sunbird AI (Enter to skip or keep the current one)").Trim()
if ($sun) { Set-Setting "SUNBIRD_API_TOKEN" $sun }

Write-Host "Saved to .env" -ForegroundColor Green
Write-Host "If Callie is running, close its window and start it again so the new keys are used." -ForegroundColor Cyan
