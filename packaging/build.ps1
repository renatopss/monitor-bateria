# Gera dist\MonitorBateria-<versão>-setup.exe
# Requisitos: Python 3.10+ e Inno Setup 6 (winget install JRSoftware.InnoSetup)
# Uso (na raiz do projeto):  powershell -ExecutionPolicy Bypass -File packaging\build.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$venv = Join-Path $root '.venv-build'
$py = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path $py)) {
    python -m venv $venv
    & $py -m pip install --require-hashes --only-binary=:all: -r requirements.txt
    & $py -m pip install pyinstaller==6.16.0
}

$version = (& $py -c "import sys; sys.path.insert(0, 'src'); import monitor_bateria; print(monitor_bateria.__version__)").Trim()
Write-Host "Versão $version"

$build = Join-Path $PSScriptRoot 'build'
if (Test-Path $build) { Remove-Item -Recurse -Force $build }
& $py packaging\make_icon.py "$build\app.ico"

& $py -m PyInstaller --noconfirm --clean --windowed --onedir `
    --name MonitorBateria --icon "$build\app.ico" `
    --paths src --collect-submodules monitor_bateria `
    --hidden-import pystray._win32 `
    --distpath "$build\dist" --workpath "$build\work" --specpath $build `
    packaging\run.py
if ($LASTEXITCODE) { throw "PyInstaller falhou" }

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 não encontrado" }
& $iscc "/DAppVersion=$version" packaging\installer.iss
if ($LASTEXITCODE) { throw "Inno Setup falhou" }

Get-Item "dist\MonitorBateria-$version-setup.exe"
