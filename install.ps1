param(
    [string]$Dir = (Join-Path $env:USERPROFILE "Codex-")
)

$ErrorActionPreference = "Stop"

$repo = "smile4fun1/Codex-"
$zipUrl = "https://github.com/$repo/archive/refs/heads/main.zip"
$zip = Join-Path $env:TEMP "codex-portable.zip"
$tmp = Join-Path $env:TEMP "codex-portable"
$portableBin = Join-Path $env:USERPROFILE ".codex-portable-bin"
$shimPath = Join-Path $portableBin "codex.cmd"

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

Write-Host "[Codex] Registering 'codex' command..."
New-Item -ItemType Directory -Force -Path $portableBin | Out-Null
@"
@echo off
setlocal
call "$Dir\codex.cmd" %*
exit /b %ERRORLEVEL%
"@ | Set-Content -Encoding ASCII -Path $shimPath

$currentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$pathEntries = @()
if ($currentUserPath) {
    $pathEntries = $currentUserPath -split ';' | Where-Object { $_ }
}
if ($pathEntries -notcontains $portableBin) {
    $newPath = @($portableBin) + $pathEntries
    [Environment]::SetEnvironmentVariable("Path", ($newPath -join ';'), "User")
    Write-Host "[Codex] Added $portableBin to user PATH. Open a new terminal and run: codex"
}
else {
    Write-Host "[Codex] 'codex' is already on user PATH."
}

Write-Host "[Codex] Launching..."
Start-Process -FilePath (Join-Path $Dir "Codex.cmd") -WorkingDirectory $Dir
