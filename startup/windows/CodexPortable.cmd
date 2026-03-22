@echo off
setlocal
set "ROOT=%~dp0..\.."
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "PYTHON_EXE=%ROOT%\.venv\Scripts\python.exe"
set "CODEX_ENTRY=%ROOT%\startup\runtime\windows\node_modules\@openai\codex\bin\codex.js"
set "NODE_EXE=%ROOT%\startup\runtime\windows\node.exe"
set "PORTABLE_HOME=%ROOT%\.codex-portable"

if not exist "%CODEX_ENTRY%" (
  call "%ROOT%\startup\windows\bootstrap-runtime.cmd"
  if errorlevel 1 exit /b %ERRORLEVEL%
)

if not exist "%PYTHON_EXE%" (
  where python >nul 2>nul
  if errorlevel 1 (
    if not exist "%NODE_EXE%" (
      echo Neither Python nor bundled Node runtime found.
      exit /b 1
    )
    mkdir "%PORTABLE_HOME%" 2>nul
    for %%D in (log memories rules sessions skills tmp) do mkdir "%PORTABLE_HOME%\\%%D" 2>nul
    set "CODEX_HOME=%PORTABLE_HOME%"
    set "HOME=%PORTABLE_HOME%"
    "%NODE_EXE%" "%CODEX_ENTRY%" -c personality=pragmatic %*
    exit /b %ERRORLEVEL%
  )
  python "%ROOT%\main.py" %*
  exit /b %ERRORLEVEL%
)

"%PYTHON_EXE%" "%ROOT%\main.py" %*
exit /b %ERRORLEVEL%
