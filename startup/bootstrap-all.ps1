$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Write-Host "[Codex] Preparing portable startup..."
& (Join-Path $root "startup\windows\CodexPortable.ps1") @args
exit $LASTEXITCODE
