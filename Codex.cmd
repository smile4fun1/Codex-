@echo off
setlocal

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
if exist "%ROOT%\\Codex.exe" (
  "%ROOT%\\Codex.exe" %*
  exit /b %ERRORLEVEL%
)
call "%ROOT%\startup\windows\CodexPortable.cmd" %*
exit /b %ERRORLEVEL%
