@echo off
setlocal
call "%~dp0startup\bootstrap-all.cmd" %*
exit /b %ERRORLEVEL%
