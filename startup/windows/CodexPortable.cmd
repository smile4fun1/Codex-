@echo off
setlocal
set "ROOT=%~dp0..\.."
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "PYTHON_EXE=%ROOT%\.venv\Scripts\python.exe"
set "CODEX_ENTRY=%ROOT%\startup\runtime\windows\node_modules\@openai\codex\bin\codex.js"

if not exist "%CODEX_ENTRY%" (
  call "%ROOT%\startup\windows\bootstrap-runtime.cmd"
  if errorlevel 1 exit /b %ERRORLEVEL%
)

if not exist "%PYTHON_EXE%" (
  python "%ROOT%\main.py" %*
  exit /b %ERRORLEVEL%
)

"%PYTHON_EXE%" "%ROOT%\main.py" %*
exit /b %ERRORLEVEL%
