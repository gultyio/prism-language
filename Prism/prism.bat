@echo off
if exist "%~dp0Prism.exe" (
    "%~dp0Prism.exe" %*
) else (
    python "%~dp0prism_ide.py" %*
)
exit /b %ERRORLEVEL%
