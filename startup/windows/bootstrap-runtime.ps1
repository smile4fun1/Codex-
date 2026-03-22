$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$runtimeDir = Join-Path $root "startup\runtime\windows"
$codexEntry = Join-Path $runtimeDir "node_modules\@openai\codex\bin\codex.js"
$nodeExe = Join-Path $runtimeDir "node.exe"
$runtimeVersionPath = Join-Path $runtimeDir "runtime-version.json"

if ((Test-Path $nodeExe) -and (Test-Path $codexEntry)) {
    Write-Host "[Codex] Windows runtime already present."
    exit 0
}

Add-Type -AssemblyName System.Runtime.InteropServices
$arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture
$distArch = switch ($arch) {
    "X64" { "win-x64" }
    "Arm64" { "win-arm64" }
    default { throw "Unsupported Windows architecture: $arch (supported: X64, Arm64)" }
}

Write-Host "[Codex] Detecting latest Node.js LTS for Windows ($distArch)..."
$index = Invoke-RestMethod -Uri "https://nodejs.org/dist/index.json" -TimeoutSec 30
$lts = $index | Where-Object { $_.lts } | Select-Object -First 1
if (-not $lts) { throw "No LTS version found in Node index.json" }
$ver = $lts.version

$zipName = "node-$ver-$distArch.zip"
$base = "https://nodejs.org/dist/$ver"
$zipUrl = "$base/$zipName"
$sumUrl = "$base/SHASUMS256.txt"

$tmp = New-Item -ItemType Directory -Force -Path ([System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "codex-win-runtime-$([System.Guid]::NewGuid().ToString('N'))"))
try {
    $zipPath = Join-Path $tmp.FullName $zipName
    $sumPath = Join-Path $tmp.FullName "SHASUMS256.txt"
    $extractPath = Join-Path $tmp.FullName "extract"

    Write-Host "[Codex] Downloading $zipName..."
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing -TimeoutSec 120
    Invoke-WebRequest -Uri $sumUrl -OutFile $sumPath -UseBasicParsing -TimeoutSec 120

    $expected = (Select-String -Path $sumPath -Pattern (" " + [regex]::Escape($zipName) + "$") | Select-Object -First 1).Line.Split(" ")[0]
    if (-not $expected) { throw "Could not find SHA256 for $zipName in SHASUMS256.txt" }
    $actual = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected.ToLowerInvariant()) { throw "SHA256 mismatch for $zipName" }

    if (Test-Path $runtimeDir) { Remove-Item -Recurse -Force $runtimeDir }
    New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
    New-Item -ItemType Directory -Force -Path $extractPath | Out-Null

    Write-Host "[Codex] Extracting Node.js into app runtime..."
    Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force

    $top = Join-Path $extractPath ("node-$ver-$distArch")
    if (-not (Test-Path $top)) { throw "Unexpected archive layout: $top not found" }

    Copy-Item -Recurse -Force (Join-Path $top "*") $runtimeDir

    $npm = Join-Path $runtimeDir "npm.cmd"
    if (-not (Test-Path $npm)) { throw "npm.cmd not found in extracted Node runtime" }

    Write-Host "[Codex] Installing @openai/codex into app runtime..."
    & $npm --prefix $runtimeDir install --no-audit --no-fund @openai/codex
    $codexPackage = Join-Path $runtimeDir "node_modules\@openai\codex\package.json"
    $codexVersion = ""
    if (Test-Path $codexPackage) {
        $codexVersion = (Get-Content $codexPackage -Raw | ConvertFrom-Json).version
    }
    @{
        platform = "windows"
        node_version = $ver
        codex_version = $codexVersion
        installed_at = (Get-Date).ToString("o")
    } | ConvertTo-Json | Set-Content -Encoding UTF8 $runtimeVersionPath
    exit $LASTEXITCODE
}
finally {
    Remove-Item -Recurse -Force $tmp.FullName -ErrorAction SilentlyContinue
}
