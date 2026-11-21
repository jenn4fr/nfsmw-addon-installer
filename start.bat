@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m nfsmw_installer.cli %*
) else (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -m nfsmw_installer.cli %*
    ) else (
        python -m nfsmw_installer.cli %*
    )
)
set "RC=%errorlevel%"
endlocal & exit /b %RC%
