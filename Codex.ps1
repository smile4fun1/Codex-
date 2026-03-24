$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe = Join-Path $root "Codex.exe"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$main = Join-Path $root "main.py"
$startup = Join-Path $root "Windows-Startup.cmd"

if (Test-Path $exe) {
    & $exe @args
    exit $LASTEXITCODE
}

Push-Location $root
try {
    & $startup @args
}
finally {
    Pop-Location
}
