@echo off
setlocal

set "SAFY_HOME=%~dp0.."
for %%I in ("%SAFY_HOME%") do set "SAFY_HOME=%%~fI"

if exist "C:\Program Files\Python312\python.exe" (
  set "SAFY_PYTHON=C:\Program Files\Python312\python.exe"
) else (
  set "SAFY_PYTHON=python"
)

set "PYTHONNOUSERSITE=1"
set "VIRTUAL_ENV="
cd /d "%SAFY_HOME%"
"%SAFY_PYTHON%" -m pip install -e .
set "SAFY_EXIT=%ERRORLEVEL%"
if "%SAFY_EXIT%"=="0" (
  echo.
  echo SAFY editable install completed.
  echo Run SAFY with: Scripts\safy.cmd run
)
endlocal & exit /b %SAFY_EXIT%
