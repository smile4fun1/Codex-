$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$python = Join-Path $root ".venv\Scripts\python.exe"
$main = Join-Path $root "main.py"
$codexEntry = Join-Path $root "startup\runtime\windows\node_modules\@openai\codex\bin\codex.js"

if (-not (Test-Path $codexEntry)) {
    & (Join-Path $root "startup\windows\bootstrap-runtime.ps1")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (Test-Path $python) {
    & $python $main @args
}
else {
    & python $main @args
}
