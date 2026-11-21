@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m venv .venv
) else (
    python -m venv .venv
)
if errorlevel 1 goto :error
call .venv\Scripts\activate.bat
if errorlevel 1 goto :error
python -m pip install -e .
if errorlevel 1 goto :error
python -m compileall -q nfsmw_installer tools tests
if errorlevel 1 goto :error
python -m unittest discover -s tests -v
if errorlevel 1 goto :error
echo.
echo Setup and tests completed successfully.
pause
exit /b 0
:error
echo Setup failed. Review the error above.
pause
exit /b 1
