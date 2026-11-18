@echo off
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0" || goto root_failed

echo Checking setup prerequisites...
where.exe node.exe >nul 2>&1
if errorlevel 1 goto node_missing
node.exe -e "const [major,minor]=process.versions.node.split('.').map(Number);process.exit(major >= 23 || (major === 22 && minor >= 12) ? 0 : 1)"
if errorlevel 1 goto node_missing
where.exe npm.cmd >nul 2>&1
if errorlevel 1 goto node_missing

if exist ".venv\Scripts\python.exe" goto install_python
where.exe py.exe >nul 2>&1
if errorlevel 1 goto python_on_path
py.exe -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 goto python_on_path
py.exe -3 -m venv ".venv"
if errorlevel 1 goto failed
goto install_python

:python_on_path
where.exe python.exe >nul 2>&1
if errorlevel 1 goto python_missing
python.exe -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 goto python_missing
python.exe -m venv ".venv"
if errorlevel 1 goto failed

:install_python
".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 goto python_missing
echo Installing local Python dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "backend\requirements.txt"
if errorlevel 1 goto failed

echo Building the offline interface...
pushd "frontend" || goto failed
call npm.cmd ci --no-audit --no-fund
if errorlevel 1 goto frontend_failed
call npm.cmd run build
if errorlevel 1 goto frontend_failed
popd

echo.
echo Setup complete. Run start.bat to open Koma Studio.
echo No models or FFmpeg were downloaded. Drafts work without either.
popd
exit /b 0

:frontend_failed
popd
goto failed

:node_missing
echo Node.js 22.12 or newer with npm is required for the initial build.
goto failed

:python_missing
echo Python 3.11 or newer is required. If an old .venv exists, rename it and rerun setup.
goto failed

:failed
echo Setup did not complete. See the output above and README.md.
popd
pause
exit /b 1

:root_failed
echo Could not open the studio sources. Put them in a writable folder on a local drive.
pause
exit /b 1
