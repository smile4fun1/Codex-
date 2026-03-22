param(
    [string]$Dir = (Join-Path $env:USERPROFILE "Codex-")
)

$ErrorActionPreference = "Stop"

$repo = "smile4fun1/Codex-"
$zipUrl = "https://github.com/$repo/archive/refs/heads/main.zip"
$zip = Join-Path $env:TEMP "codex-portable.zip"
$tmp = Join-Path $env:TEMP "codex-portable"

Write-Host "[Codex] Downloading $zipUrl"
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
Invoke-WebRequest -UseBasicParsing $zipUrl -OutFile $zip

Write-Host "[Codex] Extracting..."
Expand-Archive -Force $zip $tmp
$sourceDir = (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName
if (-not (Test-Path -LiteralPath $sourceDir)) {
    throw "Expanded archive folder not found: $sourceDir"
}

if (Test-Path -LiteralPath $Dir) { Remove-Item -Recurse -Force $Dir }
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
Copy-Item -Recurse -Force (Join-Path $sourceDir '*') $Dir

Write-Host "[Codex] Launching..."
Start-Process -FilePath (Join-Path $Dir "Codex.cmd") -WorkingDirectory $Dir
