$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$main = Join-Path $root "main.py"

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
