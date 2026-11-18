@echo off
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0" || goto root_failed
if not exist ".venv\Scripts\python.exe" goto needs_setup
if not exist "frontend\dist\index.html" goto needs_setup

".venv\Scripts\python.exe" -m backend --open-browser
if errorlevel 1 goto failed
popd
exit /b 0

:needs_setup
echo Run setup.bat once before starting Koma Studio.
goto end_error

:failed
echo Koma Studio could not start. See the error above and README.md.
:end_error
popd
pause
exit /b 1

:root_failed
echo Could not open the studio sources from this location.
pause
exit /b 1
