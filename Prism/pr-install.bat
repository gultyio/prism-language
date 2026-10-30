@echo off
if exist "%~dp0Prism.exe" (
    "%~dp0Prism.exe" pr-install %*
) else (
    python "%~dp0prism_ide.py" pr-install %*
)
exit /b %ERRORLEVEL%
