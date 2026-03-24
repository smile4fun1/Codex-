$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$python = Join-Path $root ".venv\Scripts\python.exe"
$main = Join-Path $root "main.py"
$codexEntry = Join-Path $root "startup\runtime\windows\node_modules\@openai\codex\bin\codex.js"
$nodeExe = Join-Path $root "startup\runtime\windows\node.exe"
$portableHome = $root.ToString()

if (-not (Test-Path $codexEntry)) {
    & (Join-Path $root "startup\windows\bootstrap-runtime.ps1")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (Test-Path $python) {
    & $python $main @args
}
else {
    $sysPython = Get-Command python -ErrorAction SilentlyContinue
    if ($sysPython) {
        & python $main @args
        exit $LASTEXITCODE
    }
    if (-not (Test-Path $nodeExe)) {
        Write-Error "Neither Python nor bundled Node runtime found."
        exit 1
    }
    foreach ($name in @("log", "memories", "rules", "sessions", "skills", "tmp")) {
        New-Item -ItemType Directory -Force -Path (Join-Path $portableHome $name) | Out-Null
    }
    $env:CODEX_HOME = $portableHome
    $env:HOME = $portableHome
    & $nodeExe $codexEntry -c personality=pragmatic @args
}
