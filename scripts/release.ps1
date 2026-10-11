# Publishes a release: saves and pushes your work, tags it with the number in the VERSION file, and
# GitHub then builds the Windows, Mac and Linux apps and attaches them to a Release page.
Set-Location (Split-Path $PSScriptRoot -Parent)
& .\scripts\push.ps1 -Message "Prepare release"
$v = (Get-Content VERSION -Raw).Trim()
$tag = "v$v"
if (git tag -l $tag) {
    Write-Host "Release $tag already exists. Raise the number in the VERSION file, then run this again." -ForegroundColor Yellow; return
}
git tag $tag
git push origin $tag
if ($LASTEXITCODE -ne 0) { Write-Host "Could not publish the tag. Run .\scripts\push.ps1 first and check the sign-in." -ForegroundColor Yellow; return }
Write-Host "`nRelease $tag started." -ForegroundColor Green
Write-Host "Watch it build:  https://github.com/muhumuza684/callie/actions"
Write-Host "In about 10 minutes the apps appear here:  https://github.com/muhumuza684/callie/releases"
