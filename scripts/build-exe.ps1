# Builds Callie.exe on this PC (GitHub can also build it for you - see the release option in the launcher).
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Host "Start Callie once with Callie.cmd first, so the Python environment exists." -ForegroundColor Yellow; return }
& $py -m pip install -q pyinstaller
& $py -m PyInstaller --noconfirm callie.spec
if (-not (Test-Path "dist\Callie.exe")) { Write-Host "The build did not finish. Read the messages above." -ForegroundColor Yellow; return }
$desk = [Environment]::GetFolderPath("Desktop")
Copy-Item "dist\Callie.exe" $desk -Force
Remove-Item build -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Callie.exe is on your Desktop. Double-click it." -ForegroundColor Green
