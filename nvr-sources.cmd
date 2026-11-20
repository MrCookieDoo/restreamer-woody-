@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\nvr-sources.ps1" %*
exit /b %ERRORLEVEL%
