@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-prism-path.ps1"
exit /b %ERRORLEVEL%
