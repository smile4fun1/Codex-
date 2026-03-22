$ErrorActionPreference = "Stop"

if (-not (Get-Command go -ErrorAction SilentlyContinue)) {
    throw "Go is required to build the portable launcher (https://go.dev/dl/)."
}

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$outDir = Join-Path $root "dist\local"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$out = Join-Path $outDir "Codex.exe"
Write-Host "[Build] -> $out"
Push-Location $root
try {
    go build -trimpath -ldflags "-s -w" -o $out .\cmd\codex-portable
}
finally {
    Pop-Location
}

