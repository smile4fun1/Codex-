$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe = Join-Path $root "Codex.exe"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$main = Join-Path $root "main.py"

if (Test-Path $exe) {
    & $exe @args
    exit $LASTEXITCODE
}

Push-Location $root
try {
    if (Test-Path $venvPython) {
        & $venvPython $main @args
    }
    else {
        Write-Host "[Codex] Virtual environment not found. Bootstrapping wrapper with system Python..."
        & python $main @args
    }
}
finally {
    Pop-Location
}
