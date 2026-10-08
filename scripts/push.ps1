# Saves your work and pushes it to GitHub:  .\scripts\push.ps1   (or  .\scripts\push.ps1 -Message "what changed")
param([string]$Message = "")
Set-Location (Split-Path $PSScriptRoot -Parent)
$Repo = "https://github.com/muhumuza684/callie.git"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Git is not installed. Get it from https://git-scm.com, then run this again." -ForegroundColor Yellow; return
}
if (-not (Test-Path .git)) { git init -b main | Out-Null; Write-Host "Started a new git repository." }

if (-not (git config user.name))  { git config user.name  (Read-Host "Your name for commits") }
if (-not (git config user.email)) { git config user.email (Read-Host "Your GitHub email") }

# safety: never publish your key or personal data
$private = @(git ls-files .env data/store.json data/memory.json data/profile.json tools)
if ($private.Count -gt 0) {
    Write-Host "Removing private files from git (they stay on your disk): $($private -join ', ')" -ForegroundColor Yellow
    git rm --cached -r -q -- $private
}

$version = ""
if (Test-Path VERSION) { $version = (Get-Content VERSION -Raw).Trim() }
if (-not $Message) { $Message = "Callie v$version" }

git add -A
if (git status --porcelain) { git commit -q -m $Message; Write-Host "Saved: $Message" -ForegroundColor Green }
else { Write-Host "Nothing new to save." }

if (-not ((git remote) -contains "origin")) { git remote add origin $Repo }
git push -u origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nPush did not go through." -ForegroundColor Yellow
    Write-Host "- If GitHub says the repository already has files (for example a README), run:"
    Write-Host "    git pull origin main --allow-unrelated-histories --no-edit"
    Write-Host "    .\scripts\push.ps1"
    Write-Host "- If it asks you to sign in, finish the sign-in window and run this again."
} else {
    Write-Host "`nPushed to https://github.com/muhumuza684/callie" -ForegroundColor Green
}
