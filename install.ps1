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
$dir = (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName
if (-not (Test-Path -LiteralPath $dir)) {
    throw "Expanded archive folder not found: $dir"
}

if (Test-Path -LiteralPath $Dir) { Remove-Item -Recurse -Force $Dir }
Move-Item -LiteralPath $dir -Destination $Dir

Write-Host "[Codex] Launching..."
& (Join-Path $Dir "Codex.cmd")
