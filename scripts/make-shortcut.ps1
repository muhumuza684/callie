# Puts a "Callie" shortcut (green C icon) on your Desktop. After this, just double-click it.
$Root = Split-Path $PSScriptRoot -Parent
$desk = [Environment]::GetFolderPath("Desktop")
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut((Join-Path $desk "Callie.lnk"))
$lnk.TargetPath = Join-Path $Root "Callie.cmd"
$lnk.WorkingDirectory = $Root
$lnk.IconLocation = Join-Path $Root "client\pwa\icons\callie.ico"
$lnk.Description = "Start Callie"
$lnk.Save()
Write-Host "Shortcut 'Callie' created on your Desktop. Double-click it to start." -ForegroundColor Green
