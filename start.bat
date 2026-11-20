@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"

:MENU
cls
echo ==================================================
echo    NFSMW ADD-ON INSTALLER - CONTROL PANEL
echo ==================================================
echo.
echo   1. Inspect a car mod folder or ZIP archive
echo   2. Run project tests
echo   3. Open reports folder
echo   4. Show help / current capabilities
echo   5. Exit
echo.
set "CHOICE="
set /p "CHOICE=Choose an option [1-5]: "
if "%CHOICE%"=="1" goto INSPECT
if "%CHOICE%"=="2" goto TESTS
if "%CHOICE%"=="3" goto REPORTS
if "%CHOICE%"=="4" goto HELP
if "%CHOICE%"=="5" goto END
echo.
echo Invalid choice.
pause
goto MENU

:INSPECT
cls
echo ==================================================
echo    INSPECT CAR MOD
echo ==================================================
echo.
set "CAR_PATH="
set /p "CAR_PATH=Paste the full path to the extracted mod folder or ZIP: "
if not defined CAR_PATH (
  echo.
  echo No path entered.
  pause
  goto MENU
)
rem Remove one pair of surrounding double quotes, if pasted.
if "%CAR_PATH:~0,1%"==""" set "CAR_PATH=%CAR_PATH:~1,-1%"
if not exist "%CAR_PATH%" (
  echo.
  echo ERROR: Path not found: "%CAR_PATH%"
  pause
  goto MENU
)
for %%I in ("%CAR_PATH%") do set "CAR_NAME=%%~nI"
if not exist "reports" mkdir "reports"
set "REPORT=reports\%CAR_NAME%-report.json"
echo.
echo Input:  "%CAR_PATH%"
echo Output: "%REPORT%"
echo.
call :RUN_PYTHON -m nfsmw_installer.cli inspect "%CAR_PATH%" -o "%REPORT%"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
  echo Inspection completed. No game files were changed.
  echo Report saved to: %REPORT%
) else (
  echo Inspection failed with exit code %RESULT%.
)
echo.
choice /c YN /n /m "Inspect another mod? [Y/N]: "
if errorlevel 2 goto MENU
goto INSPECT

:TESTS
cls
echo Running unit tests...
echo.
call :RUN_PYTHON -m unittest discover -s tests -v
echo.
pause
goto MENU

:REPORTS
if not exist "reports" mkdir "reports"
start "" explorer "%CD%\reports"
goto MENU

:HELP
cls
echo ==================================================
echo    CURRENT CAPABILITIES - VERSION 0.1.0
echo ==================================================
echo.
echo - Inspect extracted mod folders and ZIP archives.
echo - Identify common Unlimiter, NFSMS, ModLoader,
echo   MWPS, INI, model, texture and resource files.
echo - Parse NFSMS commands and report findings.
echo - Optional VLT inventory comparison via CLI.
echo.
echo SAFETY: This version is an analysis tool only.
echo It does NOT install cars or modify VLT/BIN files.
echo RAR/7z listing requires 7-Zip on PATH.
echo.
pause
goto MENU

:RUN_PYTHON
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" %*
  exit /b %ERRORLEVEL%
)
where py >nul 2>nul
if not errorlevel 1 (
  py %*
  exit /b %ERRORLEVEL%
)
where python >nul 2>nul
if not errorlevel 1 (
  python %*
  exit /b %ERRORLEVEL%
)
echo ERROR: Python was not found. Install Python 3.10+ or create .venv.
exit /b 9009

:END
endlocal
exit /b 0
