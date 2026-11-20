@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\studio-diagnostics.ps1" %*
exit /b %ERRORLEVEL%
